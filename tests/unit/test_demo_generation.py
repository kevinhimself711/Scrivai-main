"""线路工程 demo 生成测试。"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

from demo.generator import (
    build_initial_demo_inputs,
    build_output_filename,
    generate_demo_markdown,
    validate_template_context,
)


def _extract_chapter(markdown: str, chapter_number: int, next_chapter_number: int | None = None) -> str:
    start_marker = f"## {chapter_number} "
    start = markdown.index(start_marker)
    if next_chapter_number is None:
        return markdown[start:].strip()
    end_marker = f"## {next_chapter_number} "
    end = markdown.index(end_marker, start)
    return markdown[start:end].strip()


def test_template_context_complete() -> None:
    """A/B/C 三套模板的变量都应能在上下文中解析。"""
    assert validate_template_context() == {}


@pytest.mark.parametrize(
    ("variant", "unique_phrase"),
    [
        ("a", "工程要求质量标准：满足国家施工验收规范，优质工程标准，达标投产。"),
        ("b", "便于项目管理、专业会审和常规内部流转使用。"),
        ("c", "可直接用于施工交底、作业准备和现场执行检查。"),
    ],
)
def test_generate_demo_markdown_variants_no_placeholders(
    variant: str,
    unique_phrase: str,
) -> None:
    """同一套输入生成 A/B/C 时都应完整且无占位残留。"""
    form_data, editable_tables = build_initial_demo_inputs()

    markdown = generate_demo_markdown(
        form_data,
        editable_tables,
        template_variant=variant,
    )

    assert re.search(r"X{3,}", markdown) is None
    assert "XXX" not in markdown
    assert "../Images/" not in markdown
    for chapter_number in range(1, 9):
        assert f"## {chapter_number} " in markdown
    assert unique_phrase in markdown


def test_generate_demo_markdown_variants_are_different() -> None:
    """A/B/C 三套模板在相同输入下应生成不同正文。"""
    form_data, editable_tables = build_initial_demo_inputs()

    output_a = generate_demo_markdown(form_data, editable_tables, template_variant="a")
    output_b = generate_demo_markdown(form_data, editable_tables, template_variant="b")
    output_c = generate_demo_markdown(form_data, editable_tables, template_variant="c")

    assert output_a != output_b
    assert output_b != output_c
    assert output_a != output_c
    assert "兼顾技术会审与现场执行两类使用场景。" in output_b
    assert "每道工序均应落实作业确认点、检查记录和转序条件。" in output_c


def test_generate_demo_markdown_uses_edited_tables() -> None:
    """编辑后的表格内容应直接反映在生成结果中。"""
    form_data, editable_tables = build_initial_demo_inputs()
    editable_tables["foundation_technical_parameters_table"] = (
        "| 杆塔号 | 说明 |\n"
        "| --- | --- |\n"
        "| TEST-001 | 自定义表格 |"
    )
    editable_tables["construction_staffing_table"] = (
        "| 序号 | 工作岗位 | 技工 | 普工 | 合计 |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| 1 | 试验班组 | 2 | 4 | 6 |"
    )
    editable_tables["emergency_contact_table"] = (
        "| 序号 | 姓名 | 单位 | 职务 | 联系电话 |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| 1 | 张三 | 项目经理部 | 现场应急负责人 | 13800000000 |"
    )

    markdown = generate_demo_markdown(form_data, editable_tables, template_variant="b")

    assert "TEST-001" in markdown
    assert "自定义表格" in markdown
    assert "试验班组" in markdown
    assert "张三" in markdown
    assert "13800000000" in markdown


def test_generate_demo_markdown_invalid_template_variant() -> None:
    """未知模板变体应返回明确错误。"""
    form_data, editable_tables = build_initial_demo_inputs()

    with pytest.raises(ValueError, match="未知模板变体"):
        generate_demo_markdown(form_data, editable_tables, template_variant="z")


def test_build_output_filename_contains_template_variant() -> None:
    assert build_output_filename("a") == "line_project_demo_template_a.md"
    assert build_output_filename("c") == "line_project_demo_template_c.md"


def test_generate_demo_markdown_custom_requirements_require_llm_config() -> None:
    """填写客制化要求后必须提供 LLM 配置。"""
    form_data, editable_tables = build_initial_demo_inputs()

    with pytest.raises(ValueError, match="LLM"):
        generate_demo_markdown(
            form_data,
            editable_tables,
            custom_requirements="请增强雨季施工与环保要求。",
            llm_config={},
            template_variant="a",
        )


@patch("demo.generator.LLMClient")
def test_generate_demo_markdown_general_custom_requirements_preserve_variant_style(
    mock_llm_cls,
) -> None:
    """泛化要求应回退到第 1、2 章并带入当前模板风格信息。"""
    form_data, editable_tables = build_initial_demo_inputs()
    original_markdown = generate_demo_markdown(form_data, editable_tables, template_variant="b")
    chapter_1 = _extract_chapter(original_markdown, 1, 2).replace(
        "## 1 编制说明",
        "## 1 编制说明\n\n补充均衡通用风格要求。",
        1,
    )
    chapter_2 = _extract_chapter(original_markdown, 2, 3).replace(
        "## 2 工程概况",
        "## 2 工程概况\n\n补充阅读更顺的组织说明。",
        1,
    )

    mock_client = MagicMock()
    mapping = {
        "1 编制说明": chapter_1,
        "2 工程概况": chapter_2,
    }
    mock_client.chat_with_template.side_effect = lambda _template, variables: mapping[
        variables["chapter_title"]
    ]
    mock_llm_cls.return_value = mock_client

    markdown = generate_demo_markdown(
        form_data,
        editable_tables,
        custom_requirements="请保持全文文风正式专业，但更便于内部会审和常规流转，不改变章节结构。",
        llm_config={"model": "demo-model", "api_key": "secret-key"},
        template_variant="b",
    )

    assert "补充均衡通用风格要求。" in markdown
    assert "补充阅读更顺的组织说明。" in markdown
    assert mock_llm_cls.call_count == 2
    assert mock_client.chat_with_template.call_count == 2
    first_prompt = mock_client.chat_with_template.call_args_list[0].args[0]
    first_variables = mock_client.chat_with_template.call_args_list[0].args[1]
    assert "当前选中的模板风格信息如下" in first_prompt
    assert first_variables["template_variant_label"] == "模板B"
    assert first_variables["template_variant_style_title"] == "均衡通用"
    assert "均衡的技术文风" in first_variables["template_variant_rewrite_style_prompt"]


@patch("demo.generator.LLMClient")
def test_generate_demo_markdown_routes_custom_requirements_to_topical_chapters(mock_llm_cls) -> None:
    """主题型客制化要求应路由到相关章节。"""
    form_data, editable_tables = build_initial_demo_inputs()
    original_markdown = generate_demo_markdown(form_data, editable_tables, template_variant="c")
    chapter_5 = _extract_chapter(original_markdown, 5, 6).replace(
        "## 5 安全管理措施",
        "## 5 安全管理措施\n\n补充安全文明施工联动要求。",
        1,
    )
    chapter_7 = _extract_chapter(original_markdown, 7, 8).replace(
        "## 7 应急处置方案",
        "## 7 应急处置方案\n\n强化先期响应和到场分工要求。",
        1,
    )
    chapter_8 = _extract_chapter(original_markdown, 8, None).replace(
        "## 8 环保水保措施",
        "## 8 环保水保措施\n\n进一步强调环保水保过程留痕。",
        1,
    )

    mock_client = MagicMock()
    mapping = {
        "5 安全管理措施": chapter_5,
        "7 应急处置方案": chapter_7,
        "8 环保水保措施": chapter_8,
    }
    mock_client.chat_with_template.side_effect = lambda _template, variables: mapping[
        variables["chapter_title"]
    ]
    mock_llm_cls.return_value = mock_client

    markdown = generate_demo_markdown(
        form_data,
        editable_tables,
        custom_requirements="请强化环保水保、文明施工和应急处置要求。",
        llm_config={
            "model": "demo-model",
            "api_key": "secret-key",
            "rewrite_chapter_limit": "3",
        },
        template_variant="c",
    )

    assert "补充安全文明施工联动要求。" in markdown
    assert "强化先期响应和到场分工要求。" in markdown
    assert "进一步强调环保水保过程留痕。" in markdown
    assert mock_llm_cls.call_count == 3
    assert mock_client.chat_with_template.call_count == 3
    for call in mock_client.chat_with_template.call_args_list:
        assert call.args[1]["template_variant_label"] == "模板C"


@pytest.mark.parametrize("variant", ["a", "b", "c"])
@patch("demo.generator.LLMClient")
def test_generate_demo_markdown_chapter_3_stays_template_only(mock_llm_cls, variant: str) -> None:
    """第 3 章在所有模板中都应保持纯模板填参，不参与改写。"""
    form_data, editable_tables = build_initial_demo_inputs()
    original_markdown = generate_demo_markdown(form_data, editable_tables, template_variant=variant)
    chapter_1 = _extract_chapter(original_markdown, 1, 2).replace(
        "## 1 ",
        "## 1 补充风格要求\n\n",
        1,
    )

    mock_client = MagicMock()
    mock_client.chat_with_template.return_value = chapter_1
    mock_llm_cls.return_value = mock_client

    markdown = generate_demo_markdown(
        form_data,
        editable_tables,
        custom_requirements="请加强施工技术措施中的雨季施工和机械成孔说明，但不要改变章节结构。",
        llm_config={"model": "demo-model", "api_key": "secret-key"},
        template_variant=variant,
    )

    chapter_3 = _extract_chapter(markdown, 3, 4)
    called_titles = [
        call.args[1]["chapter_title"] for call in mock_client.chat_with_template.call_args_list
    ]
    assert "旋挖钻机" in chapter_3 or "机械成孔" in chapter_3
    assert "3 施工技术措施" not in called_titles


@patch("demo.generator.LLMClient")
def test_generate_demo_markdown_invalid_rewrite_falls_back_to_original(mock_llm_cls) -> None:
    """若 LLM 改写破坏章节结构，应自动回退原章节内容。"""
    form_data, editable_tables = build_initial_demo_inputs()
    original_markdown = generate_demo_markdown(form_data, editable_tables, template_variant="c")
    chapter_1 = _extract_chapter(original_markdown, 1, 2).replace(
        "## 1 编制说明",
        "## 1 编制说明\n\n补充执行导向风格要求。",
        1,
    )

    mock_client = MagicMock()
    mapping = {
        "1 编制说明": chapter_1,
        "2 工程概况": "```markdown\n## 2 工程概况\n仅保留一个小节\n```",
    }
    mock_client.chat_with_template.side_effect = lambda _template, variables: mapping[
        variables["chapter_title"]
    ]
    mock_llm_cls.return_value = mock_client

    markdown = generate_demo_markdown(
        form_data,
        editable_tables,
        custom_requirements="请保持全文文风正式专业，不改变章节结构。",
        llm_config={"model": "demo-model", "api_key": "secret-key"},
        template_variant="c",
    )

    assert "补充执行导向风格要求。" in markdown
    assert "#### 2.6.4" in markdown
    assert "仅保留一个小节" not in markdown
    assert mock_client.chat_with_template.call_count == 2
