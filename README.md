# Underprice API

Production backend for **Underprice** — an Android app that helps people spot underpriced listings by comparing asking price to an estimated fair value.

This repo owns the **API, agents, specialist orchestration, cache, and Modal GPU serving**. Model training and Hub publishing live in a separate research repo (`price-engine`); this service only **consumes** a versioned PEFT adapter.

## What it proves

- Modular **planner → scanner → ensemble → messenger** agents (stubs allowed; boundaries are not)
- Ensemble **cascade** of specialists: CategoryMedian → RAG → FineTuned (Hub LoRA) → LLM Judge
- FastAPI surface for paste scoring and a precomputed deal feed
- GPU specialist as a **private** Modal function (T4, scale-to-zero) — not a public HTTP endpoint

## Quick start

```bash
cd underprice-api
uv sync --extra dev
cp .env.example .env

# Score one listing without HTTP
uv run underprice score-once --title "Sony WH-1000XM5" --ask 198 --category headphones

# Hunt DealNews RSS → score → feed
uv run underprice hunt --limit 3

# Run API locally
uv run underprice serve
# → http://127.0.0.1:8000/docs
```

```bash
curl -s http://127.0.0.1:8000/v1/score \
  -H 'content-type: application/json' \
  -d '{"title":"Sony WH-1000XM5","ask":198,"category":"headphones"}' | jq
```

## API (v1)

| Method | Path | Behavior |
|--------|------|----------|
| `POST` | `/v1/score` | Paste path — run Ensemble cascade |
| `GET` | `/v1/score/{job_id}` | Poll async job (used when GPU is cold/queued) |
| `GET` | `/v1/deals` | Precomputed feed only — **never** scores |
| `GET` | `/v1/deals/{id}` | Detail + specialist signals |
| `POST` | `/v1/hunt` | DealNews RSS scan → Ensemble → persist hot deals |
| `PUT` | `/v1/prefs` | Watchlist preferences |
| `POST` | `/v1/devices` | Register FCM token |

## Hub consumer contract

| Field | Value |
|-------|--------|
| Base | `meta-llama/Llama-3.2-3B` |
| Adapter | `benifa/list-price-qlora` (configurable) |
| Revision | pin via `UNDERPRICE_ADAPTER_REVISION` |
| Prompt | question + title/description + `Price is $` |
| Domain | English product text, roughly **$1–$999** |

Local/dev defaults to a deterministic heuristic so the API and tests run without GPU. Set `UNDERPRICE_USE_MODAL_GPU=true` after deploying the Modal function.

## Deploy GPU specialist

```bash
uv sync --extra modal
modal secret create underprice-secrets \
  HF_TOKEN=... \
  UNDERPRICE_ADAPTER_ID=benifa/list-price-qlora \
  UNDERPRICE_ADAPTER_REVISION=v0.1.0 \
  UNDERPRICE_BASE_MODEL=meta-llama/Llama-3.2-3B

modal deploy src/underprice/modal/gpu_pricer.py
```

## Layout

```
src/underprice/
  api/           FastAPI (CPU image — no torch)
  agents/        Planner, Scanner, Ensemble, Messenger
  specialists/   Median, RAG, FineTuned, Judge
  cache/         Estimate cache
  store/         MemoryStore or Postgres (DATABASE_URL)
  cache/         In-process + optional Modal Dict
  modal/         Private T4 price_one / price_batch
docs/
  ARCHITECTURE.md
  INTERVIEW.md
```

## Tests

```bash
uv run pytest
uv run ruff check src tests
```

## Docs

- [Architecture](docs/ARCHITECTURE.md) — boundaries, cascade, infra
- [Interview walkthrough](docs/INTERVIEW.md) — how to present this repo

## License

MIT
