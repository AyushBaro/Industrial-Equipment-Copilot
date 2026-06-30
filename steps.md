# Project Steps & Progress — Industrial Equipment RAG Copilot

**Read this anytime to see where you are and what's next.**
Full spec lives in `Project_Docs/PRD.md`. This file is the living checklist.

- **Status:** Phase 0 (setup) nearly done — starting Phase 1
- **Started:** 2026-06-30 (Tue)
- **Target finish:** ~Jul 15 (focused) / early Aug (part-time, evenings+weekends)
- **App LLM stack:** **OpenAI only** — chat model + OpenAI embeddings. (Claude Code is just the tool you build *with*; the app calls OpenAI.)

### Legend
✅ done · 🔄 in progress · ⬜ not started · 👤 = your job (can't delegate) · 🤖 = delegate to Claude Code

---

## Important: the OpenAI-only decision

The whole application uses the OpenAI API for every model call:

| Job in the app | Use |
|---|---|
| Answer synthesis (the copilot's replies) | OpenAI chat model — `gpt-4o` or `gpt-4.1` |
| Query routing (doc / timeseries / fusion) | cheaper `gpt-4o-mini` is fine |
| Synthetic doc generation (one-time) | `gpt-4o-mini` |
| LLM-as-judge (faithfulness scoring) | `gpt-4o` (use the stronger model to judge) |
| Embeddings (retrieval) | `text-embedding-3-small` (cheap, good); `-large` if recall is weak |

Keyword retrieval (BM25 via `rank_bm25`) and the vector store (Chroma or LanceDB,
local) are **not** model-dependent — they just store the OpenAI embeddings.
Put all model calls behind **one thin `llm_client.py` module** so the model name is
changed in exactly one place.

`.env` must contain: `OPENAI_API_KEY=...` (already added ✅)

---

## Current state snapshot (2026-06-30)

- ✅ CMAPSS data downloaded → `Data/raw/CMAPSSData/` (FD001–004 train/test/RUL, readme, + `Damage Propagation Modeling.pdf`)
- ✅ `OPENAI_API_KEY` in `.env`
- ✅ PRD written → `Project_Docs/PRD.md`
- ⬜ `git init` + first commit (repo is not yet under version control)
- ⬜ `CLAUDE.md` at repo root (project context for Claude Code)
- ⬜ Python env + dependencies
- ⬜ Verify Node 18+ / Python 3.11+ installed

---

## Phase 0 — Setup  (today, ~1 hr)

- ✅ 👤 Download CMAPSS into `Data/raw/CMAPSSData/`
- ✅ 👤 Put `OPENAI_API_KEY` in `.env`
- ⬜ 👤 Confirm Node 18+ (`node -v`) and Python 3.11+ (`python3 --version`)
- ⬜ 👤 `git init`, add `.gitignore` (must ignore `.env`, `Data/raw/`, `__pycache__/`, `.venv/`), first commit
- ⬜ 🤖 Create `CLAUDE.md` from PRD §0/§2/§3 + the OpenAI-only rule + the non-negotiables (forced citation, abstention over guessing, keep eval green)
- ⬜ 👤 Read `Data/raw/CMAPSSData/readme.txt` once so you know what the 21 sensors physically are

**Checkpoint:** repo is committed, `.env` is gitignored, `CLAUDE.md` exists.

---

## Phase 1 — Data foundation  (Jun 30 – Jul 1)

- ⬜ 🤖 Set up Python project (`pyproject.toml`/`requirements.txt`, `.venv`): `openai`, `duckdb`, `pandas`, `chromadb` (or `lancedb`), `rank_bm25`, `fastapi`, `uvicorn`, `streamlit`, `python-dotenv`, `pytest`, `pypdf`
- ⬜ 🤖 DuckDB loader for **FD001 only** — parse the space-delimited file into a table (`unit_number`, `time_in_cycles`, `op_setting_1..3`, `sensor_1..21`)
- ⬜ 🤖 Identify & document the flat/constant sensors in FD001 (drop or flag them)
- ⬜ 🤖 Build the **asset hierarchy table** (sensor → subsystem → physical quantity → unit → nominal range → alarm threshold) as the single source of truth
- ⬜ 🤖 Generate **15–25 synthetic maintenance docs** (manuals, work orders, fault-code reference) grounded in the asset hierarchy + `readme.txt`; keep the generation script in the repo
- ⬜ 🤖 Optionally extract text from `Damage Propagation Modeling.pdf` as a real grounding doc
- ⬜ 👤 Spot-check: pull one engine's sensor curve and confirm it looks like degradation; skim 2–3 generated docs for consistency with real sensor IDs

**Checkpoint:** you can query "engine 1, sensor 4, last 50 cycles" and get real numbers; docs reference real sensor IDs and consistent thresholds.

---

## Phase 2 — Baseline RAG (documents only)  (Jul 2 – Jul 3)

- ⬜ 🤖 Chunk docs; embed with `text-embedding-3-small`; store in Chroma/LanceDB
- ⬜ 🤖 Hybrid retrieval: dense (embeddings) + BM25 keyword
- ⬜ 🤖 Synthesis with OpenAI chat model, **forced citations** (every claim → chunk id)
- ⬜ 👤 Ask 5 doc questions by hand; confirm answers cite real chunks
- ⬜ ⚠️ Do **NOT** add the router or time-series yet — get this working end-to-end first

**Checkpoint:** doc-only Q&A works with citations.
*(Weekend Jul 4–5: buffer / rest.)*

---

## Phase 3 — Structured tool + router  (Jul 6 – Jul 7)

- ⬜ 🤖 Time-series query tool over DuckDB (trends, last-N-cycles, threshold checks) joined to the asset hierarchy
- ⬜ 🤖 Routing layer (OpenAI tool/function calling): classify → doc-lookup / timeseries-lookup / fusion, then dispatch
- ⬜ 🤖 Fusion synthesis: combine telemetry + retrieved docs into one grounded, cited answer
- ⬜ 🤖 Abstention path: low retrieval confidence / out-of-scope → "I don't have enough information"
- ⬜ 👤 Test 3 fusion questions manually (e.g. "engine 47, sensor 11 elevated — known fault + procedure?")

**Checkpoint:** a fusion query returns a synthesized answer pulling from **both** sources.

---

## Phase 4 — Golden eval set  (Jul 8 – Jul 9)  👤 YOUR WORK, UNSKIPPABLE

- ⬜ 🤖 Define the eval data format (question, correct answer, correct source ids, category, answerable?)
- ⬜ 👤 Hand-label **40–60 Q/A pairs** across all 3 query types
- ⬜ 👤 Add **5–10 out-of-scope / unanswerable** questions (to test abstention)
- ⬜ 👤 Label the correct source(s) for each (which doc chunk and/or which sensor query)

> This is tedious and it's the entire differentiator. Claude can suggest *candidate*
> questions, but **you verify every label.** Block the time; don't rush it.

**Checkpoint:** 40–60 verified labeled pairs + abstention cases committed.

---

## Phase 5 — Automated scoring + iterate  (Jul 10, 13)

- ⬜ 🤖 Scoring code: retrieval precision/recall@k, routing accuracy, abstention rate
- ⬜ 🤖 Faithfulness scorer = LLM-as-judge (`gpt-4o`)
- ⬜ 👤 Hand-label faithfulness on ~15 examples; compare to the judge → report agreement rate (≥0.85 = trustworthy)
- ⬜ 🤖 Wire eval into a **pytest regression test** that runs on every change
- ⬜ 👤 Run the first full eval → record the **baseline** numbers (don't fix anything yet)
- ⬜ 🤖 Iterate retrieval on what eval reveals (chunking, hybrid weights, k)
- ⬜ 👤 Pick 1–2 real failures to write up as a mini case study

**Checkpoint:** a numbers table exists + at least **one documented before/after improvement**.

---

## Phase 6 — Deploy + README  (Jul 14 – Jul 15)

- ⬜ 🤖 FastAPI backend exposing the copilot
- ⬜ 🤖 Streamlit/Gradio UI
- ⬜ 🤖 Cost/latency logging per query (track OpenAI token usage)
- ⬜ 👤 Write README intro (Cognite-style problem statement) + the failure case study in your own voice
- ⬜ 🤖 Assemble README: eval table + architecture diagram **front and center**, then setup/run + synthetic-data transparency note

**Checkpoint:** demo runs end-to-end; README leads with results.

---

## Benchmarks — measure baseline (Phase 5 first run), then beat it

| Metric | Baseline (just record) | Final target |
|---|---|---|
| Retrieval recall@5 | ___ | ≥ 0.80 |
| Routing accuracy | ___ | ≥ 0.90 |
| Faithfulness | ___ | ≥ 0.85 |
| Correct abstention rate | ___ | ≥ 0.90 |
| LLM-judge ↔ your hand labels | — | ≥ 0.85 |

**The strongest portfolio artifact is the delta**, e.g. "recall@5 0.62 → 0.84 after
switching to hybrid retrieval." Record the date + the change that caused each jump.

---

## 👉 RIGHT NOW, DO THIS NEXT

1. 👤 Run `node -v` and `python3 --version` to confirm versions.
2. 👤 `git init` + add a `.gitignore` that excludes `.env` and `Data/raw/`, then commit.
3. 🤖 Ask Claude Code: *"Read Project_Docs/PRD.md and steps.md. Create CLAUDE.md, then do Phase 1: set up the Python env (OpenAI-only stack), write the DuckDB loader for FD001, build the asset hierarchy table, and generate the synthetic docs. Show me a plan before writing code."*

> The 3 ways people fail this: (1) rushing the hand-labeled eval set, (2) building the
> router before the doc-only baseline works, (3) trusting the LLM judge without
> validating it. Don't.
