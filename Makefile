PY := ./.venv/bin/python

.PHONY: data docs test all clean

# Build DuckDB + flat-sensor evidence + asset hierarchy from raw FD001 data.
data:
	$(PY) -m src.data.load_cmapss
	$(PY) -m src.data.detect_flat_sensors
	$(PY) -m src.data.asset_hierarchy

# Validate the maintenance corpus against the asset hierarchy.
docs:
	$(PY) -m src.docs_gen.validate_corpus

# Build the vector index (embeds corpus via OpenAI; cached unless corpus changed).
embed:
	$(PY) -m src.rag.embed_store

# Run the acceptance suite. Offline tests only (free, no API).
test:
	$(PY) -m pytest tests/ -v

# Run the full suite incl. live API tests (spends a few cents).
test-live:
	RUN_LLM_TESTS=1 $(PY) -m pytest tests/ -v

# Ask the copilot a question. Usage: make ask Q="your question"
ask:
	$(PY) -m src.rag.pipeline "$(Q)"

# --- Golden eval set (Phase 4) ---
# Generate candidate rows with pre-filled proposed labels (offline, no API).
eval-generate:
	$(PY) -m src.eval.generate_candidates

# Browser review app (easiest): opens http://127.0.0.1:8000, click to approve/reject.
eval-web:
	$(PY) -m src.eval.review_server

# Terminal triage: approve/edit/reject each row with one keypress (autosaves).
eval-triage:
	$(PY) -m src.eval.triage $(ARGS)

# Read-only viewer of all candidates. Add ARGS="--live" to compare vs the system.
eval-review:
	$(PY) -m src.eval.review $(ARGS)

# Validate the golden file. Add ARGS=--require-approved once you've reviewed.
eval-validate:
	$(PY) -m src.eval.validate_golden $(ARGS)

all: data docs test

clean:
	rm -rf build/*.duckdb build/*.csv build/*.json build/chroma build/corpus_manifest.json
