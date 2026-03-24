"""线路工程 demo 源数据工具测试。"""

from demo.source_data import build_chapter_draft, collect_source_stats, format_tree, render_block_ref


def test_collect_source_stats_counts() -> None:
    """源数据统计应稳定返回节点数、内容类型和占位词数量。"""
    stats = collect_source_stats("data/2.json")

    assert stats["node_count"] == 23
    assert stats["content_type_counts"] == {"text": 19, "table": 6, "image": 3}
    assert stats["placeholder_counts"]["XXXX"] >= 50


def test_format_tree_contains_nested_nodes() -> None:
    """章节树预览应包含多级节点。"""
    tree = format_tree("data/2.json")

    assert "- 1 编制说明 | content=0 | children=3" in tree
    assert "  - 2.2 地形情况 | content=2 | children=1" in tree
    assert "    - 1.2.1沿线岩土工程条件 | content=1 | children=0" in tree


def test_build_chapter_draft_renders_markdown_preview() -> None:
    """章节草稿预览应能把源节点渲染成 Markdown。"""
    draft = build_chapter_draft(
        "data/2.json",
        [
            ["1 编制说明", "1.1 编制目的"],
            ["1 编制说明", "1.2 编制依据"],
        ],
    )

    assert "### 1.1 编制目的" in draft
    assert "本工程机械挖孔基础共计XXXX基" in draft
    assert "| 序号 | 依据 | 文号 |" in draft


def test_render_block_ref_returns_markdown_table() -> None:
    """source block 引用应能解析为 Markdown 表格。"""
    table = render_block_ref(
        "data/2.json",
        {
            "path": ["1、线路标段划分：", "2.4挖孔基础技术参数"],
            "content_index": 1,
        },
    )

    assert "| 杆塔号 | 杆塔型式 | 呼高 |" in table
    assert "A118" in table
