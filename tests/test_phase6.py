"""Phase 6 — FastAPI backend.

Offline (free): the endpoints that don't hit a model — health, index, and request
validation. These use a TestClient WITHOUT the context manager so the lifespan (index
warm-up) doesn't run, keeping them key-free and instant.

Live (RUN_LLM_TESTS=1): a real /ask round-trip through the pipeline, asserting the
response shape and that a doc question answers with a citation.
"""
from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from src import config
from src.api import app

load_dotenv()
RUN_LLM = os.environ.get("RUN_LLM_TESTS") == "1" and bool(os.environ.get("OPENAI_API_KEY"))
live = pytest.mark.skipif(not RUN_LLM, reason="set RUN_LLM_TESTS=1 (and OPENAI_API_KEY) for live tests")


# ---- Offline --------------------------------------------------------------

def test_health():
    c = TestClient(app)  # no 'with' → lifespan (index build) does not run
    body = c.get("/health").json()
    assert body["status"] == "ok"
    assert body["version"] == config.APP_VERSION
    assert "synthesis" in body["models"]


def test_index_lists_routes():
    body = TestClient(app).get("/").json()
    assert body["health"] == "/health" and "ask" in body


def test_ask_rejects_empty_question():
    assert TestClient(app).post("/ask", json={"question": ""}).status_code == 422


def test_ask_rejects_out_of_range_k():
    r = TestClient(app).post("/ask", json={"question": "hi", "k": 99})
    assert r.status_code == 422


# ---- Live -----------------------------------------------------------------

@live
def test_ask_doc_question_end_to_end():
    with TestClient(app) as c:  # 'with' runs lifespan → index warm-up
        r = c.post("/ask", json={"question": "What is the recommended inspection interval for the HPC?"})
    assert r.status_code == 200
    body = r.json()
    assert body["route"] == "doc" and body["abstained"] is False
    assert body["citations"], "a grounded doc answer must carry at least one citation"
    assert body["latency_ms"] > 0
