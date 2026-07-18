# AI Operations

A support-resolution copilot, built end-to-end the way a company would ship it:

- **Ingest** internal docs (PDF / HTML / CSV / Markdown) → parse → chunk → embed
- **Answer** support questions with **inline citations** back to the exact source chunk
- **Act** through tools — search the knowledge base, look up orders, create escalation
  tickets — with **human approval required before any side-effect runs**
- **Trace** every run: each LLM call, tool call, and approval with latency, tokens,
  cost, and a decomposed confidence score
- **Evaluate** against a version-controlled golden dataset (72 questions incl. an
  unanswerable slice) with retrieval metrics, cross-provider LLM-as-judge, and a
  before/after comparison UI

Separate frontend/backend, real Postgres, CI/CD with a retrieval-regression gate,
per-IP rate limits, and a documented scaling path — all on free tiers.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design and rationale.

---

## The headline result

Same golden dataset, two retrieval configurations (live Gemini embeddings):

| Metric | keyword-only (baseline) | hybrid (production) | Δ |
|---|---:|---:|---:|
| Retrieval hit@8 | 6.7% | **100.0%** | **+93.3%** |
| MRR | 0.07 | **0.97** | +0.90 |

Lexical search collapses on natural-language questions (`plainto_tsquery` needs every
term to match); embeddings capture meaning, and RRF fusion keeps keyword's exact-match
strength for IDs and SKUs. The Evaluation page reproduces this table on demand.

---

## Stack

| Layer | Tech | Host (free tier) |
|---|---|---|
| Frontend | Next.js 15 + TypeScript + TanStack Query | Vercel |
| Backend | FastAPI + Python 3.12 + SQLAlchemy 2 (async) | Render |
| Database | Postgres 16 + pgvector | Supabase |
| LLM | Gemini (answers) · Groq/Llama (fallback + judge) · Claude (premium swap) | — |
| CI/CD | GitHub Actions (lint, tests, typecheck, build, smoke-eval) | — |

---

## What's inside

| Page | What it shows |
|---|---|
| **Documents** | Upload + live ingestion status (parse → chunk → embed → ready). One-click **“Load demo data”** seeds a 12-doc support KB. |
| **Copilot** | Agent chat: cited answers, tool activity trail, and the **approval card** when the agent wants to create an escalation — approve or reject, the run resumes either way. |
| **Traces** | Every run (chat + agent) with a **step-by-step latency waterfall**, expandable tool payloads, token/cost accounting, and the confidence breakdown. |
| **Evaluation** | Launch eval runs (keyword / vector / hybrid, optionally LLM-judged), drill into per-question results, and compare any two runs **before/after** with deltas. |
| **Escalations** | Tickets the copilot created — each one passed through human approval. |

Engineering details worth a look:

- **Durable agent loop** — a DB-backed state machine (`running → awaiting_approval →
  completed/failed/cancelled`). Message history is serialized to `runs.agent_state`,
  so an approval can arrive hours later and any replica can resume the run.
- **Guardrails as hard budgets** — max steps, token ceiling, tool timeouts + retries,
  argument validation, approval expiry. Every failure ends the run cleanly and hands
  control back to a human.
- **Provider fallback** — Gemini 503s? The same request transparently retries on Groq.
  The UI reports which model actually served.
- **Hermetic by default** — with no API keys, an offline hashing embedder and a
  deterministic fake LLM drive the entire stack (dev, CI, tests). Chunks carry an
  embedder provenance stamp, so switching providers later triggers automatic
  re-embedding instead of silent vector-space mismatch.
- **Cross-provider judging** — the eval never lets a model grade its own answers
  (Gemini answers, Llama judges).
- **CI smoke-eval** — a hermetic before/after runs on every push; if hybrid retrieval
  stops beating the baseline or drops below hit@8 ≥ 0.9, the build fails.

---

## Local development

Prerequisites: **Python 3.12+**, **Node.js 20+**, **Docker** (for local Postgres).

```bash
# 1. Database
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env          # defaults point at the docker Postgres
alembic upgrade head
uvicorn app.main:app --reload # http://localhost:8000  (docs at /docs)

# 3. Frontend (new terminal)
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE_URL → the backend URL
npm run dev                        # http://localhost:3000
```

Open <http://localhost:3000/documents> → **Load demo data** → ask the Copilot
*“How do I reset my password?”*.

> **No API keys needed locally.** Everything runs on the offline embedder + fake LLM.
> Add `GEMINI_API_KEY` (and optionally `GROQ_API_KEY`) to `backend/.env` for real
> answers — existing demo/eval docs re-embed automatically on next use.

Checks (what CI runs):

```bash
cd backend  && ruff check . && ruff format --check . && pytest -q
cd frontend && npm run typecheck && npm run build
```

After backend contract changes, regenerate the typed client:
`cd frontend && npm run gen:api`.

---

## Deployment (free tiers)

Three services, in this order. Each step is dashboard-only — no CLI needed.

