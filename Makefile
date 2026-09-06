.PHONY: install seed api web test eval build verify

install:
	cd backend && uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
	cd frontend && npm install

seed:
	cd backend && .venv/bin/python -c "from supportops.config import settings; from supportops.db import Database; from supportops.seed import seed_database; seed_database(Database(settings.database_path))"

api:
	cd backend && .venv/bin/uvicorn supportops.api:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest -q

eval:
	cd backend && .venv/bin/python -m evals.run

build:
	cd frontend && npm run typecheck && npm run build

verify: test eval build
