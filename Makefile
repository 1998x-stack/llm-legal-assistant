PYTHON ?= python3

.PHONY: install-backend install-frontend test run-api run-ui demo-file

install-backend:
	$(PYTHON) -m pip install -r backend/requirements.txt

install-frontend:
	npm install --prefix frontend --no-audit --no-fund

test:
	$(PYTHON) -m pytest backend/tests -q
	npm --prefix frontend run build

run-api:
	APP_ENV=development DEMO_MODE=1 DATABASE_PATH=./legal_dev.sqlite3 uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

run-ui:
	npm --prefix frontend run dev

demo-file:
	$(PYTHON) scripts/generate_synthetic_nda.py --out ./synthetic-mutual-nda.docx
