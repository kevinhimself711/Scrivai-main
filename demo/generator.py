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
    get_default_template_variant_id,
    get_enabled_chapters,
    get_field_map,
    get_template_variant,
    get_template_variants_meta,
    iter_field_defs,
    load_chapter_registry,
    load_field_schema,
    load_template_variants,
    resolve_chapter_template,
    resolve_repo_path,
    resolve_template_path,
)
from demo.source_data import render_block_ref

_CODE_FENCE_PATTERN = re.compile(r"^\s*```(?:markdown)?\s*|\s*```\s*$", re.MULTILINE)
_PERCENT_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*%?\s*$")
_STYLE_TOKENS = {
    "文风",
    "专业",
    "正式",
    "国网",
    "南网",
    "口径",
    "结构",
    "章节",
    "保持",
    "融入",
    "风格",
    "语气",
}
_DEFAULT_FALLBACK_REWRITE_IDS = ("chapter_1", "chapter_2")
_DEFAULT_MODEL = "qwen3-max"
_DEFAULT_REWRITE_MODEL = _DEFAULT_MODEL
_DEFAULT_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_TEMPERATURE = "0.2"
_DEFAULT_MAX_TOKENS = "4096"
_DEFAULT_REWRITE_MAX_TOKENS = "3072"
_DEFAULT_REWRITE_CHAPTER_LIMIT = "4"
_DEFAULT_REWRITE_CONCURRENCY = "3"


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


def build_output_filename(template_variant: str) -> str:
    """构造包含模板标识的下载文件名。"""
    return f"line_project_demo_template_{template_variant}.md"


def generate_demo_markdown(
    form_data: dict[str, Any],
    editable_tables: dict[str, str],
    enabled_chapters: list[str] | None = None,
    custom_requirements: str = "",
    llm_config: dict[str, Any] | None = None,
    template_variant: str | None = None,
) -> str:
    """生成 demo Markdown 文档。"""
    field_schema = load_field_schema()
    chapter_registry = load_chapter_registry()
    template_variant_config = load_template_variants()
    selected_variant = get_template_variant(template_variant_config, template_variant)
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
        "template_variant": selected_variant["id"],
        "template_variant_label": selected_variant["label"],
        "template_variant_style_title": selected_variant["style_title"],
        "template_variant_style_summary": selected_variant["style_summary"],
    }

    fragments: list[dict[str, Any]] = []
    for chapter in chapters:
        template_name = resolve_chapter_template(chapter, selected_variant["id"])
        context = dict(base_context)
        context["source_blocks"] = _resolve_source_blocks(chapter)
        fragments.append(
            {
                "id": chapter["id"],
                "title": chapter["title"],
                "markdown": _render_fragment(template_name, context),
                "rewrite_enabled": bool(chapter.get("rewrite_enabled", False)),
                "rewrite_topics": chapter.get("rewrite_topics", []),
            }
        )

    if custom_requirements.strip():
        fragments = _apply_custom_requirements_to_fragments(
            fragments=fragments,
            custom_requirements=custom_requirements,
            llm_config=llm_config or {},
            template_variant_meta=selected_variant,
        )

    return "\n\n".join(
        fragment["markdown"].strip() for fragment in fragments if fragment["markdown"].strip()
    ).strip()


def validate_template_context(
    schema: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
    template_variants: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """检查模板变量是否都能在生成上下文中找到。"""
    schema = schema or load_field_schema()
    registry = registry or load_chapter_registry()
    template_variants = template_variants or load_template_variants()

    env = jinja2.Environment()
    known_vars = {
        *get_field_map(schema).keys(),
        "toc_entries",
        "terrain_total_ratio",
        "source_blocks",
        "template_variant",
        "template_variant_label",
        "template_variant_style_title",
        "template_variant_style_summary",
    }

    missing: dict[str, list[str]] = {}
    for chapter in registry.get("chapters", []):
        for variant in get_template_variants_meta(template_variants):
            variant_id = variant["id"]
            template_source = resolve_template_path(
                resolve_chapter_template(chapter, variant_id)
            ).read_text(encoding="utf-8")
            parsed = env.parse(template_source)
            undeclared = sorted(meta.find_undeclared_variables(parsed) - known_vars)
            if undeclared:
                missing[f"{chapter['id']}:{variant_id}"] = undeclared
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
    fragments: list[dict[str, Any]],
    custom_requirements: str,
    llm_config: dict[str, Any],
    template_variant_meta: dict[str, Any],
) -> list[dict[str, Any]]:
    target_indexes = _select_rewrite_target_indexes(fragments, custom_requirements, llm_config)
    if not target_indexes:
        return fragments

    def rewrite(index: int) -> tuple[int, str]:
        fragment = fragments[index]
        client = _build_llm_client(llm_config, purpose="rewrite")
        rewritten = _apply_custom_requirements(
            llm=client,
            chapter_title=fragment["title"],
            chapter_markdown=fragment["markdown"],
            custom_requirements=custom_requirements,
            template_variant_meta=template_variant_meta,
        )
        return index, rewritten

    rewritten_map: dict[int, str] = {}
    concurrency = min(len(target_indexes), _resolve_rewrite_concurrency(llm_config))
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for index, rewritten in executor.map(rewrite, target_indexes):
            rewritten_map[index] = rewritten

    merged_fragments = [dict(fragment) for fragment in fragments]
    for index, rewritten in rewritten_map.items():
        merged_fragments[index]["markdown"] = rewritten
    return merged_fragments


