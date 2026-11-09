"""Local-only FastAPI for synthetic NDA workflow testing.

IMPORTANT: Demo headers are forgeable. Not for production or real contracts.
"""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from docx import Document
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .core import (
    MAX_BYTES, PLAYBOOK_ID, RULE_IDS, Block, DocumentError,
    inspect_synthetic_rules, parse_document, scope_gate, verify_anchor,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def opaque(prefix: str) -> str:
    return prefix + "_" + uuid4().hex


def compact(data: object) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS matters (
  id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
  status TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
  document_id TEXT, context_json TEXT, analysis_id TEXT, approval_id TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, matter_id TEXT NOT NULL, filename TEXT NOT NULL,
  media_type TEXT NOT NULL, sha256 TEXT NOT NULL, content BLOB NOT NULL,
  created_at TEXT NOT NULL, FOREIGN KEY(matter_id) REFERENCES matters(id)
);
CREATE TABLE IF NOT EXISTS blocks (
  document_id TEXT NOT NULL, block_id TEXT NOT NULL, position INTEGER NOT NULL,
  text TEXT NOT NULL, page INTEGER, PRIMARY KEY(document_id, block_id)
);
CREATE TABLE IF NOT EXISTS findings (
  id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, matter_id TEXT NOT NULL,
  rule_id TEXT NOT NULL, title TEXT NOT NULL, severity TEXT NOT NULL,
  anchor_json TEXT, suggestion TEXT NOT NULL,
  decision TEXT NOT NULL DEFAULT 'unreviewed', edited_text TEXT,
  decision_by TEXT, reason TEXT
);
CREATE TABLE IF NOT EXISTS coverage (
  analysis_id TEXT NOT NULL, rule_id TEXT NOT NULL,
  outcome TEXT NOT NULL, block_ids_json TEXT NOT NULL,
  PRIMARY KEY(analysis_id, rule_id)
);
CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY, matter_id TEXT NOT NULL, snapshot_hash TEXT NOT NULL,
  snapshot_json TEXT NOT NULL, reviewer TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exports (
  id TEXT PRIMARY KEY, matter_id TEXT NOT NULL, approval_id TEXT NOT NULL,
  content BLOB NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY, matter_id TEXT NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def db_path() -> str:
    return os.environ.get("DATABASE_PATH", "./legal_dev.sqlite3")


@contextmanager
def db_connection():
    conn = sqlite3.connect(db_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    p = Path(db_path())
    p.parent.mkdir(parents=True, exist_ok=True)
    with db_connection() as db:
        db.executescript(SCHEMA)
    yield


app = FastAPI(
    title="Legal Intelligence — Synthetic NDA Demo",
    version="0.1.0",
    description="Developer-only technical prototype. No legal advice. Synthetic input only.",
    lifespan=lifespan,
)


class MatterInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ContextInput(BaseModel):
    contract_type: str
    language: str
    parties_are_businesses: bool
    governing_law: str
    client_role: str
    purpose: str = Field(min_length=1, max_length=500)
    risk_posture: str


class DecisionInput(BaseModel):
    action: str
    reason: str = ""
    edited_text: str = ""


class ApprovalInput(BaseModel):
    acknowledged_independent_review: bool


def auth(request: Request, x_demo_user: str | None = Header(default=None),
         x_demo_role: str | None = Header(default=None)) -> dict:
    if os.environ.get("APP_ENV") != "development" or os.environ.get("DEMO_MODE") != "1":
        raise HTTPException(503, detail={"code": "DEMO_DISABLED", "message": "Local demo is disabled"})
    # Deliberate localhost-only barrier; NOT a replacement for real authentication.
    if request.client is None or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(403, detail={"code": "LOCAL_ONLY"})
    if not x_demo_user or not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", x_demo_user):
        raise HTTPException(401, detail={"code": "DEMO_USER_REQUIRED"})
    if x_demo_role not in {"preparer", "reviewer"}:
        raise HTTPException(401, detail={"code": "DEMO_ROLE_REQUIRED"})
    return {"user": x_demo_user, "role": x_demo_role}


def fail(code: str, status: int = 409) -> None:
    raise HTTPException(status, detail={"code": code})


def get_matter(db: sqlite3.Connection, matter_id: str, user: dict) -> sqlite3.Row:
    m = db.execute("SELECT * FROM matters WHERE id=? AND owner=?", (matter_id, user["user"])).fetchone()
    if m is None:
        fail("MATTER_NOT_FOUND", 404)
    return m


def expect_rev(revision: int, if_match: str | None):
    if if_match is None or if_match.strip('"') != str(revision):
        fail("VERSION_STALE")


def audit(db: sqlite3.Connection, matter_id: str, actor: str, action: str):
    db.execute("INSERT INTO audit_events VALUES (?, ?, ?, ?, ?)",
               (opaque("evt"), matter_id, actor, action, now()))


def blocks_for(db: sqlite3.Connection, document_id: str) -> tuple[Block, ...]:
    rows = db.execute("SELECT * FROM blocks WHERE document_id=? ORDER BY position",
                      (document_id,)).fetchall()
    return tuple(Block(b["block_id"], b["text"], b["page"]) for b in rows)


def latest_findings(db: sqlite3.Connection, m: sqlite3.Row) -> list[dict]:
    if not m["analysis_id"]:
        return []
    rows = db.execute("SELECT * FROM findings WHERE matter_id=? AND analysis_id=? ORDER BY rowid",
                      (m["id"], m["analysis_id"])).fetchall()
    return [{**dict(x), "anchor": json.loads(x["anchor_json"]) if x["anchor_json"] else None,
             "anchor_json": None} for x in rows]


def latest_coverage(db: sqlite3.Connection, m: sqlite3.Row) -> list[dict]:
    if not m["analysis_id"]:
        return []
    rows = db.execute("SELECT * FROM coverage WHERE analysis_id=? ORDER BY rule_id",
                      (m["analysis_id"],)).fetchall()
    return [{"rule_id": r["rule_id"], "outcome": r["outcome"],
             "examined_block_ids": json.loads(r["block_ids_json"])} for r in rows]


@app.get("/health")
def health():
    return {"status": "ok", "mode": "synthetic_only", "version": "0.1.0"}


@app.post("/v1/matters", status_code=201)
def create_matter(body: MatterInput, user: dict = Depends(auth)):
    mid = opaque("mat")
    with db_connection() as db:
        db.execute("INSERT INTO matters (id,owner,name,status,revision,created_at) VALUES (?,?,?,?,0,?)",
                   (mid, user["user"], body.name, "DRAFT", now()))
        audit(db, mid, user["user"], "matter_created")
    return {"matter_id": mid, "revision": 0, "status": "DRAFT"}


@app.get("/v1/matters")
def list_matters(user: dict = Depends(auth)):
    with db_connection() as db:
        rows = db.execute("SELECT id,name,status,revision FROM matters WHERE owner=? ORDER BY created_at DESC",
                          (user["user"],)).fetchall()
        return {"items": [dict(r) for r in rows]}


@app.post("/v1/matters/{matter_id}/documents", status_code=201)
async def upload_document(matter_id: str, file: UploadFile = File(...),
                          user: dict = Depends(auth)):
    data = await file.read(MAX_BYTES + 1)
    try:
        parsed = parse_document(file.filename or "", data)
    except DocumentError as e:
        raise HTTPException(422, detail={"code": e.code, "message": str(e)}) from e
    did = opaque("dv")
    with db_connection() as db:
        m = get_matter(db, matter_id, user)
        db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
                   (did, matter_id, (file.filename or "document")[:120],
                    parsed.media_type, parsed.sha256_hex, data, now()))
        for i, b in enumerate(parsed.blocks):
            db.execute("INSERT INTO blocks VALUES (?,?,?,?,?)", (did, b.block_id, i, b.text, b.page))
        db.execute("""UPDATE matters SET document_id=?, context_json=NULL, analysis_id=NULL,
                      approval_id=NULL, status='UPLOADED', revision=revision+1 WHERE id=?""",
                   (did, matter_id))
        audit(db, matter_id, user["user"], "document_uploaded")
        return {"document_version_id": did, "sha256": parsed.sha256_hex,
                "block_count": len(parsed.blocks), "page_count": parsed.page_count,
                "revision": m["revision"] + 1, "status": "UPLOADED"}


@app.put("/v1/matters/{matter_id}/context")
def set_context(matter_id: str, body: ContextInput, if_match: str | None = Header(default=None),
                user: dict = Depends(auth)):
    with db_connection() as db:
        m = get_matter(db, matter_id, user)
        expect_rev(m["revision"], if_match)
        if not m["document_id"]:
            fail("DOCUMENT_REQUIRED")
        context = body.model_dump()
        code, explanation = scope_gate(context, blocks_for(db, m["document_id"]))
        if code:
            raise HTTPException(422, detail={"code": code, "message": explanation})
        db.execute("""UPDATE matters SET context_json=?, analysis_id=NULL, approval_id=NULL,
                      status='CONTEXT_REQUIRED', revision=revision+1 WHERE id=?""",
                   (compact(context), matter_id))
        audit(db, matter_id, user["user"], "context_confirmed")
        return {"scope_status": "verified", "message": explanation,
                "revision": m["revision"] + 1, "status": "CONTEXT_REQUIRED"}


@app.post("/v1/matters/{matter_id}/analyses", status_code=201)
def analyze_matter(matter_id: str, if_match: str | None = Header(default=None),
                   user: dict = Depends(auth)):
    with db_connection() as db:
        m = get_matter(db, matter_id, user)
        expect_rev(m["revision"], if_match)
        if not m["document_id"] or not m["context_json"]:
            fail("MISSING_CONTEXT")
        blocks = blocks_for(db, m["document_id"])
        code, explanation = scope_gate(json.loads(m["context_json"]), blocks)
        if code:
            raise HTTPException(422, detail={"code": code, "message": explanation})
        # No model, no network, no lawyer-approved rules: technical walkthrough only.
        generated, coverage = inspect_synthetic_rules(blocks)
        aid = opaque("ar")
        for item in generated:
            anchor = item["anchor"]
            if anchor:
                block = next((b for b in blocks if b.block_id == anchor["block_id"]), None)
                if block is None or not verify_anchor(block, anchor):
                    fail("CITATION_MISMATCH")
            db.execute("""INSERT INTO findings
                (id,analysis_id,matter_id,rule_id,title,severity,anchor_json,suggestion)
                VALUES(?,?,?,?,?,?,?,?)""",
                (opaque("fd"), aid, matter_id, item["rule_id"], item["title"], item["severity"],
                 compact(anchor) if anchor else None, item["suggestion"]))
        for item in coverage:
            db.execute("INSERT INTO coverage VALUES (?,?,?,?)",
                       (aid, item["rule_id"], item["outcome"], compact(item["examined_block_ids"])))
        db.execute("""UPDATE matters SET analysis_id=?, approval_id=NULL, status='REVIEW_READY',
                      revision=revision+1 WHERE id=?""", (aid, matter_id))
        audit(db, matter_id, user["user"], "synthetic_analysis_completed")
        return {"analysis_id": aid, "finding_count": len(generated), "playbook": PLAYBOOK_ID,
                "revision": m["revision"] + 1, "status": "REVIEW_READY"}


@app.get("/v1/matters/{matter_id}")
def matter_detail(matter_id: str, user: dict = Depends(auth)):
    with db_connection() as db:
        m = get_matter(db, matter_id, user)
        blocks = [b.as_dict() for b in blocks_for(db, m["document_id"])] if m["document_id"] else []
        return {"matter_id": m["id"], "name": m["name"], "revision": m["revision"],
                "status": m["status"], "document_version_id": m["document_id"],
                "analysis_id": m["analysis_id"], "approval_id": m["approval_id"],
                "context": json.loads(m["context_json"]) if m["context_json"] else None,
                "playbook": PLAYBOOK_ID, "blocks": blocks,
                "findings": latest_findings(db, m), "coverage": latest_coverage(db, m)}


@app.patch("/v1/matters/{matter_id}/findings/{finding_id}/decision")
def decide(matter_id: str, finding_id: str, body: DecisionInput,
           if_match: str | None = Header(default=None),
           user: dict = Depends(auth)):
    if body.action not in {"accepted", "dismissed", "edited", "needs_context", "escalated"}:
        fail("INVALID_DECISION", 422)
    if body.action == "edited" and not body.edited_text.strip():
        fail("EDITED_TEXT_REQUIRED", 422)
    if body.action == "dismissed" and not body.reason.strip():
        fail("DECISION_REASON_REQUIRED", 422)
    with db_connection() as db:
        m = get_matter(db, matter_id, user)
        expect_rev(m["revision"], if_match)
        f = db.execute("SELECT * FROM findings WHERE id=? AND matter_id=? AND analysis_id=?",
                       (finding_id, matter_id, m["analysis_id"])).fetchone()
        if f is None:
            fail("FINDING_NOT_FOUND", 404)
        db.execute("""UPDATE findings SET decision=?, edited_text=?, decision_by=?, reason=? WHERE id=?""",
                   (body.action, body.edited_text if body.action == "edited" else None,
                    user["user"], body.reason, finding_id))
        db.execute("""UPDATE matters SET status='IN_REVIEW', approval_id=NULL,
                      revision=revision+1 WHERE id=?""", (matter_id,))
        audit(db, matter_id, user["user"], "finding_" + body.action)
        return {"finding_id": finding_id, "decision": body.action, "revision": m["revision"] + 1}


@app.post("/v1/matters/{matter_id}/approvals", status_code=201)
def approve(matter_id: str, body: ApprovalInput, if_match: str | None = Header(default=None),
            user: dict = Depends(auth)):
    if user["role"] != "reviewer":
        fail("REVIEWER_REQUIRED", 403)
    if not body.acknowledged_independent_review:
        fail("ACKNOWLEDGMENT_REQUIRED", 422)
    with db_connection() as db:
        m = get_matter(db, matter_id, user)
        expect_rev(m["revision"], if_match)
        if m["status"] not in {"IN_REVIEW", "REVIEW_READY"} or not m["analysis_id"]:
            fail("REVIEW_BLOCKED")
        findings = latest_findings(db, m)
        coverage = latest_coverage(db, m)
        if len(coverage) != len(RULE_IDS) or any(c["outcome"] not in
                {"matched", "checked_no_finding", "checked_absent"} for c in coverage):
            fail("COVERAGE_BLOCKED")
        if any(f["decision"] not in {"accepted", "edited", "dismissed"} for f in findings):
            fail("REVIEW_BLOCKED")
        blocks = blocks_for(db, m["document_id"])
        for f in findings:
            if f["anchor"]:
                block = next((b for b in blocks if b.block_id == f["anchor"]["block_id"]), None)
                if block is None or not verify_anchor(block, f["anchor"]):
                    fail("CITATION_MISMATCH")
        doc = db.execute("SELECT sha256 FROM documents WHERE id=?", (m["document_id"],)).fetchone()
        snapshot = {"matter_id": m["id"], "document_sha256": doc["sha256"],
                    "context": json.loads(m["context_json"]), "analysis_id": m["analysis_id"],
                    "playbook": PLAYBOOK_ID, "coverage": coverage, "findings": findings,
                    "reviewer": user["user"]}
        payload = compact(snapshot)
        digest = sha256(payload.encode()).hexdigest()
        approval_id = opaque("ap")
        db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?)",
                   (approval_id, matter_id, digest, payload, user["user"], now()))
        db.execute("""UPDATE matters SET approval_id=?, status='APPROVED',
                      revision=revision+1 WHERE id=?""", (approval_id, matter_id))
        audit(db, matter_id, user["user"], "synthetic_approval_recorded")
        return {"approval_id": approval_id, "snapshot_sha256": digest,
                "revision": m["revision"] + 1, "status": "APPROVED",
                "notice": "Simulated reviewer, not a licensed-lawyer verification"}


