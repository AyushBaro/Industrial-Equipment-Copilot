# Phase 1 Plan — Data Foundation

**Gate:** review this, then I run autonomously until the Phase 1 test suite is green.
**Constraint:** **zero OpenAI API calls in Phase 1.** The maintenance docs are
**authored directly by Claude (me)** as real markdown files — realistic prose, not
rigid templates — grounded in the data-derived asset hierarchy. No OpenAI key is
touched; the cost is zero. (Transparency note for the README: corpus is
LLM-authored by Claude, grounded in the real CMAPSS schema + data-derived thresholds.)
**Done = `pytest tests/test_phase1.py` passes** (definition-of-done encoded as tests).

---

## Deliverables (file layout)

```
Proj_1/
├─ requirements.txt              # OpenAI-only stack, pinned
├─ src/
│  ├─ config.py                  # paths, constants, FD001 location
│  ├─ llm_client.py              # thin OpenAI wrapper (STUB in Phase 1 — not called yet)
│  ├─ data/
│  │  ├─ load_cmapss.py          # parse FD001 .txt → DuckDB table
│  │  ├─ sensor_meta.py          # canonical 21-sensor mapping (name/symbol/unit/subsystem)
│  │  ├─ asset_hierarchy.py      # build asset table (source of truth for thresholds)
│  │  └─ detect_flat_sensors.py  # find constant/non-informative sensors in FD001
│  └─ docs_gen/
│     └─ validate_corpus.py      # parse front-matter + lint doc values vs hierarchy
├─ data/
│  └─ corpus/                    # 15–20 Claude-authored .md docs (COMMITTED source)
├─ build/                        # generated artifacts (gitignored)
│  ├─ cmapss.duckdb              # FD001 loaded
│  └─ asset_hierarchy.csv        # sensor → subsystem → range → threshold
├─ tests/
│  ├─ conftest.py                # fixtures: build DB + hierarchy once
│  └─ test_phase1.py             # acceptance tests (the gate)
└─ Makefile                      # `make data`, `make docs`, `make test`
```

(`build/` added to `.gitignore` — regenerable.)

## Tooling decisions
- **Env:** `python -m venv .venv` + `requirements.txt` (zero extra tooling; reliable).
- **Deps for Phase 1 only:** `duckdb`, `pandas`, `pytest`, `python-dotenv`, `pypdf`.
  (OpenAI/Chroma/BM25/FastAPI/Streamlit go in later phases — installed now but unused.)
- **DuckDB** stores FD001 as table `sensor_readings`.

## Component 1 — CMAPSS loader (`load_cmapss.py`)
- Parse `Data/raw/CMAPSSData/train_FD001.txt` (space-delimited, no header) into columns:
  `unit_number, time_in_cycles, op_setting_1..3, sensor_1..21` (26 cols).
- Load into DuckDB table `sensor_readings`. Also load `test_FD001.txt` →
  `sensor_readings_test` and `RUL_FD001.txt` → `rul_test` (engine → true RUL).
- Sanity assertions baked in: 100 train engines, 26 columns, no nulls.

## Component 2 — Sensor metadata (`sensor_meta.py`)
Canonical CMAPSS 21-sensor mapping (from the Saxena 2008 paper in the data folder),
used to ground both the asset hierarchy and the docs:

| Sensor | Symbol | Description | Units | Subsystem |
|---|---|---|---|---|
| 1 | T2 | Total temp at fan inlet | °R | Fan |
| 2 | T24 | Total temp at LPC outlet | °R | LPC |
| 3 | T30 | Total temp at HPC outlet | °R | HPC |
| 4 | T50 | Total temp at LPT outlet | °R | LPT |
| 5 | P2 | Pressure at fan inlet | psia | Fan |
| 6 | P15 | Total pressure in bypass duct | psia | Fan/Bypass |
| 7 | P30 | Total pressure at HPC outlet | psia | HPC |
| 8 | Nf | Physical fan speed | rpm | Fan |
| 9 | Nc | Physical core speed | rpm | Core |
| 10 | epr | Engine pressure ratio (P50/P2) | — | Engine |
| 11 | Ps30 | Static pressure at HPC outlet | psia | HPC |
| 12 | phi | Fuel flow / Ps30 | pps/psi | HPC |
| 13 | NRf | Corrected fan speed | rpm | Fan |
| 14 | NRc | Corrected core speed | rpm | Core |
| 15 | BPR | Bypass ratio | — | Fan/Bypass |
| 16 | farB | Burner fuel-air ratio | — | Combustor |
| 17 | htBleed | Bleed enthalpy | — | Engine |
| 18 | Nf_dmd | Demanded fan speed | rpm | Fan |
| 19 | PCNfR_dmd | Demanded corrected fan speed | rpm | Fan |
| 20 | W31 | HPT coolant bleed | lbm/s | HPT |
| 21 | W32 | LPT coolant bleed | lbm/s | LPT |

