"""文本切片：将长文档拆分为独立知识单元（技能文档 01：split_text 的底层实现）。"""
import re


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def split_text(text: str, max_length: int = 500, overlap: int = 50) -> list[str]:
    """按标题层级与长度约束切片，保留上下文衔接。"""
    if not text:
        return []
    spans = list(_HEADING_RE.finditer(text))
    chunks: list[str] = []
    if not spans:
        chunks.extend(_pack_by_length(text, max_length, overlap))
        return chunks
    for i, span in enumerate(spans):
        title = span.group(2).strip()
        start = span.start()
        end = spans[i + 1].start() if i + 1 < len(spans) else len(text)
        body = text[start:end].strip()
        chunks.extend(_pack_by_length(body, max_length, overlap, title))
    return chunks


def _pack_by_length(segment: str, max_length: int, overlap: int, prefix: str = "") -> list[str]:
    text = (prefix + "\n" + segment).strip() if prefix else segment
    if len(text) <= max_length:
        return [text]
    out: list[str] = []
    step = max(1, max_length - overlap)
    for i in range(0, len(text), step):
        piece = text[i : i + max_length]
        if piece.strip():
            out.append(piece)
        if i + max_length >= len(text):
            break
    return out