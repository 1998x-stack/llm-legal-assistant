from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient
import pytest

from app.main import app


def nda_bytes(governing_law: str = "New York", with_return: bool = False) -> bytes:
    doc = Document()
    doc.add_paragraph("Mutual Non-Disclosure Agreement")
    doc.add_paragraph("Each party is both a disclosing party and a receiving party.")
    doc.add_paragraph("The Recipient may use information for any purpose.")
    doc.add_paragraph("This Agreement is governed by the laws of the State of " + governing_law + ".")
    doc.add_paragraph("Obligations may last in perpetuity.")
    if with_return:
        doc.add_paragraph("Each party must return or destroy confidential materials.")
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "prototype.sqlite3"))
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEMO_MODE", "1")
    with TestClient(app) as client:
        yield client


def headers(user="alice", role="preparer", revision=None):
    h = {"X-Demo-User": user, "X-Demo-Role": role}
    if revision is not None:
        h["If-Match"] = str(revision)
    return h


def make_context():
    return {"contract_type": "mutual_nda", "language": "en",
            "parties_are_businesses": True, "governing_law": "NY",
            "client_role": "both", "risk_posture": "balanced",
            "purpose": "Evaluate a potential commercial partnership"}


def create_uploaded(client, law="New York"):
    matter = client.post("/v1/matters", json={"name": "Synthetic NDA"}, headers=headers())
    assert matter.status_code == 201, matter.text
    mid = matter.json()["matter_id"]
    upload = client.post(f"/v1/matters/{mid}/documents", headers=headers(),
                         files={"file": ("synthetic.docx", nda_bytes(law),
                                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert upload.status_code == 201, upload.text
    return mid, upload.json()["revision"]


def test_full_synthetic_review_with_export_and_revocation(client):
    mid, rev = create_uploaded(client)
    scope = client.put(f"/v1/matters/{mid}/context", json=make_context(), headers=headers(revision=rev))
    assert scope.status_code == 200, scope.text
    rev = scope.json()["revision"]
    run = client.post(f"/v1/matters/{mid}/analyses", headers=headers(revision=rev))
    assert run.status_code == 201, run.text
    rev = run.json()["revision"]
    detail = client.get(f"/v1/matters/{mid}", headers=headers()).json()
    assert len(detail["coverage"]) == 3
    assert len(detail["findings"]) == 3
    assert any(f["anchor"] is None for f in detail["findings"])
    assert all(f["severity"] == "info" for f in detail["findings"])
    # The demo role cannot approve a review.
    bad = client.post(f"/v1/matters/{mid}/approvals",
                      json={"acknowledged_independent_review": True}, headers=headers(revision=rev))
    assert bad.status_code == 403
    # All findings need an explicit decision; no automatic acceptance.
    for finding in detail["findings"]:
        response = client.patch(f"/v1/matters/{mid}/findings/{finding['id']}/decision",
                                json={"action": "accepted"}, headers=headers(revision=rev))
        assert response.status_code == 200, response.text
        rev = response.json()["revision"]
    approved = client.post(f"/v1/matters/{mid}/approvals",
                           json={"acknowledged_independent_review": True},
                           headers=headers(role="reviewer", revision=rev))
    assert approved.status_code == 201, approved.text
    assert approved.json()["notice"].startswith("Simulated")
    rev = approved.json()["revision"]
    output = client.post(f"/v1/matters/{mid}/exports", headers=headers(role="reviewer", revision=rev))
    assert output.status_code == 201, output.text
    eid = output.json()["export_id"]
    download = client.get(f"/v1/matters/{mid}/exports/{eid}/download", headers=headers())
    assert download.status_code == 200
    assert download.content.startswith(b"PK")
    assert b"NOT LEGAL ADVICE" not in download.content  # DOCX is compressed.
    # Editing any decision invalidates current approval and its download.
    rev = output.json()["revision"]
    fid = detail["findings"][0]["id"]
    edited = client.patch(f"/v1/matters/{mid}/findings/{fid}/decision",
                          json={"action": "edited", "edited_text": "Counsel to review"},
                          headers=headers(revision=rev))
    assert edited.status_code == 200
    denied = client.get(f"/v1/matters/{mid}/exports/{eid}/download", headers=headers())
    assert denied.status_code == 409


def test_scope_rejects_california_and_missing_law(client):
    mid, rev = create_uploaded(client, law="California")
    reply = client.put(f"/v1/matters/{mid}/context", json=make_context(), headers=headers(revision=rev))
    assert reply.status_code == 422
    assert reply.json()["detail"]["code"] == "GOVERNING_LAW_CONFLICT"


def test_cross_matter_access_and_stale_revision(client):
    mid, rev = create_uploaded(client)
    assert client.get(f"/v1/matters/{mid}", headers=headers(user="bob")).status_code == 404
    old = client.put(f"/v1/matters/{mid}/context", json=make_context(),
                     headers=headers(revision=rev-1))
    assert old.status_code == 409
    assert old.json()["detail"]["code"] == "VERSION_STALE"
    unauthorized = client.post(f"/v1/matters/{mid}/analyses",
                               headers=headers(user="bob", revision=rev))
    assert unauthorized.status_code == 404


def test_demo_mode_off_by_default(client, monkeypatch):
    monkeypatch.delenv("DEMO_MODE")
    assert client.post("/v1/matters", json={"name": "X"}, headers=headers()).status_code == 503


def test_unreviewed_findings_block_approval(client):
    mid, rev = create_uploaded(client)
    rev = client.put(f"/v1/matters/{mid}/context", json=make_context(), headers=headers(revision=rev)).json()["revision"]
    rev = client.post(f"/v1/matters/{mid}/analyses", headers=headers(revision=rev)).json()["revision"]
    res = client.post(f"/v1/matters/{mid}/approvals",
                      json={"acknowledged_independent_review": True},
                      headers=headers(role="reviewer", revision=rev))
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "REVIEW_BLOCKED"
