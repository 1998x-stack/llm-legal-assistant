# Legal Intelligence — LLM Legal Assistant

> **Status: developer-only, synthetic-data MVP implementation. Not legal advice, not production-ready.**

This repository implements a deliberately constrained technical prototype for reviewing **English mutual B2B NDAs explicitly governed by New York law**. Its purpose is to validate document anchors, safe scope checks, review decisions, immutable approvals and export consistency with **synthetic documents**. The sample playbook is *not approved by a lawyer* and must not be used for actual legal review.

See the [research, PRD and engineering design](https://github.com/1998x-stack/projects/tree/main/projects/professional/llm-legal-assistant) for product rationale. The code, tests and documentation are organized by algorithm, backend, frontend, infrastructure and quality checks. See [implementation plan](docs/ROADMAP.md) and [security limits](docs/SECURITY.md).

**Do not upload real client contracts.** Demo authentication is intentionally local-only, and production mode fails closed until real identity, tenant isolation, data handling and lawyer review are built.
