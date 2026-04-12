"""与 JSON 一致的 URL 字段优先级、消息类型推断（供 CSV / TXT 复用）。"""

from __future__ import annotations

# 与 json_parser._auto_url_raw 顺序一致（小写键用于表头匹配）
URL_HEADER_CANDIDATES: tuple[str, ...] = (
    "emojicdnurl",
    "emoji_cdn_url",
    "emojiurl",
    "emoji_url",
    "url",
    "imageurl",
    "image_url",
    "thumburl",
    "thumb_url",
    "bigurl",
    "big_url",
    "cdnurl",
    "cdn_url",
    "localpath",
    "local_path",
    "path",
)


def url_from_csv_row(
    row: dict[str, str | None],
    *,
    header_lower_to_actual: dict[str, str],
) -> str | None:
    """按列名（不区分大小写）取第一条非空 URL。"""
    for cand in URL_HEADER_CANDIDATES:
        actual = header_lower_to_actual.get(cand)
        if not actual:
            continue
        v = (row.get(actual) or "").strip()
        if v:
            return v
    return None


def infer_message_kind(
    *,
    type_cell: str | None = None,
    local_type_cell: str | None = None,
    has_url: bool = False,
    body: str = "",
) -> str:
    """与 json 导出一致的图片/表情等类型推断。"""
    body_stripped = (body or "").strip()
    body_nonempty = bool(body_stripped)

    if has_url and not body_nonempty:
        return "image"

    if local_type_cell is not None and str(local_type_cell).strip() != "":
        try:
            lt = int(float(str(local_type_cell).strip()))
            if lt in (3, 43, 47, 48, 49):
                return "image"
        except ValueError:
            pass

    if type_cell is not None and str(type_cell).strip() != "":
        raw_s = str(type_cell)
        sv = raw_s.lower()
        if sv in ("3", "43", "47"):
            return "image"
        if any(x in sv for x in ("image", "pic", "photo", "img", "picture")):
            return "image"
        if any(x in raw_s for x in ("图片", "圖片", "照片", "表情", "貼圖", "贴纸")):
            return "image"

    if has_url:
        return "image"

    if body_stripped in ("[图片]", "[表情包]", "[表情]", "[动画表情]"):
        return "image"
    if body_stripped.startswith("[图片]") or body_stripped.startswith("[表情包]"):
        return "image"

    return "text"
