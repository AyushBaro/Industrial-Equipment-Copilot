# CLAUDE.md — Project context for Claude Code

## What this project is
An **Industrial Equipment RAG Copilot** that answers maintenance/troubleshooting
questions by **fusing three heterogeneous data sources** into single, grounded,
cited answers:
1. **Time-series sensor telemetry** — NASA CMAPSS turbofan data (`Data/raw/CMAPSSData/`)
2. **Structured asset hierarchy** — synthetic: sensor → subsystem → nominal range
3. **Unstructured maintenance docs** — synthetic, grounded in the real sensor schema

Modeled on Cognite's product problem (heterogeneous industrial data made queryable
via a trustworthy copilot for troubleshooting / root-cause analysis). The domain has
**near-zero tolerance for hallucination** — that constraint drives every design call.

Full spec: `Project_Docs/PRD.md`. Living progress checklist: `steps.md` (keep it
updated as phases complete).

## Non-negotiables (these are the point of the project)
- **Forced citation** — every answer cites its evidence (which doc chunk and/or which
  sensor query produced each claim).
- **Abstention over guessing** — when retrieval confidence is low or a question is
  out of scope, return "I don't have enough information." An ungrounded answer is a
  worse failure than no answer.
- **Everything is measured** — changes must keep the eval suite green; report
  before/after deltas on the eval metrics.
- **Synthetic docs must stay consistent** with the asset-hierarchy table (sensor IDs,
  subsystems, thresholds). The asset hierarchy is the single source of truth.

## Model stack — OpenAI ONLY
The application uses the **OpenAI API for every model call**. (Claude Code is only the
build tool; the app does not call Anthropic.) Route all calls through one thin
`llm_client.py` so model names live in one place.

| Job | Model |
|---|---|
| Answer synthesis | `gpt-4o` or `gpt-4.1` |
| Query routing (doc/timeseries/fusion) | `gpt-4o-mini` |
| Synthetic doc generation (one-time) | `gpt-4o-mini` |
| LLM-as-judge (faithfulness) | `gpt-4o` |
| Embeddings | `text-embedding-3-small` (use `-large` only if recall is weak) |

Secrets: `OPENAI_API_KEY` is in `.env` (gitignored). Load via `python-dotenv`.

## Tech stack
- Python 3.13, OpenAI SDK
- Telemetry store: **DuckDB** (SQL over the CMAPSS files)
- Vector store: **Chroma** (or LanceDB), local
- Keyword retrieval: **BM25** (`rank_bm25`) — combined with dense embeddings (hybrid)
- API: **FastAPI** · UI: **Streamlit/Gradio**
- Eval/tests: **pytest**

## Data layout
- `Data/raw/CMAPSSData/` — CMAPSS files: `train_FD00X.txt`, `test_FD00X.txt`,
  `RUL_FD00X.txt`, `readme.txt`, `Damage Propagation Modeling.pdf`. **Gitignored.**
- Start with **FD001 only** (1 operating condition, 1 fault mode). Some sensors are
  flat/constant in FD001 — identify and drop/flag them, and document which.
- CMAPSS schema (space-delimited, no header):
  `unit_number, time_in_cycles, op_setting_1..3, sensor_1..21`

## Workflow expectations
- **Plan before coding** — for each phase, propose a plan and get approval first.
- **One milestone at a time** — get each phase working end-to-end before the next.
  In particular: build the docs-only baseline RAG **before** adding the router or
  time-series tool.
- **Commit often** so eval before/after deltas are visible in history.
- Keep `steps.md` checkboxes current as work completes.

## Build phases (see steps.md for the live checklist)
0. Setup — DONE
1. Data foundation (DuckDB loader, asset hierarchy, synthetic docs)
2. Baseline RAG (documents only, with citations)
3. Structured time-series tool + query router + abstention
4. Golden eval set (40–60 hand-labeled Q/A pairs + abstention cases)
5. Automated scoring (retrieval/faithfulness/routing/abstention) + regression test
6. Deploy (FastAPI + UI) + README (eval results & architecture front and center)
