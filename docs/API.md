# API contract — local demo, not production

The API is self-documented at `http://127.0.0.1:8000/docs` with `APP_ENV=development DEMO_MODE=1`. All operations other than `/health` require a fake `X-Demo-User` and `X-Demo-Role` header **for demonstration only**. Do not expose it publicly.

## Thin-slice flow

| Step | Endpoint | Response / gate |
| --- | --- | --- |
| Create matter | POST /v1/matters | id, revision 0 |
| Upload text DOCX/PDF | POST /v1/matters/{id}/documents | document_version, hash, block count; rejects broken/scanned files |
| Confirm explicit scope | PUT /v1/matters/{id}/context | If-Match revision; fails on non-mutual and non-NY law |
| Analyze synthetic patterns | POST /v1/matters/{id}/analyses | If-Match revision; 3 coverage records and candidate prompts |
| Review each finding | PATCH /v1/matters/{id}/findings/{fid}/decision | accepted, edited, dismissed, needs_context, escalated |
| Simulate review approval | POST /v1/matters/{id}/approvals | reviewer role and acknowledged_independent_review required |
| Export approved report | POST /v1/matters/{id}/exports | fixed approval snapshot, DOCX |
| Download artifact | GET /v1/matters/{id}/exports/{eid}/download | revoked if finding is changed |
| Read audit | GET /v1/matters/{id}/audit | metadata only |

Writes that operate on an existing analysis require `If-Match` equal to the current integer matter revision. A stale revision yields 409 VERSION_STALE. Different demo users cannot access each other's matters; **this does not make demo headers secure authentication**.

Common failure codes: DEMO_DISABLED, MATTER_NOT_FOUND, UNSUPPORTED_TYPE, SCAN_PDF, PARSE_INCOMPLETE, MISSING_GOVERNING_LAW, GOVERNING_LAW_CONFLICT, OUT_OF_SCOPE, MISSING_CONTEXT, VERSION_STALE, CITATION_MISMATCH, REVIEW_BLOCKED, REVIEWER_REQUIRED, APPROVAL_REQUIRED, EXPORT_MISMATCH.

Data model and release blockers are specified in [backend architecture](https://github.com/1998x-stack/projects/blob/main/projects/professional/llm-legal-assistant/design/backend-architecture-v1.0.md). Demo SQLite storage / synchronous analysis are intentional substitutions; they are not the production design.
