# Engineering rollout / F01–F09

This is an implementation plan, **not** a record of production readiness.

| Stage | Deliverable | Demonstrable acceptance |
| --- | --- | --- |
| 0 | Code categories, docs, CI and synthetic fixtures | Repo structure and CI files exist |
| 1 | Document parser, stable anchors, scope gate | Unit tests reject unsupported documents/law and preserve duplicate blocks |
| 2 | Local-only API and deterministic, unapproved demonstration playbook | Contract test from upload to evidence-linked findings |
| 3 | Decisions, revision conflicts, reviewer-only approval and immutable DOCX export | Tests for impersonation limits (demo only), wrong role, stale revision and snapshot |
| 4 | React review prototype | Browser can create matter, upload, review, approve and download with synthetic NDA |
| 5 | Production hardening | **Not implemented:** OIDC, per-matter RBAC, Postgres/jobs, encrypted object store, provider DPA, lawyer-approved rules, legal/security review |

**Strict boundaries:** English, text-native mutual B2B NDA, explicit New York governing law, synthetic examples only. No real legal opinion, OCR, third-party model, automated signing or original Word Track Changes.

Source requirements: [PRD](https://github.com/1998x-stack/projects/blob/main/projects/professional/llm-legal-assistant/reports/prd-v1.0.md) · [MVP specification](https://github.com/1998x-stack/projects/blob/main/projects/professional/llm-legal-assistant/reports/mvp-functional-spec-v1.0.md).

## Next engineering gate
Run backend pytest and frontend build in GitHub Actions. Any failure blocks claims of a working prototype. Before any customer pilot, replace demo auth, SQLite storage and example playbook; conduct independent lawyer review and security assessment.
