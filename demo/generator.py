"""线路工程 demo 文档生成服务。"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import jinja2
from dotenv import load_dotenv
from jinja2 import meta

from core.llm import LLMClient, LLMConfig
from demo.config_loader import (
    get_enabled_chapters,
    get_field_map,
    iter_field_defs,
    load_chapter_registry,
    load_field_schema,
    resolve_repo_path,
    resolve_template_path,
)
from demo.source_data import render_block_ref

_CODE_FENCE_PATTERN = re.compile(r"^\s*```(?:markdown)?\s*|\s*```\s*$", re.MULTILINE)
_PERCENT_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*%?\s*$")
_LLM_REWRITE_CHAPTER_IDS = {"chapter_1", "chapter_2"}
_DEFAULT_MODEL = "qwen3-max"
_DEFAULT_REWRITE_MODEL = _DEFAULT_MODEL
_DEFAULT_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_TEMPERATURE = "0.2"
_DEFAULT_MAX_TOKENS = "4096"
_DEFAULT_REWRITE_MAX_TOKENS = "3072"


def build_initial_demo_inputs(
    schema: dict[str, Any] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """从 schema 构造初始表单数据和表格数据。"""
    schema = schema or load_field_schema()
    form_data: dict[str, str] = {}
    editable_tables: dict[str, str] = {}

    for field in iter_field_defs(schema):
        field_type = field.get("type", "text")
        if field_type == "markdown_table":
            source_ref = field.get("source_ref")
            if source_ref:
                data_file = resolve_repo_path(source_ref["data_file"])
                editable_tables[field["id"]] = render_block_ref(data_file, source_ref)
            else:
                editable_tables[field["id"]] = field.get("default", "")
            continue

        form_data[field["id"]] = str(field.get("default", ""))

    return form_data, editable_tables


def generate_demo_markdown(
    form_data: dict[str, Any],
    editable_tables: dict[str, str],
    enabled_chapters: list[str] | None = None,
    custom_requirements: str = "",
    llm_config: dict[str, Any] | None = None,
) -> str:
    """生成 demo Markdown 文档。"""
    field_schema = load_field_schema()
    chapter_registry = load_chapter_registry()
    field_map = get_field_map(field_schema)

    normalized_form = _normalize_form_data(field_map, form_data)
    normalized_tables = _normalize_table_inputs(field_map, editable_tables)
    chapters = get_enabled_chapters(chapter_registry, enabled_chapters)
    toc_entries = _build_toc_entries(chapters)

    base_context = {
        **normalized_form,
        **normalized_tables,
        "toc_entries": toc_entries,
        "source_blocks": {},
        "terrain_total_ratio": _sum_percentages(
            normalized_form.get("high_mountain_ratio", ""),
            normalized_form.get("mountain_ratio", ""),
        ),
    }

    fragments: list[dict[str, str]] = []
    for chapter in chapters:
        context = dict(base_context)
        context["source_blocks"] = _resolve_source_blocks(chapter)
        fragments.append(
            {
                "id": chapter["id"],
                "title": chapter["title"],
                "markdown": _render_fragment(chapter["template"], context),
            }
        )

    if custom_requirements.strip():
        fragments = _apply_custom_requirements_to_fragments(
            fragments=fragments,
            custom_requirements=custom_requirements,
            llm_config=llm_config or {},
        )

    return "\n\n".join(
        fragment["markdown"].strip() for fragment in fragments if fragment["markdown"].strip()
    ).strip()


def validate_template_context(
    schema: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """检查模板变量是否都能在上下文中找到。"""
    schema = schema or load_field_schema()
    registry = registry or load_chapter_registry()

    env = jinja2.Environment()
    known_vars = {
        *get_field_map(schema).keys(),
        "toc_entries",
        "terrain_total_ratio",
        "source_blocks",
    }

    missing: dict[str, list[str]] = {}
    for chapter in registry.get("chapters", []):
        template_source = resolve_template_path(chapter["template"]).read_text(encoding="utf-8")
        parsed = env.parse(template_source)
        undeclared = sorted(meta.find_undeclared_variables(parsed) - known_vars)
        if undeclared:
            missing[chapter["id"]] = undeclared
    return missing


def _normalize_form_data(
    field_map: dict[str, dict[str, Any]],
    form_data: dict[str, Any],
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for field_id, field in field_map.items():
        if field.get("type") == "markdown_table":
            continue

        raw_value = form_data.get(field_id, field.get("default", ""))
        value = str(raw_value).strip()
        if not value:
            if field.get("required", False):
                raise ValueError(f"缺少必填项: {field['label']}")
            value = field.get("empty_value", "待补充")
        normalized[field_id] = value
    return normalized


def _normalize_table_inputs(
    field_map: dict[str, dict[str, Any]],
    editable_tables: dict[str, str],
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for field_id, field in field_map.items():
        if field.get("type") != "markdown_table":
            continue

        value = editable_tables.get(field_id, "").strip()
        if not value:
            if field.get("required", False):
                raise ValueError(f"缺少必填表格: {field['label']}")
            value = field.get("empty_value", "")
        normalized[field_id] = value
    return normalized


def _resolve_source_blocks(chapter: dict[str, Any]) -> dict[str, str]:
    blocks: dict[str, str] = {}
    for alias, ref in (chapter.get("source_blocks") or {}).items():
        data_file = resolve_repo_path(ref.get("data_file", chapter["data_file"]))
        blocks[alias] = render_block_ref(data_file, ref)
    return blocks


def _render_fragment(template_name: str, context: dict[str, Any]) -> str:
    template_path = resolve_template_path(template_name)
    template_str = template_path.read_text(encoding="utf-8").replace("\ufeff", "")
    return jinja2.Template(template_str).render(**context)


def _build_toc_entries(chapters: list[dict[str, Any]]) -> list[str]:
    entries: list[str] = []
    for chapter in chapters:
        if chapter.get("include_in_toc", False):
            entries.extend(chapter.get("toc_entries", []))
    return entries


def _sum_percentages(*values: str) -> str:
    total = 0.0
    parsed_any = False
    for value in values:
        match = _PERCENT_PATTERN.match(value or "")
        if not match:
            continue
        total += float(match.group(1))
        parsed_any = True

    if not parsed_any:
        return "100%"
    if total.is_integer():
        return f"{int(total)}%"
    return f"{total:.1f}%"


def _apply_custom_requirements_to_fragments(
    fragments: list[dict[str, str]],
    custom_requirements: str,
    llm_config: dict[str, Any],
) -> list[dict[str, str]]:
    target_indexes = [
        index for index, fragment in enumerate(fragments) if fragment["id"] in _LLM_REWRITE_CHAPTER_IDS
    ]
    if not target_indexes:
        return fragments

    # 第 1/2 章互不依赖，可以并行改写，把总等待时间从两次串行调用压成一次最长调用。
    def rewrite(index: int) -> tuple[int, str]:
        fragment = fragments[index]
        client = _build_llm_client(llm_config, purpose="rewrite")
        rewritten = _apply_custom_requirements(
            llm=client,
            chapter_title=fragment["title"],
            chapter_markdown=fragment["markdown"],
            custom_requirements=custom_requirements,
        )
        return index, rewritten

    rewritten_map: dict[int, str] = {}
    max_workers = min(len(target_indexes), 2)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for index, rewritten in executor.map(rewrite, target_indexes):
            rewritten_map[index] = rewritten

    merged_fragments = [dict(fragment) for fragment in fragments]
    for index, rewritten in rewritten_map.items():
        merged_fragments[index]["markdown"] = rewritten
    return merged_fragments


def _build_llm_client(llm_config: dict[str, Any], purpose: str = "default") -> LLMClient:
    model = _resolve_model_for_purpose(llm_config, purpose)
    api_key = str(llm_config.get("api_key", "")).strip()
    if not model or not api_key:
        raise ValueError("填写客制化要求前，请先提供可用的 LLM model 和 api_key。")

    max_tokens = _resolve_max_tokens_for_purpose(llm_config, purpose)
    return LLMClient(
        LLMConfig(
            model=model,
            temperature=float(llm_config.get("temperature", _DEFAULT_TEMPERATURE)),
            max_tokens=max_tokens,
            api_base=str(llm_config.get("api_base", "")).strip() or None,
            api_key=api_key,
        )
    )


def _resolve_model_for_purpose(llm_config: dict[str, Any], purpose: str) -> str:
    configured_model = str(llm_config.get("model", "")).strip()
    if purpose != "rewrite":
        return configured_model

    rewrite_model = str(llm_config.get("rewrite_model", "")).strip()
    if rewrite_model:
        return rewrite_model
    if configured_model == _DEFAULT_MODEL:
        return _DEFAULT_REWRITE_MODEL
    return configured_model


def _resolve_max_tokens_for_purpose(llm_config: dict[str, Any], purpose: str) -> int:
    key = "rewrite_max_tokens" if purpose == "rewrite" else "max_tokens"
    default_value = _DEFAULT_REWRITE_MAX_TOKENS if purpose == "rewrite" else _DEFAULT_MAX_TOKENS
    return int(str(llm_config.get(key, llm_config.get("max_tokens", default_value))).strip() or default_value)


def _apply_custom_requirements(
    llm: LLMClient,
    chapter_title: str,
    chapter_markdown: str,
    custom_requirements: str,
) -> str:
    prompt = """
