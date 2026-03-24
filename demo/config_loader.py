"""Demo 配置加载工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PACKAGE_ROOT / "config"
TEMPLATES_DIR = PACKAGE_ROOT / "templates"
REPO_ROOT = PACKAGE_ROOT.parent


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"配置文件格式错误: {path}")
    return data


def load_field_schema() -> dict[str, Any]:
    """加载表单字段 schema。"""
    return _load_yaml(CONFIG_DIR / "fields.yaml")


def load_chapter_registry() -> dict[str, Any]:
    """加载章节清单配置。"""
    return _load_yaml(CONFIG_DIR / "chapters.yaml")


def resolve_template_path(relative_path: str) -> Path:
    """将模板相对路径解析为绝对路径。"""
    return TEMPLATES_DIR / relative_path


def resolve_repo_path(relative_path: str) -> Path:
    """将仓库内相对路径解析为绝对路径。"""
    return REPO_ROOT / relative_path


def iter_field_defs(schema: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """遍历所有字段定义。"""
    for group in schema.get("groups", []):
        for field in group.get("fields", []):
            yield field


def get_field_map(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """按字段 id 建立索引。"""
    return {field["id"]: field for field in iter_field_defs(schema)}


def get_enabled_chapters(
    registry: dict[str, Any],
    enabled_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """按配置顺序返回启用的章节。"""
    chapters = registry.get("chapters", [])
    if enabled_ids is None:
        return [chapter for chapter in chapters if chapter.get("enabled", True)]

    enabled_set = set(enabled_ids)
    return [chapter for chapter in chapters if chapter["id"] in enabled_set]


def get_chapter_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """按章节 id 建立索引。"""
    return {chapter["id"]: chapter for chapter in registry.get("chapters", [])}
