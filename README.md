# Tallyquo

Invoicing and financial record-keeping for Canadian sole proprietors. See
[`docs/`](docs/) for the full spec: [`problem-statement.md`](docs/problem-statement.md),
[`architecture.md`](docs/architecture.md), [`datamodel.md`](docs/datamodel.md),
[`design.md`](docs/design.md), [`edgecases.md`](docs/edgecases.md), and the
build sequencing in [`implementation-plan.md`](docs/implementation_plan.md).

## Repo structure

```
api/    FastAPI modular monolith (identity, billing, tax, expenses, templates, reporting, notifications)
web/    React SPA (Vite + TypeScript)
docs/   Product spec and implementation plan
```

## Running locally

### API

```bash
cd api
python -m venv .venv
.venv/Scripts/activate            # .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
cp .env.example .env

docker compose up -d              # local Postgres on port 5435
python -m alembic upgrade head    # creates tallyquo_app role, RLS policies
python -m pytest tests/ -v        # adversarial cross-tenant probe included

python -m uvicorn tallyquo.main:app --reload --port 8000
```

### Web

```bash
cd web
npm install
cp .env.example .env
npm run dev                       # http://localhost:5173
```

With both running, the SPA's home page confirms it can reach `/health` on
the API — that's Phase 0's whole job: prove the environment plumbing works
before any product feature is built on top of it.

## Why two DSNs

`DATABASE_URL` is the low-privilege `tallyquo_app` role (no `BYPASSRLS`) —
the only thing the running API ever connects as. `DATABASE_ADMIN_URL` is
used only by Alembic, to create that role and define RLS policies — an
operation the app role must never be able to perform itself (ADR-001 in
`architecture.md`). CI mirrors this: migrations run as admin, tests run
against both to prove the app role is actually constrained.

## Status

Phase 0 (foundations) is in progress — see `docs/implementation_plan.md`
§2 for the full workstream list and exit criteria.
