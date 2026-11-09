# Frontend: synthetic contract review

React + TypeScript + Vite development UI. It drives the local demo API with an explicit simulated `reviewer` or `preparer` header.

```bash
cd frontend
npm ci
npm run dev
npm run build
```

The Vite proxy forwards `/v1` to `http://127.0.0.1:8000`. Never expose this demo publicly. No claim of production security, legal advice or lawyer verification is made.

Browser E2E: after creating `../synthetic-mutual-nda.docx`, run `npm exec -- playwright install chromium` and `npm run test:e2e` from `frontend/`. Never use real client agreements in these tests.
