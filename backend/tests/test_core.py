from hashlib import sha256
from io import BytesIO

import fitz
import pytest
from docx import Document

from app.core import DocumentError, inspect_synthetic_rules, parse_document, scope_gate, verify_anchor, verified_anchor


def synthetic_docx(texts: list[str]) -> bytes:
    doc = Document()
    for line in texts:
        doc.add_paragraph(line)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


BASE = [
    "Mutual Non-Disclosure Agreement",
    "Each party can be a Disclosing Party and a Receiving Party.",
    "The parties shall use Confidential Information only for the specified purpose.",
    "This Agreement is governed by the laws of the State of New York.",
    "Each party shall return or destroy confidential materials at termination.",
]


def test_docx_block_anchors_handle_duplicate_text():
    data = synthetic_docx(BASE + ["A perpetual duty.", "A perpetual duty."])
    parsed = parse_document("nda.docx", data)
    assert parsed.sha256_hex == sha256(data).hexdigest()
    assert parsed.page_count is None  # DOCX page numbers are not reliably available.
    assert parsed.blocks[-1].block_id != parsed.blocks[-2].block_id
    first = verified_anchor(parsed.blocks[-2], 2, 11)
    second = verified_anchor(parsed.blocks[-1], 2, 11)
    assert verify_anchor(parsed.blocks[-2], first)
    assert verify_anchor(parsed.blocks[-1], second)
    assert not verify_anchor(parsed.blocks[-1], first)
    assert not verify_anchor(parsed.blocks[-2], {**first, "exact_quote": "fabricated"})


def test_scope_gate_blocks_other_governing_law_and_missing_law():
    context = {"contract_type": "mutual_nda", "language": "en",
               "parties_are_businesses": True, "governing_law": "NY",
               "purpose": "Discuss a commercial partnership",
               "client_role": "both", "risk_posture": "balanced"}
    good = parse_document("nda.docx", synthetic_docx(BASE)).blocks
    assert scope_gate(context, good)[0] is None
    ca = parse_document("nda.docx", synthetic_docx(BASE[:-2] + [
        "This Agreement is governed by the laws of California.",
        BASE[-1],
    ])).blocks
    assert scope_gate(context, ca)[0] == "GOVERNING_LAW_CONFLICT"
    missing = parse_document("nda.docx", synthetic_docx(BASE[:3] + BASE[-1:])).blocks
    assert scope_gate(context, missing)[0] == "MISSING_GOVERNING_LAW"
    assert scope_gate({**context, "contract_type": "unilateral_nda"}, good)[0] == "OUT_OF_SCOPE"


def test_absence_is_coverage_not_fabricated_source():
    blocks = parse_document("nda.docx", synthetic_docx(BASE[:-1])).blocks
    findings, coverage = inspect_synthetic_rules(blocks)
    item = next(f for f in findings if f["rule_id"] == "SYN-RETURN")
    status = next(c for c in coverage if c["rule_id"] == "SYN-RETURN")
    assert item["anchor"] is None
    assert status["outcome"] == "checked_absent"
    assert len(status["examined_block_ids"]) == len(blocks)


def test_perpetuity_variant_is_flagged_with_exact_anchor():
    parsed = parse_document("nda.docx", synthetic_docx(BASE + [
        "Obligations survive in perpetuity."
    ]))
    findings, coverage = inspect_synthetic_rules(parsed.blocks)
    item = next(f for f in findings if f["rule_id"] == "SYN-TERM")
    assert item["anchor"]["exact_quote"] == "perpetuity"
    block = next(b for b in parsed.blocks if b.block_id == item["anchor"]["block_id"])
    assert verify_anchor(block, item["anchor"])
    assert next(c for c in coverage if c["rule_id"] == "SYN-TERM")["outcome"] == "matched"


def test_invalid_signature_and_empty_pdf_fail_closed():
    with pytest.raises(DocumentError) as exc:
        parse_document("nda.docx", b"Not a docx")
    assert exc.value.code == "UNSUPPORTED_TYPE"
    pdf = fitz.open()
    pdf.new_page()
    data = pdf.tobytes()
    pdf.close()
    with pytest.raises(DocumentError) as exc:
        parse_document("nda.pdf", data)
    assert exc.value.code == "SCAN_PDF"
