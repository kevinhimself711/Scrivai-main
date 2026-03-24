"""线路工程 demo 生成测试。"""

import re
from unittest.mock import MagicMock, patch

import pytest

from demo.generator import build_initial_demo_inputs, generate_demo_markdown, validate_template_context


def _extract_chapter(markdown: str, chapter_number: int, next_chapter_number: int | None = None) -> str:
    start_marker = f"## {chapter_number} "
    start = markdown.index(start_marker)
    if next_chapter_number is None:
        return markdown[start:].strip()
    end_marker = f"## {next_chapter_number} "
    end = markdown.index(end_marker, start)
    return markdown[start:end].strip()


def test_template_context_complete() -> None:
    """所有模板变量都应能在生成上下文中解析。"""
    assert validate_template_context() == {}


def test_generate_demo_markdown_default_no_placeholders() -> None:
    """默认输入应生成无占位残留的 1-5 章文档。"""
    form_data, editable_tables = build_initial_demo_inputs()

    markdown = generate_demo_markdown(form_data, editable_tables)

    assert re.search(r"X{3,}", markdown) is None
    assert "../Images/" not in markdown
    assert "## 1 编制说明" in markdown
    assert "## 2 工程概况" in markdown
    assert "## 3 施工技术措施" in markdown
    assert "## 4 施工组织措施" in markdown
    assert "## 5 安全管理措施" in markdown
    assert "2.6.4 箱筋安装要求" in markdown
    assert "3.2.13 排水沟施工" in markdown
    assert "4.4 工期计划" in markdown
    assert "5.4.2 环保水保要求" in markdown


def test_generate_demo_markdown_uses_edited_table() -> None:
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

    markdown = generate_demo_markdown(form_data, editable_tables)

    assert "TEST-001" in markdown
    assert "自定义表格" in markdown
    assert "试验班组" in markdown


def test_generate_demo_markdown_custom_requirements_require_llm_config() -> None:
    """填写客制化要求后必须提供 LLM 配置。"""
    form_data, editable_tables = build_initial_demo_inputs()

    with pytest.raises(ValueError, match="LLM"):
        generate_demo_markdown(
            form_data,
            editable_tables,
            custom_requirements="请增强雨季施工与环保要求。",
            llm_config={},
        )


@patch("demo.generator.LLMClient")
def test_generate_demo_markdown_custom_requirements_calls_llm(mock_llm_cls) -> None:
    """客制化要求应触发对第1章和第2章的受控 LLM 改写。"""
    form_data, editable_tables = build_initial_demo_inputs()
    original_markdown = generate_demo_markdown(form_data, editable_tables)
    chapter_1 = _extract_chapter(original_markdown, 1, 2).replace(
        "特编制本施工方案。",
        "特编制本施工方案，并补充雨季施工和环保水保方面的控制要求。",
        1,
    )
    chapter_2 = _extract_chapter(original_markdown, 2, 3).replace(
        "本工程总体交通条件良好。",
        "本工程总体交通条件良好，并应同步关注山区运输组织与雨季通行风险。",
        1,
    )
    mock_client_1 = MagicMock()
    mock_client_1.chat_with_template.return_value = chapter_1
    mock_client_2 = MagicMock()
    mock_client_2.chat_with_template.return_value = chapter_2
    mock_llm_cls.side_effect = [mock_client_1, mock_client_2]

    markdown = generate_demo_markdown(
        form_data,
        editable_tables,
        custom_requirements="请强化雨季边坡防护和环保水保要求。",
        llm_config={"model": "demo-model", "api_key": "secret-key"},
    )

    assert "雨季施工和环保水保方面的控制要求" in markdown
    assert "山区运输组织与雨季通行风险" in markdown
    assert "## 3 施工技术措施" in markdown
    assert mock_llm_cls.call_count == 2
    assert mock_client_1.chat_with_template.call_count == 1
    assert mock_client_2.chat_with_template.call_count == 1


@patch("demo.generator.LLMClient")
def test_generate_demo_markdown_invalid_rewrite_falls_back_to_original(mock_llm_cls) -> None:
    """若 LLM 改写破坏章节结构，应自动回退原章节内容。"""
    form_data, editable_tables = build_initial_demo_inputs()
    original_markdown = generate_demo_markdown(form_data, editable_tables)
    chapter_1 = _extract_chapter(original_markdown, 1, 2).replace(
        "特编制本施工方案。",
        "特编制本施工方案，并补充雨季施工和环保水保方面的控制要求。",
        1,
    )

    mock_client_1 = MagicMock()
    mock_client_1.chat_with_template.return_value = chapter_1
    mock_client_2 = MagicMock()
    mock_client_2.chat_with_template.return_value = "```markdown\n## 2 工程概况\n仅保留一个小节\n```"
    mock_llm_cls.side_effect = [mock_client_1, mock_client_2]

    markdown = generate_demo_markdown(
        form_data,
        editable_tables,
        custom_requirements="请强化雨季边坡防护和环保水保要求。",
        llm_config={"model": "demo-model", "api_key": "secret-key"},
    )

    assert "雨季施工和环保水保方面的控制要求" in markdown
    assert "#### 2.6.4 箱筋安装要求" in markdown
    assert "仅保留一个小节" not in markdown
    assert len(markdown) >= len(original_markdown) - 1000
