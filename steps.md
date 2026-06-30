# Project Steps & Progress — Industrial Equipment RAG Copilot

**Read this anytime to see where you are and what's next.**
Full spec lives in `Project_Docs/PRD.md`. This file is the living checklist.

- **Status:** ✅ Phase 0 & Phase 1 complete (8/8 tests green) — next: Phase 2
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
- ✅ `git init` + first commit (branch `main`, commit `eb4ac0c`)
- ✅ `.gitignore` (excludes `.env` + `Data/raw/`) and `.env.example`
- ✅ `CLAUDE.md` at repo root (project context for Claude Code)
- ✅ Node v24.2.0 / Python 3.13.4 confirmed
- ⬜ Python env + dependencies (Phase 1)

---

## Phase 0 — Setup  ✅ COMPLETE (2026-06-30)

- ✅ 👤 Download CMAPSS into `Data/raw/CMAPSSData/`
- ✅ 👤 Put `OPENAI_API_KEY` in `.env`
- ✅ 👤 Confirm Node 18+ (v24.2.0) and Python 3.11+ (3.13.4)
- ✅ 👤 `git init`, add `.gitignore` (ignores `.env`, `Data/raw/`, `__pycache__/`, `.venv/`), first commit
- ✅ 🤖 Create `CLAUDE.md` (OpenAI-only rule + non-negotiables: forced citation, abstention, keep eval green)
- ✅ 👤 Read `Data/raw/CMAPSSData/readme.txt`

**Checkpoint:** ✅ repo committed (`main`/`eb4ac0c`), `.env` gitignored, `CLAUDE.md` exists.

---

## Phase 1 — Data foundation  ✅ COMPLETE (2026-06-30)

- ✅ 🤖 Python project + `.venv` + pinned `requirements.txt` (OpenAI-only stack)
- ✅ 🤖 DuckDB loader for **FD001** — train (100 engines, 20631 rows), test, and true RUL tables
- ✅ 🤖 Flat-sensor detection (SNR / drift-based) → canonical constant set `{1,5,6,10,16,18,19}`
- ✅ 🤖 **Asset hierarchy** (`build/asset_hierarchy.csv`) — 21 sensors → subsystem, data-derived nominal range + alarm threshold/direction. Single source of truth.
- ✅ 🤖 **19 Claude-authored maintenance docs** in `data/corpus/` (7 manuals, 3 fault-code, 9 work orders), every cited value asserted against the hierarchy
- ✅ 🤖 8-test acceptance suite `tests/test_phase1.py` — **all green** (incl. the corpus↔hierarchy consistency lint)
- ⬜ 👤 (optional) Spot-check: `make data` then eyeball `build/asset_hierarchy.csv`; skim 2–3 docs in `data/corpus/`

**Checkpoint:** ✅ `make test` → 8/8 pass. Time-series queries work; corpus is consistent with the data.
**Artifacts:** `src/` (config, llm_client stub, data/, docs_gen/), `data/corpus/`, `tests/`, `Makefile`.

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

Phases 0 & 1 are done (8/8 tests green). Start **Phase 2 — Baseline RAG (docs only)**:

1. 👤 (optional) Review Phase 1: run `make data && make test`, then skim `build/asset_hierarchy.csv` and a couple of docs in `data/corpus/`.
2. 🤖 Ask Claude Code: *"Do Phase 2: chunk the corpus, embed with OpenAI text-embedding-3-small into a local vector store, add hybrid (dense+BM25) retrieval, and answer doc-only questions with forced citations. Plan first."*

> Note: Phase 2 is the first phase that **spends OpenAI API** (embeddings + synthesis). The key in `.env` will be used.

> The 3 ways people fail this: (1) rushing the hand-labeled eval set, (2) building the
> router before the doc-only baseline works, (3) trusting the LLM judge without
> validating it. Don't.
