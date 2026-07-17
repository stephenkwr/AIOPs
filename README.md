# AI Operations Copilot

A support-resolution copilot: ingest internal docs → answer with cited sources →
route to tools (knowledge base, order lookup, escalation) → **require human approval
before any action** → show a full trace (sources, tool calls, latency, tokens, cost,
confidence) → evaluate against a golden dataset.

Built to mirror how a company would ship this: separate frontend/backend, a real
database, CI/CD, guardrails, and a documented scaling path — all on free tiers.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design and rationale.

---

## Stack

| Layer | Tech | Host (free tier) |
|---|---|---|
| Frontend | Next.js + TypeScript | Vercel |
| Backend | FastAPI + Python 3.12 | Render |
| Database | Postgres + pgvector | Supabase |
| LLM | Gemini (default) · Groq (judge/fallback) · Claude (premium swap) | — |
| CI/CD | GitHub Actions | — |

---

## Status

Phase 0 (scaffold + CI) — backend skeleton with health probes, migrations, and CI.
Later phases add ingestion, retrieval, the agent loop, tracing, and evaluation.

---

## Local development (backend)

Prerequisites: **Python 3.12+**, **Docker** (for local Postgres).

```bash
# 1. Start Postgres (with pgvector) locally
docker compose up -d

# 2. Set up the backend
cd backend
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -e .[dev]

# 3. Configure env
cp .env.example .env        # defaults already point at the docker Postgres

# 4. Run migrations
alembic upgrade head

# 5. Run the API
uvicorn app.main:app --reload
```

Then:

- Liveness: <http://localhost:8000/healthz> → `{"status":"ok"}`
- Readiness (DB check): <http://localhost:8000/readyz> → `{"status":"ready","database":"ok"}`
- Interactive API docs: <http://localhost:8000/docs>

### Checks (what CI runs)

```bash
cd backend
ruff check .
ruff format --check .
pytest -q
```

---

## Secrets — how this maps to real practice

**Yes, a local `.env` file is the standard developer setup** — but with rules:

- **`.env` is never committed.** It's gitignored. Only `.env.example` (placeholders,
  no real values) is committed, so teammates know which variables exist.
- **In production, secrets do not live in a file.** They're injected as environment
  variables by the platform's secret store — here, the **Render dashboard**,
  **Vercel project settings**, and **GitHub Actions secrets**. Bigger companies use a
  dedicated manager (AWS Secrets Manager, HashiCorp Vault, Doppler, Infisical) that
  handles rotation and access control, and inject the values at deploy/runtime.
- The application reads everything the same way (`os.environ` via `pydantic-settings`),
  so nothing in the code changes between local and production — only *where the values
  come from* changes. That's the 12-factor "config in the environment" principle.

Rule of thumb: **if it's a secret, it goes in an ignored `.env` locally and a secret
store in the cloud — never in git.**

---

## Repository layout

```
├── ARCHITECTURE.md          # full design + rationale
├── docker-compose.yml       # local Postgres + pgvector
├── render.yaml              # backend infra-as-code (Render blueprint)
├── .github/workflows/       # CI (lint + tests) and keepalive cron
└── backend/
    ├── app/
    │   ├── main.py          # FastAPI app factory
    │   ├── config.py        # env-driven settings
    │   ├── db.py            # async engine + session
    │   ├── api/health.py    # /healthz + /readyz
    │   └── models/          # SQLAlchemy models
    ├── alembic/             # migrations
    └── tests/
```
