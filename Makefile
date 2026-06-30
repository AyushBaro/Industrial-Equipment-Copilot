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

# Run the Phase 1 acceptance suite (the gate).
test:
	$(PY) -m pytest tests/ -v

all: data docs test

clean:
	rm -rf build/*.duckdb build/*.csv build/*.json