def _select_rewrite_target_indexes(
    fragments: list[dict[str, Any]],
    custom_requirements: str,
    llm_config: dict[str, Any],
) -> list[int]:
    requirement_text = custom_requirements.strip()
    limit = _resolve_rewrite_chapter_limit(llm_config)

    scored_targets: list[tuple[int, int]] = []
    for index, fragment in enumerate(fragments):
        if not fragment.get("rewrite_enabled", False):
            continue
        score = _score_fragment_for_rewrite(fragment, requirement_text)
        if score > 0:
            scored_targets.append((index, score))

    if scored_targets:
        scored_targets.sort(key=lambda item: (-item[1], item[0]))
        selected = [index for index, _ in scored_targets[:limit]]
        if _contains_style_signal(requirement_text):
            selected = _append_default_rewrite_indexes(fragments, selected, limit)
        return selected

    fallback_indexes = [
        index
        for index, fragment in enumerate(fragments)
        if fragment["id"] in _DEFAULT_FALLBACK_REWRITE_IDS and fragment.get("rewrite_enabled", False)
    ]
    if fallback_indexes:
        return fallback_indexes[:limit]

    return [
        index
        for index, fragment in enumerate(fragments)
        if fragment.get("rewrite_enabled", False)
    ][:limit]


def _append_default_rewrite_indexes(
    fragments: list[dict[str, Any]],
    selected_indexes: list[int],
    limit: int,
) -> list[int]:
    merged = list(selected_indexes)
    for chapter_id in _DEFAULT_FALLBACK_REWRITE_IDS:
        if len(merged) >= limit:
            break
        fallback_index = next(
            (
                index
                for index, fragment in enumerate(fragments)
                if fragment["id"] == chapter_id and fragment.get("rewrite_enabled", False)
            ),
            None,
        )
        if fallback_index is not None and fallback_index not in merged:
            merged.append(fallback_index)
    return merged


def _score_fragment_for_rewrite(fragment: dict[str, Any], custom_requirements: str) -> int:
    score = 0
    requirement_text = custom_requirements.casefold()
    for topic in fragment.get("rewrite_topics", []):
        normalized_topic = str(topic).strip().casefold()
        if normalized_topic and normalized_topic in requirement_text:
            score += max(2, len(normalized_topic))
    return score


def _contains_style_signal(custom_requirements: str) -> bool:
    normalized = custom_requirements.casefold()
    return any(token.casefold() in normalized for token in _STYLE_TOKENS)


def _resolve_rewrite_chapter_limit(llm_config: dict[str, Any]) -> int:
    raw_value = str(
        llm_config.get("rewrite_chapter_limit", _DEFAULT_REWRITE_CHAPTER_LIMIT)
    ).strip() or _DEFAULT_REWRITE_CHAPTER_LIMIT
    return max(1, int(raw_value))


def _resolve_rewrite_concurrency(llm_config: dict[str, Any]) -> int:
    raw_value = str(
        llm_config.get("rewrite_concurrency", _DEFAULT_REWRITE_CONCURRENCY)
    ).strip() or _DEFAULT_REWRITE_CONCURRENCY
    return max(1, int(raw_value))


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
    raw_value = str(llm_config.get(key, llm_config.get("max_tokens", default_value))).strip()
    return int(raw_value or default_value)


def _apply_custom_requirements(
    llm: LLMClient,
    chapter_title: str,
    chapter_markdown: str,
    custom_requirements: str,
    template_variant_meta: dict[str, Any],
) -> str:
    prompt = """
你是电力线路工程施工方案编辑助手。请只改写当前章节，把与当前章节直接相关的客制化要求自然融入现有表述。

当前选中的模板风格信息如下：
- 模板名称：{{ template_variant_label }}
- 风格标题：{{ template_variant_style_title }}
- 风格说明：{{ template_variant_style_summary }}
- 改写保持要求：{{ template_variant_rewrite_style_prompt }}

绝对要求：
1. 只输出当前章节，不新增、删除、合并章节。
2. 必须完整保留现有 Markdown 标题层级、表格结构、工程数据和编号顺序，不得省略任何原有小节、列表项或表格。
3. 只处理与当前章节直接相关的要求；如果客户要求与本章节关系不大，只做最小必要融合。
4. 改写时必须保留当前所选模板的语气、展开方式、组织结构和写作风格，不得把 {{ template_variant_label }} 改写成其他模板口气。
5. 若客制化要求包含明确主题词，例如“雨季施工”“环保水保”“山区运输”“边坡稳定”“夜间施工”“质量控制”“应急处置”，请在相关段落中明确体现这些主题词或其正式同义表达，不要只写成笼统概括。
6. 不输出解释、前后缀、代码块或“修改说明”。

当前章节标题：{{ chapter_title }}

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
            "template_variant_label": template_variant_meta["label"],
            "template_variant_style_title": template_variant_meta["style_title"],
            "template_variant_style_summary": template_variant_meta["style_summary"],
            "template_variant_rewrite_style_prompt": template_variant_meta["rewrite_style_prompt"],
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
        "rewrite_chapter_limit": os.getenv(
            "REWRITE_CHAPTER_LIMIT",
            _DEFAULT_REWRITE_CHAPTER_LIMIT,
        ),
        "rewrite_concurrency": os.getenv(
            "REWRITE_CONCURRENCY",
            _DEFAULT_REWRITE_CONCURRENCY,
        ),
        "template_variant": os.getenv(
            "TEMPLATE_VARIANT",
            get_default_template_variant_id(load_template_variants()),
        ),
    }
