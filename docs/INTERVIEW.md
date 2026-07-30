# Interview walkthrough — Underprice API

## 30-second pitch

Underprice scores whether a listing is underpriced. I split **research** (`price-engine` publishes a versioned LoRA) from **production** (this API). The backend is modular agents with an Ensemble that cascades cheap specialists before a scale-to-zero GPU model — so architecture stays clean while ops keep the bill around tens of dollars a month.

## 2-minute architecture

1. Android paste hits `POST /v1/score`.
2. Planner (or API) calls **Ensemble** — never the GPU directly.
3. Ensemble: cache → category median gate → RAG (later) → FineTuned Hub adapter on Modal T4 → optional Judge.
4. Result includes `fair_value`, `deal_score = ask/fair`, `confidence`, `stages_run`, and per-specialist `signals`.
5. Hunt feed is a separate path: cron → Scanner → Ensemble batch → DB → Messenger. Scroll never wakes the GPU.

## Hardest decision (and rejected alternative)

**Decision:** Keep agents and specialists as separate modules; control cost with cascade + scale-to-zero.

**Rejected:** Collapse into one “score” function that always runs the LLM to “ship faster / save money.”

**Why:** A monolith makes GPU the default path, couples ingest to pricing, and makes it hard to explain or evolve specialists. Cascade lets median reject obvious non-deals for free; GPU stays rare. Stubs are fine; deleting boundaries is not.

## Test / eval strategy

- Unit tests pin cascade behavior: median gate skips GPU; gray zone records Judge stage; cache hits skip specialists.
- API tests cover paste → job poll and “feed never scores.”
- Model quality lives upstream: Hub revision pinned after `price-engine` eval; this service treats the specialist as a versioned dependency.

## Cost / latency notes

| Path | Expectation |
|------|-------------|
| Paste | User may wait on T4 cold start (~30–90s MVP) |
| Feed | Precomputed; list endpoint is a DB read |
| GPU | T4 `min_containers=0`; no 24/7 warm |

Levers that do **not** change architecture: warm policy, gate thresholds, batch cadence, cache TTL, judge rarity.

## Follow-ups you should be ready for

1. Why not put the model on-device?
2. How do you prevent Scanner from calling the Judge?
3. What happens when the new Hub revision is worse?
4. How would you add RAG without rewriting Ensemble?
5. How do you rate-limit paste abuse without blocking hunt?

## What I'd improve at 10×

- Postgres + Cursor-based feed; Redis/Modal Dict cache
- RAG comps with metadata filters + small golden eval set
- Async `202` score jobs with stage streaming for Android UX
- Daily GPU/judge budget meters in Planner
- Baseline profiles / tracing per stage for p95 latency
