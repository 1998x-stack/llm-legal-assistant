# Quality & contract tests

Backend: `pytest backend/tests -q`. Frontend: `npm --prefix frontend run build` (and `npm --prefix frontend test` if dependencies have been installed). CI runs both using synthetic NDA fixtures.

Important negative paths: malformed DOCX, scanned/empty PDF, CA/NY conflict, missing NY governing law, quote verification, repeated clauses, unauthorised matter owner, non-reviewer approval, stale revision, unreviewed findings, stale export.