你是电力线路工程施工方案编辑助手。请只改写当前章节，把客制化要求自然融入现有表述。
绝对要求：
1. 只输出当前章节，不新增、删除、合并章节。
2. 必须完整保留现有 Markdown 标题层级、表格结构、工程数据和编号顺序，不得省略任何原有小节、列表项或表格。
3. 如客制化要求与本章节关系不大，只做最小必要融入。
4. 若客制化要求包含明确主题词，例如“雨季施工”“环保水保”“山区运输”“边坡稳定”“夜间施工”，请在相关段落中明确体现这些主题词或其正式同义表述，不要只写成笼统的“客制化要求”。
5. 不输出解释、前后缀、代码块或“修改说明”。

当前章节标题：
{{ chapter_title }}

客制化要求：
{{ custom_requirements }}

当前章节内容：
{{ chapter_markdown }}
"""
    response = llm.chat_with_template(
        prompt,
        {
            "chapter_title": chapter_title,
            "custom_requirements": custom_requirements.strip(),
            "chapter_markdown": chapter_markdown,
        },
    )
    rewritten = _CODE_FENCE_PATTERN.sub("", response).strip()
    if not _rewrite_output_is_valid(chapter_markdown, rewritten):
        return chapter_markdown
    return rewritten


def _rewrite_output_is_valid(original_markdown: str, rewritten_markdown: str) -> bool:
    if not rewritten_markdown:
        return False

    original_headings = [
        line.strip() for line in original_markdown.splitlines() if line.lstrip().startswith("#")
    ]
    rewritten_headings = {
        line.strip() for line in rewritten_markdown.splitlines() if line.lstrip().startswith("#")
    }
    if any(heading not in rewritten_headings for heading in original_headings):
        return False

    return len(rewritten_markdown) >= int(len(original_markdown) * 0.85)


def load_llm_config_from_env() -> dict[str, Any]:
    """为 Streamlit 页面提供默认 LLM 配置。"""
    load_dotenv()
    configured_model = os.getenv("MODEL_NAME", _DEFAULT_MODEL)
    return {
        "model": configured_model,
        "rewrite_model": os.getenv(
            "REWRITE_MODEL",
            _DEFAULT_REWRITE_MODEL if configured_model == _DEFAULT_MODEL else configured_model,
        ),
        "api_key": os.getenv("API_KEY", os.getenv("LLM_API_KEY", "")),
        "api_base": os.getenv("BASE_URL", _DEFAULT_API_BASE),
        "temperature": os.getenv("TEMPERATURE", _DEFAULT_TEMPERATURE),
        "max_tokens": os.getenv("MAX_TOKENS", _DEFAULT_MAX_TOKENS),
        "rewrite_max_tokens": os.getenv("REWRITE_MAX_TOKENS", _DEFAULT_REWRITE_MAX_TOKENS),
    }
