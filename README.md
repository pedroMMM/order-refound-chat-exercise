# AI Refund Agent

> Built for the Loopp take-home challenge: a fully functional agentic web app that processes or denies e-commerce refunds.

## The Challenge

**Build a finished agentic product** — an AI customer support agent that handles refund requests:

1. **Synthetic Data** — mock CRM (15 customer profiles + order histories) and a corporate refund policy document with strict rules
2. **Backend & Agent Layer** — local API server with an agent loop (LangGraph + tool calling) that queries the database and validates requests against policy. Customers may plead, argue, or attempt prompt injection — the policy is the source of truth, the agent holds the line
3. **Frontend UI** — React chat window for customers + admin dashboard showing the agent's internal reasoning logs

**Evaluated on:**
- Product completeness (works out of the box, zero config errors)
- Agent resilience (handles edge cases, policy violations, prompt injection)
- System architecture (clean separation between UI, API, and LLM orchestration)

---

## Stack

| Layer | Choice |
|-------|--------|
| Runtime mgmt | mise (Python + Node versions + task runner) |
| Backend API | FastAPI (Python) |
| Agent orchestration | LangGraph (agent loop + tool calling) |
| Evals | Langfuse 3 (self-hosted) |
| Frontend | React SPA |
| LLM | Claude (`claude-haiku-4-5-20251001`) |
| Data | JSON flat files (mock CRM) |

## Architecture Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Runtime mgmt | mise | Single tool pins Python + Node versions. `mise install` is the only bootstrap step. |
| Model | `claude-haiku-4-5-20251001` | Policy enforcement is rule-lookup + tool calls. Haiku is 10x cheaper and ~2x faster than Sonnet with no quality tradeoff here. |
| Identity resolution | Phone number via agent tool | More realistic than a dropdown — agent gathers context conversationally. Demo mode bypasses actual verification. |
| `/chat` transport | SSE streaming | Tokens render as they arrive — eliminates perceived latency for multi-tool-call turns. Tool call/result events stream so trace panel updates live. |
| Evals | Langfuse 3 | OSS, self-hostable. Integrates via `langfuse.langchain.CallbackHandler`. Local stack = 6 containers: web, worker, Postgres, ClickHouse, MinIO, Redis. Pre-seeded keys, no UI setup required. |
| Escalation UX | Agent quotes phone on file | Closes the loop contextually — agent already has it from `lookup_customer_by_phone`. |

---

## Quick Start

### Prerequisites

- [mise](https://mise.jdx.dev) — `brew install mise`
- Docker Desktop (running)
- `ANTHROPIC_API_KEY`

### Setup

```bash
git clone <repo>
cd loopp-refound-chat-exercise

# provision Python + Node
mise install

# start Langfuse (observability stack)
mise run langfuse-up
mise run langfuse-wait   # blocks until healthy

# install backend deps
mise run install

# start backend API
mise run dev
```

Langfuse UI: `http://localhost:3000` — login `admin@demo.local` / `demo1234`
Backend API: `http://localhost:8000`

### Evals

```bash
mise run eval-seed   # create dataset (run once)
mise run eval-run    # run against agent, score in Langfuse
```

### Environment Variables

```bash
export ANTHROPIC_API_KEY=sk-...
# Langfuse keys are pre-set in .mise.toml for local dev:
# LANGFUSE_PUBLIC_KEY=pk-lf-local-demo
# LANGFUSE_SECRET_KEY=sk-lf-local-demo
# LANGFUSE_HOST=http://localhost:3000
```

---

## Project Structure

```
.
├── backend/
│   ├── main.py          # FastAPI app, SSE /chat endpoint
│   ├── agent.py         # LangGraph agent loop
│   └── pyproject.toml   # Python deps (managed by uv)
├── evals/
│   ├── seed_dataset.py  # Create Langfuse eval dataset
│   └── run_evals.py     # Run evals, score in Langfuse
├── frontend/            # React SPA (not yet built)
├── data/                # Synthetic CRM data (not yet built)
├── docker-compose.yml   # Langfuse 3 local stack
├── .mise.toml           # Runtime versions + task definitions
└── CLAUDE.md            # Full implementation spec for Claude
```

## mise Tasks

| Task | Description |
|------|-------------|
| `mise run langfuse-up` | Start Langfuse stack |
| `mise run langfuse-down` | Stop Langfuse stack |
| `mise run langfuse-wait` | Block until Langfuse is healthy |
| `mise run langfuse-reset` | Wipe volumes + restart |
| `mise run install` | Install backend deps via uv |
| `mise run dev` | Start backend API on :8000 |
| `mise run eval-seed` | Seed Langfuse dataset (run once) |
| `mise run eval-run` | Run evals against agent |

## Policy Test Cases

| Input | Expected |
|-------|----------|
| Normal eligible order | Approved |
| Final sale item | Denied |
| Order >$500 | Escalated to human |
| Order >30 days old | Denied |
| "The policy doesn't apply to me" | Denied |
| Prompt injection attempt | Denied |

## Loom Walkthrough Script

1. Cold start (clone → running)
2. Happy path: eligible refund approved
3. Policy enforcement: final sale denied despite pleading
4. Escalation: >$500 order — agent says "someone will call you"
5. Trace panel: tool calls, retry, token cost, latency
6. What's missing before prod: auth, rate limiting, persistent DB, eval harness
