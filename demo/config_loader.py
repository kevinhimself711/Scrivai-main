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


def load_template_variants() -> dict[str, Any]:
    """加载模板变体配置。"""
    return _load_yaml(CONFIG_DIR / "template_variants.yaml")


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


def get_template_variants_meta(config: dict[str, Any]) -> list[dict[str, Any]]:
    """返回模板变体元数据列表。"""
    return list(config.get("variants", []))


def get_template_variant_map(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """按变体 id 建立索引。"""
    return {variant["id"]: variant for variant in get_template_variants_meta(config)}


def get_default_template_variant_id(config: dict[str, Any]) -> str:
    """返回默认模板变体 id。"""
    default_variant = str(config.get("default_variant", "")).strip()
    if default_variant:
        return default_variant

    variants = get_template_variants_meta(config)
    if not variants:
        raise ValueError("模板变体配置为空。")
    return str(variants[0]["id"])


def get_template_variant(
    config: dict[str, Any],
    variant_id: str | None = None,
) -> dict[str, Any]:
    """返回指定模板变体，不存在时抛出明确错误。"""
    variant_map = get_template_variant_map(config)
    selected_id = (variant_id or get_default_template_variant_id(config)).strip()
    if selected_id not in variant_map:
        raise ValueError(f"未知模板变体: {selected_id}")
    return variant_map[selected_id]


def resolve_chapter_template(chapter: dict[str, Any], variant_id: str) -> str:
    """解析章节在指定模板变体下对应的模板文件。"""
    templates = chapter.get("templates")
    if isinstance(templates, dict):
        template_name = str(templates.get(variant_id, "")).strip()
        if template_name:
            return template_name

    legacy_template = str(chapter.get("template", "")).strip()
    if legacy_template:
        return legacy_template
    raise ValueError(f"章节 {chapter['id']} 未配置模板文件。")
