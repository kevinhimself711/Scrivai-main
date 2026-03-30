"""Streamlit demo 入口。"""

from __future__ import annotations

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
        st.subheader("当前已启用章节")
        for chapter in enabled_chapters:
            st.write(f"- {chapter['title']}")

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
        st.markdown(generated_markdown)
        st.download_button(
            label="下载 Markdown",
            data=generated_markdown,
            file_name=build_output_filename(generated_variant_id),
            mime="text/markdown",
        )


if __name__ == "__main__":
    main()
