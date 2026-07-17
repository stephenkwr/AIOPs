"""Parse uploaded files into a common, structure-aware representation.

Each parser returns a ParsedDoc of Sections. A Section is a coherent unit of text
with metadata (page number, CSV row range, HTML title) that the chunker preserves
onto every chunk it produces — which is what later powers citations.
"""

import csv
import io
from dataclasses import dataclass, field

from pypdf import PdfReader
from selectolax.parser import HTMLParser

# mime type -> internal kind
ALLOWED_MIME = {
    "application/pdf": "pdf",
    "text/html": "html",
    "text/csv": "csv",
    "application/csv": "csv",
    "text/plain": "txt",
    "text/markdown": "txt",
}

# file extension -> internal kind (fallback when the mime type is generic/missing)
EXT_KIND = {
    "pdf": "pdf",
    "html": "html",
    "htm": "html",
    "csv": "csv",
    "txt": "txt",
    "md": "txt",
}

CSV_ROWS_PER_SECTION = 10


@dataclass
class Section:
    text: str
    meta: dict = field(default_factory=dict)


@dataclass
class ParsedDoc:
    sections: list[Section]
    page_count: int | None = None


def detect_kind(mime_type: str, filename: str) -> str | None:
    if mime_type in ALLOWED_MIME:
        return ALLOWED_MIME[mime_type]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXT_KIND.get(ext)


def parse(data: bytes, mime_type: str, filename: str) -> ParsedDoc:
    kind = detect_kind(mime_type, filename)
    if kind == "pdf":
        return _parse_pdf(data)
    if kind == "html":
        return _parse_html(data)
    if kind == "csv":
        return _parse_csv(data)
    if kind == "txt":
        return _parse_txt(data)
    raise ValueError(f"Unsupported file type: mime={mime_type!r} filename={filename!r}")


def _parse_pdf(data: bytes) -> ParsedDoc:
    reader = PdfReader(io.BytesIO(data))
    sections: list[Section] = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            sections.append(Section(text=text, meta={"page": i + 1}))
    return ParsedDoc(sections=sections, page_count=len(reader.pages))


def _parse_html(data: bytes) -> ParsedDoc:
    tree = HTMLParser(data)
    for node in tree.css("script, style, noscript"):
        node.decompose()
    body = tree.body or tree.root
    text = body.text(separator="\n", strip=True) if body else ""
    meta: dict = {}
    title = tree.css_first("title")
    if title:
        meta["title"] = title.text(strip=True)
    return ParsedDoc(sections=[Section(text=text, meta=meta)] if text else [])


def _parse_csv(data: bytes) -> ParsedDoc:
    text = data.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ParsedDoc(sections=[])
    header = rows[0]
    body = rows[1:]
    if not body:
        # Header-only file: still index the header line.
        return ParsedDoc(sections=[Section(text=", ".join(header), meta={"rows": "header"})])

    sections: list[Section] = []
    for start in range(0, len(body), CSV_ROWS_PER_SECTION):
        group = body[start : start + CSV_ROWS_PER_SECTION]
        lines = ["; ".join(f"{h}: {v}" for h, v in zip(header, r, strict=False)) for r in group]
        sections.append(
            Section(text="\n".join(lines), meta={"rows": f"{start + 1}-{start + len(group)}"})
        )
    return ParsedDoc(sections=sections)


def _parse_txt(data: bytes) -> ParsedDoc:
    text = data.decode("utf-8", errors="replace").strip()
    return ParsedDoc(sections=[Section(text=text)] if text else [])
