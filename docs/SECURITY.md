# Security and legal limits

**DO NOT DEPLOY TO THE INTERNET OR UPLOAD REAL CLIENT AGREEMENTS.** This prototype intentionally has demo identities selected by HTTP headers. They are not authentication, cannot demonstrate production multi-tenant security, and are disabled unless both `APP_ENV=development` and `DEMO_MODE=1`. Run the API on `127.0.0.1` only.

Data is stored locally in SQLite, including document bytes. There is no encryption-at-rest, secret management, customer DPA, verified backup deletion, malware sandbox, lawyer-approved playbook, OCR, external LLM, enterprise permissions or real user login. Basic ZIP guards and PDF checks are only a starting point; they are **not** malicious-document isolation.

All rules are **synthetic examples for testing technical workflows**, not New York legal determinations. The role `reviewer` is only a simulated approval role; the software does not verify bar membership. Never present exported demo documents as a lawyer's independent review.

Production blockers:
1. OIDC + MFA and server-validated membership + matter ACL (not demo role headers).
2. Containerized parser sandbox with no network; robust malware scanning and resource limits.
3. PostgreSQL transactions, immutable versioning, encrypted object storage and verifiable lifecycle/deletion.
4. Playbook reviewed by qualified counsel; golden set of authorized, de-identified NDA samples; complete citation and coverage tests.
5. Vendor privacy assessment, authorization and applicable bar ethics review before processing real contracts.
6. Threat modeling, penetration testing, sensitive-logging audit and signoff on release gates.

Report vulnerabilities privately to the repository maintainers; do not paste confidential contracts or exploit content into public GitHub Issues.
