# Architecture

## System context

```text
Android ──HTTPS──► Underprice API (this repo)
                       │
                       ├── Agents: Planner → Scanner → Ensemble → Messenger
                       ├── Specialists (Ensemble only): Median → RAG → FineTuned → Judge
                       ├── Store / estimate cache
                       └── Modal GPU (private) ──► HF Hub PEFT @ revision
```

Sibling repos:

| Repo | Owns |
|------|------|
| `price-engine` | Train / eval / `publish-model --tag` → Hub adapter |
| `underprice-api` | Serving, agents, API, ops |
| `underprice-android` | Thin Compose client |

Weights promote by env pin (`ADAPTER_ID` + `REVISION`), not by Android release.

## Design principles

1. **Modular agents + separate specialist deploy units** — never a cheap monolith.
2. Cost control is **ops** (scale-to-zero, cascade gates, batch, cache, rare judge), not deleting modules.
3. **Ensemble is the only specialist orchestrator.** Scanner must not call Judge; Messenger must not call GPU.
4. **Feed is precomputed**; paste is the interactive path that may wait on GPU cold start.
5. Web/CPU image has **no torch**. GPU lives in a separate Modal image/function with **no public HTTP**.

## Agents

| Agent | Responsibility | Must not |
|-------|----------------|----------|
| Planner | Order scan → score → notify; budgets | Price items itself |
| Scanner | Allowlisted ingest → `Candidate` | Call GPU or Judge |
| Ensemble | Cascade specialists; fuse result | Own push or ingest |
| Messenger | FCM / in-app notify | Call GPU |

Phase 1 implements Ensemble + paste API; Scanner / Messenger / Planner hunt path are present as stubs with stable interfaces.

## Specialist contract

```text
estimate(candidate) -> Signal { value: float?, notes: str, source: str }
```

### Cascade (ops policy inside Ensemble)

```text
cache? → CategoryMedian → gate(ask/median)
      → RAG comps → gate
      → FineTuned GPU → fuse fair_value
      → gray zone? → LLM Judge
      → persist
```

Example thresholds (configurable):

| Gate | Default | Meaning |
|------|---------|---------|
| Median gate | `ask/median <= 0.95` | Else reject without GPU |
| Hot deal | `ask/fair <= 0.70` | Messenger-eligible |
| Gray zone | `0.70–0.90` | Optional Judge |
| Cache TTL | 14 days | Skip specialists |

**Fusion:** prefer FineTuned → RAG → median. `confidence=high` only when FineTuned ran. Always persist `stages_run`, `signals`, `early_exit_reason`.

**Deal score:** `ask / fair_value` (lower is better).

## API rules

- `GET /v1/deals` reads the store only — **never** triggers scoring.
- `POST /v1/score` is rate-limited in production; may return `202` + `job_id` when GPU is cold (Phase 1 returns `200` inline).
- GPU is invoked only via Modal `.remote()` from the FineTuned specialist.

## Infra (MVP)

| Component | Where | Scale |
|-----------|-------|-------|
| FastAPI | Modal ASGI / local uvicorn | CPU |
| Ensemble + Median | In-process with API | CPU |
| FineTuned | Modal `price_one` / `price_batch` | T4, `min=0` |
| Judge | Provider HTTPS (Phase 5) | No host |
| Store | Memory (default) or Postgres via `DATABASE_URL` | External |
| Cache | In-process + optional Modal Dict (`USE_MODAL_DICT`) | TTL |

## Failure isolation

| Failure | Mitigation |
|---------|------------|
| GPU cold start | Honest client UX; async job poll; cache |
| Specialist error | Signal with `value=None`; cascade can early-exit |
| Cost spike | Median gate, budgets, rate limits, scale-to-zero |
| Bad Hub revision | Pin previous tag; same specialist interface |

## Phase map

| Phase | Deliverable |
|-------|-------------|
| **1** | Paste + Ensemble cascade + FineTuned path + API |
| **2** | Median stats from store samples + shared Modal Dict cache |
| **3 (store + hunt)** | Postgres optional; Scanner pulls DealNews RSS (Ed week-8 feeds) → hunt persists hot deals |
| 3 (notify) | Messenger FCM |
| 4 | RAG comps |
| 5 | Judge on gray/detail |