def render_report(snapshot: dict) -> bytes:
    document = Document()
    document.add_heading("Synthetic NDA review — technical demonstration", level=1)
    document.add_paragraph(
        "NOT LEGAL ADVICE. Rules are synthetic and not approved by qualified counsel. "
        "Reviewer identity is a local demo header, not a verified lawyer."
    )
    document.add_paragraph("Document SHA-256: " + snapshot["document_sha256"])
    document.add_paragraph("Playbook: " + snapshot["playbook"])
    document.add_heading("Coverage", level=2)
    for cov in snapshot["coverage"]:
        document.add_paragraph(cov["rule_id"] + " — " + cov["outcome"], style="List Bullet")
    document.add_heading("Reviewed findings", level=2)
    for item in snapshot["findings"]:
        document.add_heading(item["rule_id"] + ": " + item["title"], level=3)
        document.add_paragraph("Decision: " + item["decision"])
        if item["anchor"]:
            document.add_paragraph("Source: " + item["anchor"]["exact_quote"])
        else:
            document.add_paragraph("Source: No exact quote; absence check limited to extracted blocks")
        if item["decision"] != "dismissed":
            document.add_paragraph("Suggested review action: " +
                                   (item["edited_text"] or item["suggestion"]))
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@app.post("/v1/matters/{matter_id}/exports", status_code=201)
def create_export(matter_id: str, if_match: str | None = Header(default=None),
                  user: dict = Depends(auth)):
    if user["role"] != "reviewer":
        fail("REVIEWER_REQUIRED", 403)
    with db_connection() as db:
        m = get_matter(db, matter_id, user)
        expect_rev(m["revision"], if_match)
        if m["status"] not in {"APPROVED", "EXPORTED"} or not m["approval_id"]:
            fail("APPROVAL_REQUIRED")
        ap = db.execute("SELECT * FROM approvals WHERE id=? AND matter_id=?",
                        (m["approval_id"], matter_id)).fetchone()
        if ap is None or sha256(ap["snapshot_json"].encode()).hexdigest() != ap["snapshot_hash"]:
            fail("EXPORT_MISMATCH")
        payload = render_report(json.loads(ap["snapshot_json"]))
        eid = opaque("ex")
        digest = sha256(payload).hexdigest()
        db.execute("INSERT INTO exports VALUES (?,?,?,?,?,?)",
                   (eid, matter_id, ap["id"], payload, digest, now()))
        db.execute("UPDATE matters SET status='EXPORTED', revision=revision+1 WHERE id=?",
                   (matter_id,))
        audit(db, matter_id, user["user"], "synthetic_report_exported")
        return {"export_id": eid, "sha256": digest, "revision": m["revision"] + 1,
                "status": "EXPORTED", "filename": "synthetic-review-report.docx"}


@app.get("/v1/matters/{matter_id}/exports/{export_id}/download")
def download_export(matter_id: str, export_id: str, user: dict = Depends(auth)):
    with db_connection() as db:
        m = get_matter(db, matter_id, user)
        if m["status"] != "EXPORTED" or not m["approval_id"]:
            fail("APPROVAL_REQUIRED")
        result = db.execute("SELECT * FROM exports WHERE id=? AND matter_id=? AND approval_id=?",
                            (export_id, matter_id, m["approval_id"])).fetchone()
        if result is None:
            fail("EXPORT_NOT_FOUND", 404)
        if sha256(result["content"]).hexdigest() != result["sha256"]:
            fail("EXPORT_MISMATCH")
        return Response(
            content=result["content"], media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": 'attachment; filename="synthetic-review-report.docx"',
                     "Cache-Control": "no-store"},
        )


@app.get("/v1/matters/{matter_id}/audit")
def audit_log(matter_id: str, user: dict = Depends(auth)):
    with db_connection() as db:
        get_matter(db, matter_id, user)
        rows = db.execute("SELECT actor,action,created_at FROM audit_events WHERE matter_id=? ORDER BY created_at",
                          (matter_id,)).fetchall()
        return {"items": [dict(x) for x in rows]}
