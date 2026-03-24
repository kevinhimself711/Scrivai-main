"""Demo 源数据解析与预览工具。"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

PLACEHOLDER_PATTERN = re.compile(r"X{2,}")


@dataclass(frozen=True)
class SourceNode:
    """带路径信息的源数据节点。"""

    path: tuple[str, ...]
    node: dict[str, Any]

    @property
    def path_str(self) -> str:
        return " > ".join(self.path)


def load_data_tree(data_file: str | Path) -> list[dict[str, Any]]:
    """读取章节树 JSON。"""
    path = Path(data_file)
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"源数据必须是 list: {path}")
    return data


def iter_nodes(
    nodes: Iterable[dict[str, Any]],
    parent_path: tuple[str, ...] = (),
) -> Iterable[SourceNode]:
    """深度优先遍历章节树。"""
    for node in nodes:
        path = parent_path + (node.get("title", "<no-title>"),)
        yield SourceNode(path=path, node=node)
        yield from iter_nodes(node.get("children", []), path)


def format_tree(data_file: str | Path) -> str:
    """输出章节树预览。"""
    lines: list[str] = []
    for source_node in iter_nodes(load_data_tree(data_file)):
        depth = len(source_node.path) - 1
        node = source_node.node
        lines.append(
            f"{'  ' * depth}- {node.get('title', '<no-title>')} "
            f"| content={len(node.get('content', []))} "
            f"| children={len(node.get('children', []))}"
        )
    return "\n".join(lines)


def find_node_by_path(data_file: str | Path, path: list[str] | tuple[str, ...]) -> dict[str, Any]:
    """根据标题路径查找节点。"""
    current_nodes = load_data_tree(data_file)
    current_node: dict[str, Any] | None = None

    for part in path:
        current_node = next((node for node in current_nodes if node.get("title") == part), None)
        if current_node is None:
            pretty = " > ".join(path)
            raise KeyError(f"未找到节点路径: {pretty}")
        current_nodes = current_node.get("children", [])

    return current_node or {}


def render_markdown_table(rows: list[Any]) -> str:
    """将二维数组或字典列表渲染为 Markdown 表格。"""
    if not rows:
        return ""

    if isinstance(rows[0], dict):
        headers = [str(key).strip() for key in rows[0].keys()]
        table_rows = [headers]
        for row in rows:
            table_rows.append([str(row.get(header, "")).strip() for header in headers])
        return _render_table_rows(table_rows)

    table_rows = [
        [str(cell).strip() for cell in row]
        for row in rows
        if isinstance(row, list) and any(str(cell).strip() for cell in row)
    ]
    return _render_table_rows(table_rows)


def _render_table_rows(rows: list[list[str]]) -> str:
    if not rows:
        return ""

    max_cols = max(len(row) for row in rows)
    padded_rows = [row + [""] * (max_cols - len(row)) for row in rows]

    header = padded_rows[0]
    separator = ["---"] * max_cols
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in padded_rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_content_item(item: dict[str, Any], ignore_images: bool = True) -> str:
    """将单个 content item 渲染为 Markdown。"""
    item_type = item.get("type")
    if item_type == "text":
        return str(item.get("content", item.get("text", ""))).strip()
    if item_type == "table":
        return render_markdown_table(item.get("data") or item.get("content") or [])
    if item_type == "image":
        if ignore_images:
            return ""
        alt = item.get("alt") or item.get("desc", "")
        src = item.get("src", "")
        return f"![{alt}]({src})"
    return ""


def render_content_list(items: list[dict[str, Any]], ignore_images: bool = True) -> str:
    """将一组 content 渲染为 Markdown。"""
    blocks: list[str] = []
    for item in items:
        rendered = render_content_item(item, ignore_images=ignore_images)
        if rendered:
            blocks.append(rendered)
    return "\n\n".join(blocks).strip()


def render_node(node: dict[str, Any], ignore_images: bool = True) -> str:
    """按节点类型渲染整块节点内容。"""
    node_type = node.get("type")
    if node_type == "table":
        return render_markdown_table(node.get("content", []))
    if node_type == "list":
        lines = []
        for item in node.get("content", []):
            text = render_content_item(item, ignore_images=ignore_images)
            if text:
                lines.append(f"- {text}")
        return "\n".join(lines).strip()
    return render_content_list(node.get("content", []), ignore_images=ignore_images)


def render_block_ref(data_file: str | Path, ref: dict[str, Any], ignore_images: bool = True) -> str:
    """按显式引用解析 source block。"""
    node = find_node_by_path(data_file, ref["path"])

    if ref.get("render_node"):
        return render_node(node, ignore_images=ignore_images)

    if "content_index" in ref:
        index = ref["content_index"]
        items = node.get("content", [])
        if index >= len(items):
            raise IndexError(f"content_index 超出范围: {ref}")
        item = items[index]
        if isinstance(item, dict) and item.get("type"):
            return render_content_item(item, ignore_images=ignore_images).strip()
        if isinstance(item, dict):
            return render_markdown_table([item]).strip()
        return str(item).strip()

    return render_node(node, ignore_images=ignore_images)


def build_chapter_draft(
    data_file: str | Path,
    source_paths: list[list[str]],
    ignore_images: bool = True,
) -> str:
    """根据 source_paths 生成章节草稿预览。"""
    parts: list[str] = []
    for path in source_paths:
        node = find_node_by_path(data_file, path)
        heading_level = min(len(path) + 1, 6)
        heading = "#" * heading_level
        parts.append(f"{heading} {node['title']}")

        body = render_node(node, ignore_images=ignore_images)
        if body:
            parts.append(body)

    return "\n\n".join(parts).strip()


def collect_source_stats(data_file: str | Path) -> dict[str, Any]:
    """统计数据文件中的节点、内容类型和占位词。"""
    nodes = load_data_tree(data_file)
    content_types: Counter[str] = Counter()
    placeholder_counts: Counter[str] = Counter()
    placeholder_snippets: list[dict[str, str]] = []
    node_count = 0

    for source_node in iter_nodes(nodes):
        node_count += 1
        title = source_node.node.get("title", "")
        for placeholder in PLACEHOLDER_PATTERN.findall(title):
            placeholder_counts[placeholder] += 1
            placeholder_snippets.append({"path": source_node.path_str, "snippet": title})

        for item in source_node.node.get("content", []):
            item_type = item.get("type", "unknown") if isinstance(item, dict) else "unknown"
            content_types[item_type] += 1

            if item_type == "text":
                text = str(item.get("content", item.get("text", "")))
                for placeholder in PLACEHOLDER_PATTERN.findall(text):
                    placeholder_counts[placeholder] += 1
                    placeholder_snippets.append(
                        {
                            "path": source_node.path_str,
                            "snippet": " ".join(text.split())[:240],
                        }
                    )

    return {
        "node_count": node_count,
        "content_type_counts": dict(content_types),
        "placeholder_counts": dict(placeholder_counts),
        "placeholder_snippets": placeholder_snippets,
    }
