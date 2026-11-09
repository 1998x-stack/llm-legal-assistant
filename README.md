# Legal Intelligence — LLM Legal Assistant

> **Status: working local synthetic-data prototype (v0.1), subject to CI verification. NOT LEGAL ADVICE.**
>
> **Do not upload real customer contracts or deploy publicly.** The demo has forgeable HTTP identity headers, local unencrypted SQLite and a **not-lawyer-approved synthetic rule set**. There is **no external LLM** and **no production identity verification**.

A deliberately narrow technical slice of an evidence-grounded NDA review workflow for English **mutual B2B NDAs explicitly governed by New York law**. This repository validates the engineering flow: source → anchored example findings → explicit human decision → simulated approval → immutable DOCX report.

The product research, PRD and architecture are in [1998x-stack/projects](https://github.com/1998x-stack/projects/tree/main/projects/professional/llm-legal-assistant).

## Developer quickstart

Requirements: Python 3.12+, Node 22+. Run only on your own machine / loopback.

```bash
python -m pip install -r backend/requirements.txt
npm install --prefix frontend --no-audit --no-fund
python scripts/generate_synthetic_nda.py --out ./synthetic-mutual-nda.docx

# Terminal 1: local-only demo API
APP_ENV=development DEMO_MODE=1 DATABASE_PATH=./legal_dev.sqlite3 \
  uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# Terminal 2: Vite development UI (loopback only)
npm --prefix frontend run dev
```

Open http://127.0.0.1:5173, create a matter, upload the synthetic file, confirm scope, run the example checks, decide each finding, and export a DOCX with a **simulated reviewer role**.

## Repo / code categories

```text
algorithm/          Algorithm roadmap and evidence constraints
backend/
  app/core.py       Deterministic parser, scope gate, anchors, sample findings
  app/main.py       FastAPI, local SQLite state, approvals, export and audit
  tests/            Core, scope, permission, stale version and export tests
frontend/
  src/api.ts        Typed demo API client
  src/App.tsx       Review queue, source viewer, decisions, simulated approval
  src/styles.css    Responsive styling
infra/              Explicitly reserved for production hardening
tests/              Test guidance + synthetic fixtures
scripts/            Synthetic NDA generator
docs/               Roadmap, API contract, security limitations
.github/workflows/  Backend pytest, frontend typecheck/build, and Playwright browser E2E
```

## What works, and what does not

| Feature | Current state |
| --- | --- |
| Document parse and exact source blocks | Implemented for limited text-native DOCX/PDF (not hostile-file secure) |
| Jurisdiction and mutual NDA scope gate | Deterministic implementation, tested on synthetic cases |
| Risk review engine | **Three unapproved illustrative text pattern checks**; not actual legal analysis |
| Reviewer decisions and approval | Local demonstration state machine; **not a real lawyer identity check** |
| DOCX report | Synthetic only, generated from frozen snapshot; **not Word Track Changes** |
| Multi-tenant security, login, encrypted storage, background worker | **Not implemented**; developer-only |
| External LLM provider, production legal rules, lawyer validation | **Not implemented** |
| Production deployment, customer onboarding and retention | **Not implemented** |

Run tests:

```bash
python -m pytest backend/tests -q
npm --prefix frontend run build
# Full browser E2E: first generate the synthetic document and install Chromium
npm --prefix frontend exec -- playwright install chromium
npm --prefix frontend run test:e2e
```

See [Roadmap](docs/ROADMAP.md), [API](docs/API.md), [Security](docs/SECURITY.md), [Backend](backend/README.md) and [Frontend](frontend/README.md). For legal quality and customer pilots, independent counsel approval and security reviews are mandatory; synthetic unit tests are **not evidence of legal accuracy**.
