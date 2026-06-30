# Phase 2 Plan — Baseline RAG (Documents Only)

**Gate:** review this, then I run autonomously until the Phase 2 test suite is green.
**What this phase is:** the first *answering* phase. We make the 19-doc maintenance
corpus searchable and have the system produce **grounded, cited answers** to
document-style questions. **No time-series, no router yet** (those are Phase 3).
**Cost:** this is the first phase that **spends OpenAI API** — estimated **< $0.25**
for the entire build including live tests (embeddings are ~$0.0003; a dozen synthesis
calls are a few cents).
**Done = `pytest tests/` is green** (offline logic tests always; live API smoke tests
run once during the build and reported).

---

## What we're building, in one picture

```
Question ("What's the HPC inspection interval?")
   │
   ▼
Hybrid retrieval over corpus chunks
   ├─ Dense:  OpenAI embeddings + Chroma  (semantic match)
   └─ Sparse: BM25 keyword               (exact terms: "Ps30", "FC-HPC-001")
   │            └── fused with Reciprocal Rank Fusion (RRF)
   ▼
Top-k chunks (each tagged with its doc id + section)
   ▼
Synthesis (gpt-4o): answer ONLY from those chunks, with inline citations
   ▼
{ answer, citations:[doc ids], confidence }   ← citations verified ⊆ retrieved
   │
   └─ if nothing relevant retrieved → "I don't have enough information" (basic abstention)
```

## Deliverables (file layout — adds to Phase 1)

```
src/
├─ llm_client.py            # FILL IN the stub: real chat() + embed() (OpenAI)
└─ rag/
   ├─ chunk.py              # corpus .md → chunks (strip YAML, keep metadata)
   ├─ embed_store.py        # embed chunks → persistent Chroma index (+ cache)
   ├─ retrieve.py           # dense + BM25 + RRF fusion → top-k chunks
   ├─ synthesize.py         # build prompt, get cited answer, verify citations, abstain
   └─ pipeline.py           # answer(question) end-to-end  + CLI entrypoint
Data/eval/
└─ phase2_seed.jsonl        # ~8 doc-only Q/A with expected source doc (seeds Phase 4)
tests/
└─ test_phase2.py           # offline logic tests + gated live smoke tests
build/chroma/               # persisted vector index (gitignored)
```

## Key engineering decisions (the judgment calls — flagging for your input)

1. **Chunk by section, not whole-doc.** The docs are small but have clear `##`
   sections. Section-level chunks give finer citations ("manual-hpc → Alarm response")
   and better retrieval precision. YAML front-matter is parsed into chunk *metadata*
   (doc id, type, subsystem, cited sensors) and **not** embedded as text.

2. **Hybrid retrieval (dense + BM25) fused with RRF.** Exact tokens like `Ps30` or
   `FC-HPC-001` must match precisely — pure semantic search misses those. Reciprocal
   Rank Fusion is the simple, standard way to combine the two ranked lists.

3. **Structured, verified citations.** Synthesis returns JSON `{answer, citations,
   confidence}`. We **programmatically verify** every cited doc id was actually in the
   retrieved set — a model can't cite something it wasn't given. Non-abstaining answers
   must cite ≥1 source.

4. **Basic abstention now, robust abstention in Phase 3.** If retrieval surfaces
   nothing above a relevance floor, the pipeline returns "I don't have enough
   information" without calling the model. Full abstention tuning/testing is Phase 3+5.
   (Flagging: this is a deliberately minimal version this phase.)

5. **Cost-safe testing.** Tests split in two:
   - **Offline (always run, no API):** chunking, BM25, RRF fusion math, citation
     verifier, abstention guard. These are the deterministic core.
   - **Live (gated by `OPENAI_API_KEY` + `RUN_LLM_TESTS=1`):** embed→retrieve→synthesize
     on the seed questions. I run these **once** during the build (pennies) and report;
     they're skipped in normal `pytest` runs so the suite never burns money on repeat.

## Components in detail

- **`llm_client.py`** — implement `chat(messages, model)` and `embed(texts)` against the
  OpenAI SDK, loading `OPENAI_API_KEY` from `.env`. Minimal retry/backoff. Still the one
  place model names live.
- **`chunk.py`** — reuse the Phase-1 front-matter parser; emit `Chunk(id, doc_id, type,
  subsystem, section_title, text)`. Deterministic ids (`{doc_id}#{section-slug}`).
- **`embed_store.py`** — embed all chunks in one batch; persist to Chroma in
  `build/chroma/`. A content hash manifest avoids re-embedding unchanged corpus
  (`make embed` rebuilds only when the corpus changes).
- **`retrieve.py`** — `dense(query,k)`, `bm25(query,k)`, `hybrid(query,k)` via RRF.
  Returns chunks + fused scores + a top relevance score (used by abstention).
- **`synthesize.py`** — system prompt enforces "answer only from the numbered context,
  cite the doc id for each claim, say you don't know if the context is insufficient."
  Parse JSON, verify citations, enforce non-empty citations on confident answers.
- **`pipeline.py`** — `answer(question) -> {answer, citations, contexts, abstained}`;
  CLI: `python -m src.rag.pipeline "your question"`.

## Seed eval set (`Data/eval/phase2_seed.jsonl`) — ~8 doc-only questions
Each: `{question, expected_doc_id, type}`. Examples:
- "What's the recommended inspection interval for the HPC?" → `manual-hpc`
- "What does fault code FC-HPC-001 mean?" → `fault-FC-HPC-001`
- "Which work order covers engine 47?" → `wo-1002-engine47`
- 1–2 **out-of-scope** questions (e.g. "What's a 747's tire pressure?") → expect abstention.
This is a *smoke* set, not the full 40–60 golden set (that's Phase 4) — it seeds it.

## Acceptance tests (`tests/test_phase2.py`)
**Offline (always):**
1. Chunking: every doc → ≥1 chunk; metadata present; no YAML leaks into chunk text.
2. BM25: a query with an exact token (`Ps30`, `FC-HPC-001`) ranks the owning doc top-3.
3. RRF: fusion function returns correct fused order on synthetic ranked inputs.
4. Citation verifier: rejects citations outside the retrieved set; accepts valid ones.
5. Abstention guard: empty/low retrieval → canned abstention, no model call, no citations.

**Live (gated, run once during build):**
6. Dense retrieval: HPC interval question → `manual-hpc` in top-3.
7. End-to-end: a seed question yields a non-empty answer citing the expected doc id,
   citations ⊆ retrieved.
8. Live abstention: out-of-scope question → abstains (no fabricated citation).

## Build order
1. Implement `llm_client` (chat + embed) → 2. `chunk.py` + tests → 3. `embed_store.py`
→ 4. `retrieve.py` + tests → 5. `synthesize.py` + verifier tests → 6. `pipeline.py` +
CLI → 7. seed eval set → 8. run live smoke tests, iterate to green → 9. macOS
notification + commit + update `steps.md`.

## What I will NOT do in Phase 2
- No query router and no time-series tool (Phase 3).
- No full golden eval set or scoring metrics (Phases 4–5).
- No UI or API server (Phase 6).
- No retrieval-quality *tuning* beyond getting the seed questions to pass — systematic
  tuning waits for the real eval harness in Phase 5.

## Notification
macOS desktop notification + written summary + test output when the suite is green.
