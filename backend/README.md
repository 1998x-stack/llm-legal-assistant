# Backend: local-only API

`fastapi` routes are in `app/main.py`; parsing and the **non-legal demonstration** rule engine live in `app/core.py`.

```bash
pip install -r backend/requirements.txt
export APP_ENV=development DEMO_MODE=1 DATABASE_PATH=./legal_dev.sqlite3
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
pytest backend/tests -q
```

`X-Demo-User` and `X-Demo-Role` only select fake identities for local testing. Both are trivially forgeable. The backend **must be replaced with real authentication and security controls before any production use**.

OpenAPI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
