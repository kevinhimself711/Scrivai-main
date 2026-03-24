"""SDK 入口模块。

提供 Project 作为统一入口，负责配置加载和组件组装。
"""

from __future__ import annotations

import locale
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from core.audit.engine import AuditEngine
from core.generation.context import GenerationContext
from core.generation.engine import GenerationEngine
from core.knowledge.store import KnowledgeStore
from core.llm import LLMClient, LLMConfig

logger = logging.getLogger(__name__)


@dataclass
class ProjectConfig:
    """项目配置。"""

    llm: LLMConfig
    knowledge: dict[str, Any] = field(
        default_factory=lambda: {"db_path": "data/scrivai.db", "namespace": "default"}
    )
    generation: dict[str, Any] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)


def _read_text_with_fallback(path: Path) -> str:
    raw = path.read_bytes()
    encodings = ["utf-8", "utf-8-sig", locale.getpreferredencoding(False), "gbk", "cp1252"]
    seen: set[str] = set()
    for encoding in encodings:
        if not encoding or encoding in seen:
            continue
        seen.add(encoding)
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", raw, 0, 1, f"无法识别文件编码: {path}")


def _escape_backslashes_in_quoted_scalars(text: str) -> str:
    return re.sub(
        r'"([^"\n]*)"',
        lambda match: '"' + match.group(1).replace('\\', '\\\\') + '"',
        text,
    )


def _load_yaml_file(path: Path) -> dict[str, Any]:
    text = _read_text_with_fallback(path)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        data = yaml.safe_load(_escape_backslashes_in_quoted_scalars(text))

    if not isinstance(data, dict):
        raise ValueError(f"YAML 顶层结构必须是映射: {path}")
    return data


class Project:
    """SDK 统一入口，负责配置加载和组件组装。"""

    def __init__(self, config_path: str) -> None:
        config = self._load_config(config_path)
        runtime_llm_config = self._build_runtime_llm_config(config.llm)

        self.llm = LLMClient(runtime_llm_config)
        logger.info("LLMClient 初始化完成: model=%s", runtime_llm_config.model)

        self.store: KnowledgeStore | None = None
        kb_cfg = config.knowledge
        if kb_cfg is not None and kb_cfg is not False:
            db_path = kb_cfg.get("db_path", "data/scrivai.db")
            namespace = kb_cfg.get("namespace", "default")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self.store = KnowledgeStore(db_path, namespace)
            logger.info("KnowledgeStore 初始化完成: db=%s, ns=%s", db_path, namespace)

        self.gen = GenerationEngine(self.llm, self.store)
        self.ctx = GenerationContext(self.llm)
        logger.info("GenerationEngine + GenerationContext 初始化完成")

        self.audit = AuditEngine(self.llm, self.store)
        logger.info("AuditEngine 初始化完成")

        self._config = config

    def _build_runtime_llm_config(self, llm_config: LLMConfig) -> LLMConfig:
        load_dotenv()
        return LLMConfig(
            model=os.getenv("MODEL_NAME") or llm_config.model,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            api_base=os.getenv("BASE_URL") or llm_config.api_base,
            api_key=os.getenv("LLM_API_KEY") or os.getenv("API_KEY") or llm_config.api_key,
        )

    def _load_config(self, config_path: str) -> ProjectConfig:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        data = _load_yaml_file(path)
        if not data or "llm" not in data:
            raise ValueError("配置文件必须包含 llm 字段")

        llm_data = data["llm"]
        llm_config = LLMConfig(
            model=llm_data.get("model"),
            temperature=llm_data.get("temperature", 0.7),
            max_tokens=llm_data.get("max_tokens", 4096),
            api_base=llm_data.get("api_base"),
            api_key=llm_data.get("api_key"),
        )

        return ProjectConfig(
            llm=llm_config,
            knowledge=data.get("knowledge", {}),
            generation=data.get("generation", {}),
            audit=data.get("audit", {}),
        )

    @property
    def config(self) -> ProjectConfig:
        """访问原始配置对象。"""
        return self._config
