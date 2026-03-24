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
    """默认输入应生成无占位残留的 1-8 章文档。"""
    form_data, editable_tables = build_initial_demo_inputs()

    markdown = generate_demo_markdown(form_data, editable_tables)

    assert re.search(r"X{3,}", markdown) is None
    assert "XXX" not in markdown
    assert "../Images/" not in markdown
    assert "## 1 编制说明" in markdown
    assert "## 2 工程概况" in markdown
    assert "## 3 施工技术措施" in markdown
    assert "## 4 施工组织措施" in markdown
    assert "## 5 安全管理措施" in markdown
    assert "## 6 质量控制措施" in markdown
    assert "## 7 应急处置方案" in markdown
    assert "## 8 环保水保措施" in markdown
    assert "2.6.4 箱筋安装要求" in markdown
    assert "3.2.13 排水沟施工" in markdown
    assert "4.4 工期计划" in markdown
    assert "5.4.2 环保水保要求" in markdown
    assert "6.5 标准工艺施工要求" in markdown
    assert "7.3.10 环境污染事件" in markdown
    assert "8.3 水土保持措施" in markdown


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
        "| 1 | 张三 | 项目经理 | 现场应急领导小组组长 | 13800000000 |"
    )

    markdown = generate_demo_markdown(form_data, editable_tables)

    assert "TEST-001" in markdown
    assert "自定义表格" in markdown
    assert "试验班组" in markdown
    assert "张三" in markdown
    assert "13800000000" in markdown


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
def test_generate_demo_markdown_general_custom_requirements_fallback_to_chapter_1_and_2(
    mock_llm_cls,
) -> None:
    """泛化要求应回退到第 1、2 章改写。"""
    form_data, editable_tables = build_initial_demo_inputs()
    original_markdown = generate_demo_markdown(form_data, editable_tables)
    chapter_1 = _extract_chapter(original_markdown, 1, 2).replace(
        "特编制本施工方案。",
        "特编制本施工方案，并补充总体风格与正式表述要求。",
        1,
    )
    chapter_2 = _extract_chapter(original_markdown, 2, 3).replace(
        "本工程总体交通条件良好。",
        "本工程总体交通条件良好，文稿表述同步保持正式、规范、专业口径。",
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
        custom_requirements="请保持全文文风正式专业，符合国网工程管理口径，不改变章节结构。",
        llm_config={"model": "demo-model", "api_key": "secret-key"},
    )

    assert "补充总体风格与正式表述要求" in markdown
    assert "正式、规范、专业口径" in markdown
    assert mock_llm_cls.call_count == 2
    assert mock_client.chat_with_template.call_count == 2


@patch("demo.generator.LLMClient")
def test_generate_demo_markdown_routes_custom_requirements_to_topical_chapters(mock_llm_cls) -> None:
    """主题型客制化要求应路由到相关章节。"""
    form_data, editable_tables = build_initial_demo_inputs()
    original_markdown = generate_demo_markdown(form_data, editable_tables)
    chapter_3 = _extract_chapter(original_markdown, 3, 4).replace(
        "## 3 施工技术措施",
        "## 3 施工技术措施\n\n重点落实雨季施工组织要求。",
        1,
    )
    chapter_5 = _extract_chapter(original_markdown, 5, 6).replace(
        "## 5 安全管理措施",
        "## 5 安全管理措施\n\n补充环保水保专项管控要求。",
        1,
    )
    chapter_7 = _extract_chapter(original_markdown, 7, 8).replace(
        "## 7 应急处置方案",
        "## 7 应急处置方案\n\n强化应急处置响应链路。",
        1,
    )
    chapter_8 = _extract_chapter(original_markdown, 8, None).replace(
        "## 8 环保水保措施",
        "## 8 环保水保措施\n\n进一步强调环保水保过程留痕。",
        1,
    )

    mock_client = MagicMock()
    mapping = {
        "3 施工技术措施": chapter_3,
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
        custom_requirements="请强化雨季施工、环保水保和应急处置要求。",
        llm_config={"model": "demo-model", "api_key": "secret-key"},
    )

    assert "重点落实雨季施工组织要求" in markdown
    assert "补充环保水保专项管控要求" in markdown
    assert "强化应急处置响应链路" in markdown
    assert "进一步强调环保水保过程留痕" in markdown
    assert mock_llm_cls.call_count == 4
    assert mock_client.chat_with_template.call_count == 4


@patch("demo.generator.LLMClient")
def test_generate_demo_markdown_invalid_rewrite_falls_back_to_original(mock_llm_cls) -> None:
    """若 LLM 改写破坏章节结构，应自动回退原章节内容。"""
    form_data, editable_tables = build_initial_demo_inputs()
    original_markdown = generate_demo_markdown(form_data, editable_tables)
    chapter_1 = _extract_chapter(original_markdown, 1, 2).replace(
        "特编制本施工方案。",
        "特编制本施工方案，并补充总体风格与正式表述要求。",
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
        custom_requirements="请保持全文文风正式专业，符合国网工程管理口径，不改变章节结构。",
        llm_config={"model": "demo-model", "api_key": "secret-key"},
    )

    assert "补充总体风格与正式表述要求" in markdown
    assert "#### 2.6.4 箱筋安装要求" in markdown
    assert "仅保留一个小节" not in markdown
    assert len(markdown) >= len(original_markdown) - 1000
    assert mock_client.chat_with_template.call_count == 2
