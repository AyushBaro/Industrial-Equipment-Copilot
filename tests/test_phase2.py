"""Phase 2 acceptance tests.

Offline tests (no API) always run: chunking, BM25, RRF, citation verifier, abstention
guard. Live tests (embed + synthesize) run only when RUN_LLM_TESTS=1 and a key is
present — so the normal suite never spends money, while the build proves end-to-end
once.
"""
from __future__ import annotations

import json
import os

import pytest
from dotenv import load_dotenv

from src import config
from src.rag.chunk import Chunk, build_chunks
from src.rag.retrieve import Retriever, Retrieved, rrf_fuse
from src.rag.synthesize import ABSTENTION_MESSAGE, should_abstain, verify_citations

load_dotenv()
RUN_LLM = os.environ.get("RUN_LLM_TESTS") == "1" and bool(os.environ.get("OPENAI_API_KEY"))
live = pytest.mark.skipif(not RUN_LLM, reason="set RUN_LLM_TESTS=1 (and OPENAI_API_KEY) for live tests")


def _seed():
    return [json.loads(l) for l in config.PHASE2_SEED.read_text().splitlines() if l.strip()]


# ---- Offline ---------------------------------------------------------------

def test_chunking():
    chunks = build_chunks()
    assert len(chunks) >= 19
    doc_ids = {c.doc_id for c in chunks}
    assert len(doc_ids) == 19  # every doc represented
    for c in chunks:
        assert c.text and c.doc_id and c.doc_type
        # front-matter must not leak into chunk text
        assert "cites_sensors" not in c.text
        assert "assertions:" not in c.text


def test_bm25_exact_tokens():
    # BM25's role is to bring exact-token matches into the candidate pool (k*2 before
    # fusion), not necessarily to rank them #1 — a short index doc can outscore them.
    r = Retriever()
    top = r.bm25("FC-HPC-001 primary signature", k=5)
    assert any(cid.startswith("fault-FC-HPC-001") for cid in top)
    # Ps30 is an HPC-only token: the top hit must be an HPC chunk.
    top2 = r.bm25("Ps30 static pressure HPC outlet", k=3)
    assert top2 and r._by_id[top2[0]].subsystem == "HPC"


def test_rrf_fusion():
    fused = rrf_fuse([["a", "b"], ["a", "c"]])
    order = [cid for cid, _ in fused]
    assert order[0] == "a"            # appears top of both lists
    assert set(order) == {"a", "b", "c"}
    # 'a' strictly beats the singletons
    scores = dict(fused)
    assert scores["a"] > scores["b"] and scores["a"] > scores["c"]


def test_citation_verifier():
    assert verify_citations(["x", "y", "x"], ["x", "z"]) == ["x"]
    assert verify_citations([], ["x"]) == []
    assert verify_citations(["nope"], ["x", "z"]) == []


def test_abstention_guard():
    assert should_abstain([]) is True
    dummy = Retrieved(
        chunk=Chunk("d#s", "d", "manual", "HPC", "t", "s", "body text", ()),
        score=0.5, dense_rank=0, sparse_rank=0,
    )
    assert should_abstain([dummy]) is False


# ---- Live (gated) ----------------------------------------------------------

@pytest.fixture(scope="module")
def built_index():
    from src.rag.embed_store import build_index

    build_index()
    yield


@live
def test_dense_retrieval_live(built_index):
    r = Retriever()
    ids = r.dense("recommended inspection interval for the high pressure compressor", k=3)
    assert any(cid.startswith("manual-hpc") for cid in ids)


@live
def test_end_to_end_cited_answer_live(built_index):
    from src.rag.pipeline import answer

    res = answer("What is the recommended inspection interval for the HPC?")
    assert not res["abstained"]
    assert res["answer"] and res["answer"] != ABSTENTION_MESSAGE
    assert "manual-hpc" in res["citations"]
    retrieved_docs = {c["doc_id"] for c in res["contexts"]}
    assert set(res["citations"]).issubset(retrieved_docs)  # forced-citation invariant


@live
def test_abstention_live(built_index):
    from src.rag.pipeline import answer

    res = answer("What is the tire pressure of a Boeing 747 main landing gear?")
    assert res["abstained"] is True
    assert res["citations"] == []
