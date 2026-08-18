"""文档解析：PDF / Markdown / Word / TXT（技能文档 01：parse_document 的底层实现）。"""
from pathlib import Path


def parse_pdf(file_path: str) -> str:
    """解析 PDF 文档为纯文本。"""
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    parts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(parts)


def parse_markdown(file_path: str) -> str:
    """解析 Markdown 文档为纯文本。"""
    from markdown_it import MarkdownIt

    text = Path(file_path).read_text(encoding="utf-8")
    md = MarkdownIt()
    tokens = md.parse(text)
    parts = [t.content for t in tokens if t.type == "inline"]
    return "\n".join(parts)


def parse_word(file_path: str) -> str:
    """解析 Word（.docx）文档为纯文本。"""
    from docx import Document

    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs)


def parse_txt(file_path: str) -> str:
    """读取 TXT 文档（按编码探测）。"""
    raw = Path(file_path).read_bytes()
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")