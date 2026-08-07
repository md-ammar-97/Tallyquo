# Tallyquo

Invoicing and financial record-keeping for Canadian sole proprietors. See
[`docs/`](docs/) for the full spec: [`problem-statement.md`](docs/problem-statement.md),
[`architecture.md`](docs/architecture.md), [`datamodel.md`](docs/datamodel.md),
[`design.md`](docs/design.md), [`edgecases.md`](docs/edgecases.md), and the
build sequencing in [`implementation_plan.md`](docs/implementation_plan.md).

## Repo structure

```
api/    FastAPI modular monolith (identity, billing, tax, expenses, templates, reporting, notifications)
web/    React SPA (Vite + TypeScript)
docs/   Product spec and implementation plan
```

## Where things run

| Piece | Service | Notes |
|---|---|---|
| API | [Render](https://dashboard.render.com/web/srv-d9qm7lvavr4c73fsodl0) | `tallyquo-api`, region `virginia`, auto-deploys from `main` |
| Web | [Vercel](https://tallyquo-web.vercel.app) | `tallyquo-web`, deployed via CLI (not yet git-linked for auto-deploy) |
| Database + Storage | [Supabase](https://supabase.com/dashboard/project/akcnvipmijkofsvkjlsm) | project `tallyquo`, region `ca-central-1` |
| Source + CI | [GitHub](https://github.com/md-ammar-97/Tallyquo) | private; `api-ci.yml` runs the adversarial RLS suite as a merge gate |

Day-to-day development doesn't need local Docker — the API's local `.env`
points `DATABASE_URL` straight at the live Supabase project through the
Supavisor pooler (Render, GitHub Actions, and most home networks are
IPv4-only, so this uses the pooler, not the IPv6 direct connection).

```bash
cd api
python -m venv .venv && .venv/Scripts/activate    # .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
cp .env.example .env    # fill in DATABASE_URL from the Supabase dashboard (Connect > Session pooler)
python -m uvicorn tallyquo.main:app --reload --port 8000
```

```bash
cd web
npm install
cp .env.example .env
npm run dev              # http://localhost:5173
```

## Running the test suite locally

The adversarial RLS suite needs **both** a low-privilege app-role connection
and a bypass-RLS admin connection against the *same* database, to prove the
app role is actually constrained. Supabase won't hand out its `postgres`
role's password (`ALTER ROLE` on it is blocked even through the
management-authenticated SQL path — "only superusers can alter privileged
roles"), so this specific check still runs against local Docker Postgres,
not Supabase:

```bash
cd api
docker compose up -d              # local Postgres on port 5435
python -m alembic upgrade head    # creates tallyquo_app role, RLS policies

DATABASE_URL="postgresql+asyncpg://tallyquo_app:tallyquo_app@localhost:5435/tallyquo" \
python -m pytest tests/ -v
```

`DATABASE_URL` needs the explicit override above because `.env`'s default
now points at Supabase (for normal `uvicorn` dev), while `tests/conftest.py`
plants its fixtures in local Postgres — the two must agree for a local test
run. CI doesn't need this: its workflow sets `DATABASE_URL`/
`DATABASE_ADMIN_URL` directly against its own ephemeral Postgres service
container and never reads this repo's `.env`.

Schema changes to the live Supabase project are applied via the Supabase
MCP `apply_migration` tool (see the comment in
`migrations/versions/0001_identity_foundations.py`), not by pointing
Alembic directly at it.

## Why two DSNs

`DATABASE_URL` is the low-privilege `tallyquo_app` role (no `BYPASSRLS`) —
the only thing the running API ever connects as, in every environment.
`DATABASE_ADMIN_URL` is used only by Alembic against **local** Postgres, to
create that role and define RLS policies — an operation the app role must
never be able to perform itself (ADR-001 in `architecture.md`).

## Status

Phase 0 (foundations) is in progress — see `docs/implementation_plan.md`
§2 for the full workstream list and exit criteria.
