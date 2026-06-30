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

# Ask the copilot a question (docs-only RAG). Usage: make ask Q="your question"
ask:
	$(PY) -m src.rag.pipeline "$(Q)"

all: data docs test

clean:
	rm -rf build/*.duckdb build/*.csv build/*.json build/chroma build/corpus_manifest.json
