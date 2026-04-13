"""Streamlit demo 入口。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from demo.config_loader import (
    get_default_template_variant_id,
    get_enabled_chapters,
    get_template_variant,
    get_template_variants_meta,
    load_chapter_registry,
    load_field_schema,
    load_template_variants,
)
from demo.generator import (
    build_initial_demo_inputs,
    build_output_filename,
    generate_demo_markdown,
    load_llm_config_from_env,
)
from demo.image_manager import render_image_upload_section
from demo.word_exporter import markdown_to_docx


_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
_HISTORY_LIMIT = 5


def _parse_headings(markdown: str) -> list[dict]:
    """提取 Markdown 标题，附带稳定锚点 ID。"""
    headings: list[dict] = []
    for line in markdown.splitlines():
        match = _HEADING_PATTERN.match(line)
        if not match:
            continue
        level = len(match.group(1))
        text = match.group(2).strip()
        headings.append(
            {
                "level": level,
                "text": text,
                "anchor": f"scrivai-h{len(headings)}",
            }
        )
    return headings


def _inject_anchors(markdown: str, headings: list[dict]) -> str:
    """在每个标题前注入隐藏锚点，供侧边栏目录跳转。"""
    if not headings:
        return markdown
    lines = markdown.splitlines()
    out: list[str] = []
    heading_idx = 0
    for line in lines:
        if _HEADING_PATTERN.match(line) and heading_idx < len(headings):
            out.append(f'<a id="{headings[heading_idx]["anchor"]}"></a>')
            out.append("")
            heading_idx += 1
        out.append(line)
    return "\n".join(out)


def _render_sidebar_toc(headings: list[dict]) -> None:
    """在侧边栏渲染可点击的目录导航。"""
    if not headings:
        st.caption("（未解析到标题）")
        return
    min_level = min(h["level"] for h in headings)
    lines: list[str] = []
    for heading in headings:
        indent = "  " * (heading["level"] - min_level)
        lines.append(f"{indent}- [{heading['text']}](#{heading['anchor']})")
    st.markdown("\n".join(lines))


def _append_history(
    *,
    markdown_text: str,
    variant: dict,
    image_count: int,
) -> None:
    """把一次成功生成的快照追加到会话历史。"""
    history = st.session_state.setdefault("generation_history", [])
    history.insert(
        0,
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "variant_id": variant["id"],
            "variant_label": variant["label"],
            "style_title": variant["style_title"],
            "char_count": len(markdown_text),
            "image_count": image_count,
            "markdown": markdown_text,
        },
    )
    del history[_HISTORY_LIMIT:]


def _init_field_defaults(default_variant_id: str) -> None:
    form_defaults, table_defaults = build_initial_demo_inputs()

    for field_id, value in form_defaults.items():
        st.session_state.setdefault(f"field_{field_id}", value)
    for field_id, value in table_defaults.items():
        st.session_state.setdefault(f"field_{field_id}", value)

    st.session_state.setdefault("selected_template_variant", default_variant_id)


def _render_field(field: dict) -> None:
    key = f"field_{field['id']}"
    field_type = field.get("type", "text")
    help_text = field.get("help")

    if field_type == "textarea":
        st.text_area(field["label"], key=key, help=help_text, height=140)
        return

    if field_type == "markdown_table":
        st.text_area(
            field["label"],
            key=key,
            help=help_text,
            height=int(field.get("height", 320)),
        )
        return

    st.text_input(field["label"], key=key, help=help_text)


def _render_template_selector(variants: list[dict]) -> dict:
    st.subheader("模板选择")
    st.caption("三套模板共用同一套表单和表格，第 3 章始终只填空不改写；其余章节在保留当前模板风格前提下融合客制化要求。")

    columns = st.columns(len(variants))
    selected_id = st.session_state["selected_template_variant"]

    for column, variant in zip(columns, variants, strict=True):
        is_selected = selected_id == variant["id"]
        with column:
            with st.container(border=True):
                st.markdown(
                    f"### {variant['label']}\n"
                    f"**{variant['style_title']}**\n\n"
                    f"{variant['scenario']}\n\n"
                    f"风格说明：{variant['style_summary']}\n\n"
                    f"篇幅倾向：{variant['length_bias']}\n\n"
                    "改写规则：第 3 章只填空不改写，其他章节按需融合客制化要求。"
                )
                button_label = "当前已选" if is_selected else f"切换到{variant['label']}"
                if st.button(button_label, key=f"select_template_{variant['id']}", use_container_width=True):
                    st.session_state["selected_template_variant"] = variant["id"]
                    selected_id = variant["id"]

    return get_template_variant(load_template_variants(), selected_id)


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="线路工程施工方案 Demo", layout="wide")

    schema = load_field_schema()
    registry = load_chapter_registry()
    template_variant_config = load_template_variants()
    variants = get_template_variants_meta(template_variant_config)
    default_variant_id = get_default_template_variant_id(template_variant_config)
    enabled_chapters = get_enabled_chapters(registry)
    _init_field_defaults(default_variant_id)

    st.title("线路工程施工方案 Demo")
    st.caption("当前 Demo 已启用封面、审批页、目录和第 1 至第 8 章，并支持在统一表单下切换模板 A/B/C。")

    demo_type = st.selectbox("工程类型", ["线路工程"], index=0)
    st.info(f"当前工程类型：{demo_type}")

    selected_variant = _render_template_selector(variants)

    st.divider()
    render_image_upload_section()
    st.divider()

    with st.sidebar:
        st.subheader("当前模板")
        st.write(f"**{selected_variant['label']}｜{selected_variant['style_title']}**")
        st.caption(selected_variant["scenario"])
        st.write(f"篇幅倾向：{selected_variant['length_bias']}")

        st.divider()
        st.subheader("LLM 配置")
        env_defaults = load_llm_config_from_env()
        model = st.text_input("MODEL_NAME", value=env_defaults["model"])
        rewrite_model = st.text_input("REWRITE_MODEL", value=env_defaults["rewrite_model"])
        api_key = st.text_input("API_KEY", value=env_defaults["api_key"], type="password")
        api_base = st.text_input("BASE_URL", value=env_defaults["api_base"])
        temperature = st.text_input("temperature", value=str(env_defaults["temperature"]))
        max_tokens = st.text_input("max_tokens", value=str(env_defaults["max_tokens"]))
        rewrite_max_tokens = st.text_input(
            "rewrite_max_tokens",
            value=str(env_defaults["rewrite_max_tokens"]),
        )
        rewrite_chapter_limit = st.text_input(
            "rewrite_chapter_limit",
            value=str(env_defaults["rewrite_chapter_limit"]),
        )
        rewrite_concurrency = st.text_input(
            "rewrite_concurrency",
            value=str(env_defaults["rewrite_concurrency"]),
        )

        st.divider()
        sidebar_markdown = st.session_state.get("generated_markdown", "")
        if sidebar_markdown:
            st.subheader("文档目录")
            st.caption("点击跳转到对应章节")
            _render_sidebar_toc(_parse_headings(sidebar_markdown))
        else:
            st.subheader("当前已启用章节")
            st.caption("生成后此处会自动变成可点击的文档目录")
            for chapter in enabled_chapters:
                st.write(f"- {chapter['title']}")

        st.divider()
        st.subheader("生成历史")
        history = st.session_state.get("generation_history", [])
        if not history:
            st.caption("暂无历史记录，点击生成后会自动保存最近 5 次结果。")
        else:
            st.caption(f"最近 {len(history)} 次生成（最多保留 {_HISTORY_LIMIT} 条）")
            for idx, entry in enumerate(history):
                with st.container(border=True):
                    st.markdown(
                        f"**{entry['timestamp']}**  \n"
                        f"{entry['variant_label']}｜{entry['style_title']}  \n"
                        f"字数：{entry['char_count']}｜图片：{entry['image_count']} 张"
                    )
                    col_view, col_download = st.columns(2)
                    with col_view:
                        if st.button("查看", key=f"history_view_{idx}", use_container_width=True):
                            st.session_state["generated_markdown"] = entry["markdown"]
                            st.session_state["generated_template_variant"] = entry["variant_id"]
                            st.rerun()
                    with col_download:
                        st.download_button(
                            label="下载 MD",
                            data=entry["markdown"],
                            file_name=build_output_filename(entry["variant_id"]),
                            mime="text/markdown",
                            key=f"history_download_{idx}",
                            use_container_width=True,
                        )

    with st.form("line_project_demo_form"):
        st.subheader("关键数据表单")
        for group in schema.get("groups", []):
            with st.expander(group["title"], expanded=group.get("expanded", True)):
                if group.get("description"):
                    st.caption(group["description"])
                for field in group.get("fields", []):
                    _render_field(field)

        custom_requirements = st.text_area(
            "客制化要求",
            help=(
                "如填写，将调用在线 LLM 对相关章节做受控改写。"
                "系统会根据章节标签和客制化关键词自动选择相关章节，并在保留当前模板风格前提下并行改写。"
            ),
            height=180,
        )
        submitted = st.form_submit_button("生成施工方案")

    if submitted:
        form_data: dict[str, str] = {}
        editable_tables: dict[str, str] = {}

        for group in schema.get("groups", []):
            for field in group.get("fields", []):
                value = st.session_state.get(f"field_{field['id']}", "")
                if field.get("type") == "markdown_table":
                    editable_tables[field["id"]] = value
                else:
                    form_data[field["id"]] = value

        llm_config = {
            "model": model.strip(),
            "rewrite_model": rewrite_model.strip(),
            "api_key": api_key.strip(),
            "api_base": api_base.strip(),
            "temperature": temperature.strip(),
            "max_tokens": max_tokens.strip(),
            "rewrite_max_tokens": rewrite_max_tokens.strip(),
            "rewrite_chapter_limit": rewrite_chapter_limit.strip(),
            "rewrite_concurrency": rewrite_concurrency.strip(),
        }

        try:
            markdown_text = generate_demo_markdown(
                form_data=form_data,
                editable_tables=editable_tables,
                enabled_chapters=[chapter["id"] for chapter in enabled_chapters],
                custom_requirements=custom_requirements,
                llm_config=llm_config,
                template_variant=selected_variant["id"],
            )
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
        else:
            st.session_state["generated_markdown"] = markdown_text
            st.session_state["generated_template_variant"] = selected_variant["id"]
            _append_history(
                markdown_text=markdown_text,
                variant=selected_variant,
                image_count=len(st.session_state.get("uploaded_images", [])),
            )
            st.success("施工方案生成完成。")

    generated_markdown = st.session_state.get("generated_markdown", "")
    generated_variant_id = st.session_state.get(
        "generated_template_variant",
        st.session_state["selected_template_variant"],
    )
    generated_variant = get_template_variant(template_variant_config, generated_variant_id)
    if generated_markdown:
        st.subheader("Markdown 预览")
        st.caption(
            f"当前预览：{generated_variant['label']}｜{generated_variant['style_title']}｜{generated_variant['length_bias']}"
        )

        md_filename = build_output_filename(generated_variant_id)
        docx_filename = Path(md_filename).with_suffix(".docx").name
        try:
            docx_bytes = markdown_to_docx(
                generated_markdown,
                title=f"{generated_variant['label']}｜{generated_variant['style_title']}",
            )
            docx_error: str | None = None
        except Exception as exc:  # noqa: BLE001
            docx_bytes = b""
            docx_error = str(exc)

        col_md, col_docx = st.columns(2)
        with col_md:
            st.download_button(
                label="下载 Markdown",
                data=generated_markdown,
                file_name=md_filename,
                mime="text/markdown",
                use_container_width=True,
            )
        with col_docx:
            if docx_error:
                st.error(f"Word 生成失败：{docx_error}")
            else:
                st.download_button(
                    label="下载 Word (.docx)",
                    data=docx_bytes,
                    file_name=docx_filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

        headings = _parse_headings(generated_markdown)
        st.markdown(
            _inject_anchors(generated_markdown, headings),
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
