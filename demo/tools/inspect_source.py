"""源数据检查与模板更新辅助工具。"""

from __future__ import annotations

import argparse
import json
import sys

from demo.config_loader import get_chapter_map, load_chapter_registry, resolve_repo_path
from demo.source_data import build_chapter_draft, collect_source_stats, format_tree


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查线路工程 demo 的章节源数据")
    parser.add_argument(
        "--data-file",
        default="data/2.json",
        help="章节树 JSON 路径，默认 data/2.json",
    )
    parser.add_argument(
        "--chapter-id",
        help="按章节清单中的 chapter id 生成草稿预览，例如 chapter_1",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="按显式路径生成草稿，格式：标题1 > 标题2 > 标题3，可重复传入",
    )
    parser.add_argument("--tree-only", action="store_true", help="只输出章节树")
    parser.add_argument("--stats-only", action="store_true", help="只输出统计信息")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = _parse_args()
    data_file = resolve_repo_path(args.data_file)

    if not args.stats_only:
        print("=== 章节树预览 ===")
        print(format_tree(data_file))
        print()

    if not args.tree_only:
        print("=== 统计信息 ===")
        print(json.dumps(collect_source_stats(data_file), ensure_ascii=False, indent=2))
        print()

    if args.chapter_id:
        chapter_map = get_chapter_map(load_chapter_registry())
        if args.chapter_id not in chapter_map:
            raise SystemExit(f"未知章节 id: {args.chapter_id}")
        chapter = chapter_map[args.chapter_id]
        print(f"=== 章节草稿预览: {args.chapter_id} ===")
        print(build_chapter_draft(data_file, chapter.get("source_paths", [])))
        print()

    if args.path:
        source_paths = [[segment.strip() for segment in raw.split(">")] for raw in args.path]
        print("=== 显式路径草稿预览 ===")
        print(build_chapter_draft(data_file, source_paths))


if __name__ == "__main__":
    main()
