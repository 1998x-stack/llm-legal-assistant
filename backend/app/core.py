"""Deterministic, synthetic-only NDA document parser and evidence engine.

This is NOT a New York legal playbook and does not call an LLM.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import re
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import fitz
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph


MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 40
MAX_UNCOMPRESSED = 30 * 1024 * 1024
PLAYBOOK_ID = "SYNTHETIC-UNAPPROVED-v0.1"
RULE_IDS = ("SYN-TERM", "SYN-RETURN", "SYN-PURPOSE")


class DocumentError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class Block:
    block_id: str
    text: str
    page: int | None = None

    def as_dict(self) -> dict:
        return {"block_id": self.block_id, "text": self.text, "page": self.page}


@dataclass(frozen=True)
class ParsedDocument:
    blocks: tuple[Block, ...]
    sha256_hex: str
    page_count: int | None
    media_type: str


def _docx_blocks(data: bytes) -> tuple[Block, ...]:
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 500:
                raise DocumentError("UNSAFE_ARCHIVE", "Too many archive entries")
            total = sum(e.file_size for e in entries)
            if total > MAX_UNCOMPRESSED:
                raise DocumentError("UNSAFE_ARCHIVE", "Uncompressed file exceeds limit")
            for e in entries:
                if e.compress_size and e.file_size / e.compress_size > 200:
                    raise DocumentError("UNSAFE_ARCHIVE", "Suspicious archive compression")
                if "vbaproject" in e.filename.lower() or e.filename.lower().endswith(".bin"):
                    raise DocumentError("UNSAFE_ARCHIVE", "Macros or embedded binaries are unsupported")
            if "word/document.xml" not in archive.namelist():
                raise DocumentError("UNSUPPORTED_TYPE", "Not a DOCX document")
        document = Document(BytesIO(data))
    except (BadZipFile, KeyError, OSError) as exc:
        raise DocumentError("UNSUPPORTED_TYPE", "Invalid DOCX file") from exc

    # Header/footer content is not indexed in this demo; reject rather than skip silently.
    for section in document.sections:
        for part in (section.header, section.footer):
            if any(p.text.strip() for p in part.paragraphs) or part.tables:
                raise DocumentError("PARSE_INCOMPLETE", "Headers/footers are unsupported")
    output: list[Block] = []
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            text = Paragraph(child, document).text.strip()
            if text:
                output.append(Block(f"docx:p:{len(output):05d}", text))
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            for row in table.rows:
                for cell in row.cells:
                    value = "\n".join(p.text for p in cell.paragraphs).strip()
                    if value:
                        output.append(Block(f"docx:cell:{len(output):05d}", value))
    if not output or sum(len(b.text) for b in output) < 40:
        raise DocumentError("PARSE_INCOMPLETE", "Document text is too short or empty")
    return tuple(output)


def _pdf_blocks(data: bytes) -> tuple[tuple[Block, ...], int]:
    try:
        with fitz.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise DocumentError("UNSUPPORTED_TYPE", "Encrypted PDFs are unsupported")
            if not (1 <= pdf.page_count <= MAX_PAGES):
                raise DocumentError("TOO_MANY_PAGES", "PDF page limit exceeded")
            blocks: list[Block] = []
            for number, page in enumerate(pdf, start=1):
                content = [b for b in page.get_text("blocks") if len(b) > 6 and b[6] == 0]
                for item in content:
                    text = item[4].strip()
                    if text:
                        blocks.append(Block(f"pdf:page:{number}:block:{len(blocks):05d}", text, number))
            if sum(len(b.text) for b in blocks) < 40:
                raise DocumentError("SCAN_PDF", "Scanned or empty PDF is unsupported")
            return tuple(blocks), pdf.page_count
    except (RuntimeError, ValueError) as exc:
        if isinstance(exc, DocumentError):
            raise
        raise DocumentError("UNSUPPORTED_TYPE", "Invalid PDF file") from exc


def parse_document(filename: str, content: bytes) -> ParsedDocument:
    if not content or len(content) > MAX_BYTES:
        raise DocumentError("FILE_SIZE", "File must be non-empty and at most 10 MB")
    extension = Path(filename).suffix.lower()
    if extension == ".docx":
        if not content.startswith(b"PK\x03\x04"):
            raise DocumentError("UNSUPPORTED_TYPE", "DOCX signature mismatch")
        blocks, pages, mime = _docx_blocks(content), None, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif extension == ".pdf":
        if not content.startswith(b"%PDF"):
            raise DocumentError("UNSUPPORTED_TYPE", "PDF signature mismatch")
        blocks, pages = _pdf_blocks(content)
        mime = "application/pdf"
    else:
        raise DocumentError("UNSUPPORTED_TYPE", "Only DOCX and text-based PDF are supported")
    return ParsedDocument(blocks, sha256(content).hexdigest(), pages, mime)


def scope_gate(context: dict, blocks: tuple[Block, ...]) -> tuple[str | None, str]:
    """Return (blocking_code, explanation); do not infer legal validity."""
    if context.get("contract_type") != "mutual_nda" or context.get("language") != "en":
        return "OUT_OF_SCOPE", "Only English mutual NDAs are supported"
    if context.get("parties_are_businesses") is not True:
        return "OUT_OF_SCOPE", "Both parties must be businesses"
    if context.get("governing_law") != "NY":
        return "OUT_OF_SCOPE", "Only an explicit New York law scope is supported"
    if not context.get("purpose", "").strip() or context.get("client_role") not in {"disclosing", "receiving", "both"}:
        return "MISSING_CONTEXT", "Purpose and client role are required"
    if context.get("risk_posture") not in {"balanced", "conservative", "fast"}:
        return "MISSING_CONTEXT", "Risk posture is required"
    text = "\n".join(b.text for b in blocks).casefold()
    if not ("mutual" in text and ("confidential" in text or "non-disclosure" in text)):
        return "OUT_OF_SCOPE", "Document could not be identified as a mutual NDA"
    law_matches = re.findall(r"governed\s+by\s+(?:the\s+)?laws?\s+of\s+(?:the\s+state\s+of\s+)?([a-z ]{3,35})", text)
    if not law_matches:
        return "MISSING_GOVERNING_LAW", "A governing-law clause was not found in the document"
    if not all("new york" in value for value in law_matches):
        return "GOVERNING_LAW_CONFLICT", "The document refers to a different governing law"
    return None, "Scope matched; this is not a legal-validity determination"


def verified_anchor(block: Block, start: int, end: int) -> dict:
    if not (0 <= start < end <= len(block.text)):
        raise DocumentError("CITATION_MISMATCH", "Anchor offset is invalid")
    quote = block.text[start:end]
    return {
        "block_id": block.block_id, "start_char": start, "end_char": end,
        "exact_quote": quote, "quote_sha256": sha256(quote.encode("utf-8")).hexdigest(),
        "page": block.page,
    }


def verify_anchor(block: Block, anchor: dict) -> bool:
    try:
        expected = verified_anchor(block, int(anchor["start_char"]), int(anchor["end_char"]))
        return all(expected[key] == anchor[key] for key in ("block_id", "exact_quote", "quote_sha256", "page"))
    except (KeyError, ValueError, TypeError, DocumentError):
        return False


def inspect_synthetic_rules(blocks: tuple[Block, ...]) -> tuple[list[dict], list[dict]]:
    """Illustrative pattern checks, not qualified-lawyer-approved rules."""
    findings: list[dict] = []
    coverage: list[dict] = []
    all_blocks = [b.block_id for b in blocks]
    cases = (
        ("SYN-TERM", re.compile(r"\bperpetual(?:ly)?\b", re.I),
         "A perpetual-term phrase warrants human review", "Consider reviewing the duration with counsel"),
        ("SYN-PURPOSE", re.compile(r"\bany\s+purpose\b", re.I),
         "A broad-use phrase warrants human review", "Clarify the permitted purpose with counsel"),
    )
    for rule_id, pattern, title, suggestion in cases:
        matches = []
        for block in blocks:
            match = pattern.search(block.text)
            if match:
                matches.append(verified_anchor(block, match.start(), match.end()))
        coverage.append({"rule_id": rule_id, "outcome": "matched" if matches else "checked_no_finding",
                         "examined_block_ids": all_blocks})
        for anchor in matches:
            findings.append({"rule_id": rule_id, "title": title, "severity": "info",
                             "anchor": anchor, "suggestion": suggestion})
    has_return = any(re.search(r"\b(return\s+or\s+destroy|destroy\s+or\s+return)\b", b.text, re.I) for b in blocks)
    coverage.append({"rule_id": "SYN-RETURN", "outcome": "checked_no_finding" if has_return else "checked_absent",
                     "examined_block_ids": all_blocks})
    if not has_return:
        findings.append({"rule_id": "SYN-RETURN", "title": "No matching return-or-destroy phrase was found in extracted text",
                         "severity": "info", "anchor": None,
                         "suggestion": "Ask counsel to check the full document for a return/destruction clause"})
    return findings, coverage
