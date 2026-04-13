"""施工图片上传管理：上传、图题编辑、持久化存储。"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

_UPLOADS_DIRNAME = "uploads"
_CAPTIONS_FILENAME = "captions.json"


def _get_uploads_dir() -> Path:
    """返回 uploads 目录，不存在时自动创建。"""
    path = Path(__file__).resolve().parent.parent / _UPLOADS_DIRNAME
    path.mkdir(exist_ok=True)
    return path


def _sanitize_filename(name: str) -> str:
    """仅保留安全字符，避免写入时出现非法路径。"""
    cleaned = "".join(c for c in name if c.isalnum() or c in "._-")
    return cleaned or "image"


def _save_uploads_metadata(images: list[dict]) -> None:
    meta_path = _get_uploads_dir() / _CAPTIONS_FILENAME
    payload = [
        {"filename": img["filename"], "caption": img.get("caption", "")}
        for img in images
    ]
    meta_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_uploads_metadata() -> list[dict]:
    uploads_dir = _get_uploads_dir()
    meta_path = uploads_dir / _CAPTIONS_FILENAME
    if not meta_path.exists():
        return []
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    images: list[dict] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        filename = entry.get("filename")
        if not filename:
            continue
        file_path = uploads_dir / filename
        if not file_path.exists():
            continue
        images.append(
            {
                "file_id": None,
                "filename": filename,
                "path": str(file_path),
                "caption": entry.get("caption", ""),
            }
        )
    return images


def render_image_upload_section() -> None:
    """表单上方的图片上传区域：上传图片并填写图题，保存到本地。"""
    uploads_dir = _get_uploads_dir()

    if "uploaded_images" not in st.session_state:
        st.session_state["uploaded_images"] = _load_uploads_metadata()

    st.subheader("施工图片上传")
    st.caption(
        "上传图片并为每张图片填写图题。图片会保存到本地 "
        f"`{uploads_dir.name}/` 目录，当前版本暂不插入到生成的文档中。"
    )

    new_files = st.file_uploader(
        "选择图片文件（支持 PNG / JPG / JPEG / GIF / BMP / WEBP，可多选）",
        type=["png", "jpg", "jpeg", "gif", "bmp", "webp"],
        accept_multiple_files=True,
        key="image_uploader",
    )

    if new_files:
        processed_ids = {
            img.get("file_id")
            for img in st.session_state["uploaded_images"]
            if img.get("file_id") is not None
        }
        added = 0
        for upload in new_files:
            if upload.file_id in processed_ids:
                continue
            safe_name = _sanitize_filename(upload.name)
            save_path = uploads_dir / safe_name
            counter = 1
            while save_path.exists():
                stem = save_path.stem
                suffix = save_path.suffix
                save_path = uploads_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            save_path.write_bytes(upload.getvalue())
            st.session_state["uploaded_images"].append(
                {
                    "file_id": upload.file_id,
                    "filename": save_path.name,
                    "path": str(save_path),
                    "caption": "",
                }
            )
            added += 1
        if added:
            _save_uploads_metadata(st.session_state["uploaded_images"])
            st.success(f"已新增 {added} 张图片，请在下方填写图题。")

    images = st.session_state["uploaded_images"]
    if not images:
        st.info("尚未上传图片。")
        return

    st.markdown(f"**已上传 {len(images)} 张图片**")
    remove_index: int | None = None
    metadata_dirty = False

    for idx, img in enumerate(images):
        with st.container(border=True):
            col_img, col_caption = st.columns([1, 3])
            with col_img:
                try:
                    st.image(img["path"], width=180)
                except Exception:  # noqa: BLE001
                    st.warning(f"无法预览：{img['filename']}")
            with col_caption:
                current_caption = img.get("caption", "")
                new_caption = st.text_input(
                    f"图 {idx + 1} 图题（必填）",
                    value=current_caption,
                    key=f"image_caption_input_{idx}",
                    placeholder="例如：图 1-1 施工现场总平面布置图",
                )
                if new_caption != current_caption:
                    img["caption"] = new_caption
                    metadata_dirty = True
                st.caption(f"文件名：{img['filename']}")
                if st.button("删除该图片", key=f"image_delete_{idx}"):
                    remove_index = idx

    if remove_index is not None:
        removed = images.pop(remove_index)
        Path(removed["path"]).unlink(missing_ok=True)
        _save_uploads_metadata(images)
        st.rerun()
    elif metadata_dirty:
        _save_uploads_metadata(images)