### 1. Supabase (database)

1. [supabase.com](https://supabase.com) → New project (free plan). Pick a region close
   to Render's (e.g. Singapore). Save the database password.
2. SQL Editor → run `create extension if not exists vector;`
3. Project Settings → Database → copy **two** connection strings:
   - **Transaction pooler** (port `6543`) → becomes `DATABASE_URL`
   - **Direct connection** (port `5432`) → becomes `DATABASE_URL_DIRECT` (migrations)
4. Convert both to the async driver: replace `postgresql://` with
   `postgresql+asyncpg://`.

### 2. Render (backend)

1. [render.com](https://render.com) → New → **Blueprint** → connect the GitHub repo.
   Render reads [render.yaml](render.yaml) and creates the `copilot-backend` service.
2. Set the environment variables it prompts for:
   - `DATABASE_URL` / `DATABASE_URL_DIRECT` — from Supabase (step 1)
   - `CORS_ORIGINS` — your Vercel URL (add after step 3; start with `*` temporarily)
   - `GEMINI_API_KEY`, `GROQ_API_KEY` — from [aistudio.google.com](https://aistudio.google.com/apikey) and [console.groq.com](https://console.groq.com/keys)
3. Deploy. Migrations run automatically on start (`alembic upgrade head`).
   Verify: `https://<service>.onrender.com/readyz` → `{"status":"ready"}`.
4. Optional: add a GitHub Actions secret `BACKEND_READY_URL` pointing at `/readyz` —
   the [keepalive workflow](.github/workflows/keepalive.yml) pings it so the free
   instance cold-starts less often.

### 3. Vercel (frontend)

1. [vercel.com](https://vercel.com) → Add New → Project → import the repo.
   Set **Root Directory = `frontend`** (framework auto-detects Next.js).
2. Environment variable: `NEXT_PUBLIC_API_BASE_URL` = the Render URL
   (`https://<service>.onrender.com`, no trailing slash).
3. Deploy, then go back to Render and set `CORS_ORIGINS` to the exact Vercel URL
   (`https://<project>.vercel.app`).
4. Open the site → Documents → **Load demo data** → done.

### Free-tier caveats (by design, documented not hidden)

- **Render free spins down after ~15 min idle** — first request after a nap takes
  ~30–60 s. The keepalive cron reduces this; a paid instance removes it.
- **Uploaded raw files live on the instance disk** (ephemeral). Chunks + embeddings
  are in Postgres, so search/answers survive restarts; only re-parsing an original
  file wouldn't. The storage layer is a 3-method interface — swapping in Supabase
  Storage is the documented next step.
- **Per-IP rate limits** protect the free LLM quotas (chat/agent 20/min, uploads
  20/min, eval runs 10/hour, demo seed 10/hour).

---

## Secrets — how this maps to real practice

**Yes, a local `.env` file is the standard developer setup** — but with rules:

- **`.env` is never committed.** Only `.env.example` (placeholders, no real values)
  is committed, so teammates know which variables exist.
- **In production, secrets do not live in a file.** They're injected as environment
  variables by the platform's secret store — the **Render dashboard**, **Vercel
  project settings**, **GitHub Actions secrets**. Bigger companies use a dedicated
  manager (AWS Secrets Manager, Vault, Doppler) that adds rotation and access control.
- The application reads everything the same way (`pydantic-settings`), so nothing in
  code changes between local and production — only *where values come from* changes.
  That's the 12-factor "config in the environment" principle.

---

## Repository layout

```
├── ARCHITECTURE.md            # full design + rationale
├── docker-compose.yml         # local Postgres + pgvector
├── render.yaml                # backend infra-as-code (Render blueprint)
├── .github/workflows/         # CI (lint/tests/build/smoke-eval) + keepalive cron
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app factory
│   │   ├── config.py          # env-driven settings
│   │   ├── limits.py          # per-IP rate limits
│   │   ├── api/               # health, documents, chat, agent, approvals, ops, eval, demo
│   │   ├── core/
│   │   │   ├── ingestion/     # parsers, chunker, embedder (+provenance), pipeline
│   │   │   ├── retrieval/     # hybrid retriever (pgvector + FTS + RRF)
│   │   │   ├── agent/         # the durable agent loop (approval gate lives here)
│   │   │   ├── llm/           # provider adapters + fallback chain + fake
│   │   │   └── eval/          # golden dataset, metrics, judge, runner, seeder
│   │   ├── tools/             # kb_search, order_lookup, create_escalation
│   │   └── models/            # SQLAlchemy models
│   ├── eval/                  # version-controlled corpus (12 docs) + dataset.json (72 Qs)
│   ├── alembic/               # migrations
│   └── tests/                 # 56 hermetic tests (incl. the CI smoke-eval)
└── frontend/
    ├── app/                   # documents, copilot, traces, evals, escalations
    ├── components/            # approval card, trace waterfall, compare panel, …
    └── lib/api/               # typed client generated from the backend OpenAPI schema
```