Note: FD001's fault mode is **HPC degradation**, so HPC sensors (3, 7, 11, 12) are the
storyline for fault-pattern queries later.

## Component 3 — Flat-sensor detection (`detect_flat_sensors.py`)
- Compute per-sensor std/unique-count across FD001; flag sensors that are constant or
  near-constant (no information). Output the list + stats to `build/flat_sensors.json`.
- Documented, not hardcoded — the test asserts the detector finds the expected
  constant sensors (FD001 typically: 1, 5, 10, 16, 18, 19; verified at runtime, not assumed).

## Component 4 — Asset hierarchy (`asset_hierarchy.py`) — SOURCE OF TRUTH
- Build `build/asset_hierarchy.csv`: one row per sensor with
  `sensor_id, symbol, description, unit, subsystem, nominal_min, nominal_max, alarm_threshold, is_informative`.
- **Nominal ranges are derived from the actual FD001 data** (e.g. healthy-window
  percentiles per sensor), so thresholds are real, not invented. Alarm threshold =
  a defined margin beyond nominal.
- This table is the single source the docs must agree with.

## Component 5 — Maintenance corpus (Claude-authored, NO API)
**I author ~18 markdown docs** in `data/corpus/` *after* the asset hierarchy is built,
so I can ground every number in the actual data-derived values. Realistic prose, not
templates. Each doc carries front-matter (`id`, `type`, `subsystem`, `cites_sensors`)
for clean citation later.
- **Subsystem manuals** (Fan, LPC, HPC, Combustor, HPT, LPT) — description, monitored
  sensors, nominal ranges, inspection intervals, recommended actions. (~6 docs)
- **Fault-code reference** — fault codes mapping symptoms (which sensors deviate, e.g.
  HPC degradation → rising T30/Ps30) → diagnostic procedure. (~3 docs)
- **Work orders / maintenance logs** — dated entries referencing specific engines,
  sensor readings, fault codes, and actions taken. (~9 docs)

`validate_corpus.py` parses each doc's front-matter and checks that every numeric
threshold/range it cites matches the asset hierarchy (powers acceptance test #7).

## Acceptance tests (`tests/test_phase1.py`) — the gate
1. **Load**: `sensor_readings` has 100 train engines, 26 columns, 0 nulls; row count > 20000.
2. **Test/RUL**: `rul_test` has 100 engines; every test engine present.
3. **Schema**: column names match the canonical list exactly.
4. **Query smoke**: "engine 1, sensor_4, last 50 cycles" returns ≤50 ordered rows.
5. **Flat sensors**: detector runs and flags ≥1 constant sensor; list is stable/deterministic.
6. **Hierarchy**: all 21 sensors mapped; every row has subsystem + valid min<max + threshold.
7. **Consistency lint (key test)**: every sensor/threshold/range value cited in the
   corpus docs matches the asset hierarchy — no doc invents a number.
8. **Corpus**: 15–20 docs exist, each parses with valid front-matter and a known type.

## Notification
When the suite is green (or I hit a genuine blocker), I'll fire a **macOS desktop
notification** via `osascript` and post a written summary + test output here.

## Build order (within the autonomous run)
1. Load CMAPSS → DuckDB  2. Detect flat sensors  3. Build asset hierarchy (real ranges)
4. **I author the corpus docs grounded in those computed values**  5. Run the test suite.

## What I will NOT do in Phase 1
- No OpenAI/embedding/LLM *API* calls. `llm_client.py` is a stub with the interface
  only. (Docs are authored by me directly, which costs nothing.)
- No retrieval, router, or UI (Phases 2–3).
- No changes to `Data/raw/`.
