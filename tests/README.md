# Quality & contract tests

Backend: `pytest backend/tests -q`. Frontend: `npm --prefix frontend run build` (and `npm --prefix frontend test` if dependencies have been installed). CI runs both using synthetic NDA fixtures.

Important negative paths: malformed DOCX, scanned/empty PDF, CA/NY conflict, missing NY governing law, quote verification, repeated clauses, unauthorised matter owner, non-reviewer approval, stale revision, unreviewed findings, stale export.

Browser end-to-end: generate `synthetic-mutual-nda.docx` via `python scripts/generate_synthetic_nda.py`, then run `npm --prefix frontend exec -- playwright install chromium` and `npm --prefix frontend run test:e2e`. The Playwright config launches the loopback-only backend and Vite server. Browser tests use synthetic documents and fake demo identities only.
