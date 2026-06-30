"""Hybrid retrieval: dense (embeddings/Chroma) + sparse (BM25), fused with RRF.

Why hybrid: semantic search finds paraphrases, but exact tokens like "Ps30" or
"FC-HPC-001" must match precisely — that's BM25's job. Reciprocal Rank Fusion combines
the two ranked lists without needing to calibrate their score scales.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from src import config
from src.llm_client import client as llm
from src.rag.chunk import Chunk, build_chunks


@dataclass
class Retrieved:
    chunk: Chunk
    score: float        # fused RRF score
    dense_rank: int | None
    sparse_rank: int | None


def tokenize(text: str) -> list[str]:
    # \w+ keeps alphanumerics together (so "ps30" stays one token); hyphens split
    # "FC-HPC-001" into [fc, hpc, 001], which a same-tokenized query also produces.
    return re.findall(r"\w+", text.lower())


class Retriever:
    def __init__(self):
        self._chunks = build_chunks()
        self._by_id = {c.id: c for c in self._chunks}
        self._bm25 = BM25Okapi([tokenize(c.text) for c in self._chunks])
        self._collection = None  # lazy (needs the persisted index)

    # --- individual retrievers ------------------------------------------------
    def bm25(self, query: str, k: int = config.RETRIEVAL_K) -> list[str]:
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self._chunks[i].id for i in ranked[:k] if scores[i] > 0]

    def dense(self, query: str, k: int = config.RETRIEVAL_K) -> list[str]:
        if self._collection is None:
            from src.rag.embed_store import get_collection

            self._collection = get_collection()
        qvec = llm.embed([query])[0]
        res = self._collection.query(query_embeddings=[qvec], n_results=k)
        return list(res["ids"][0])

    # --- fusion ---------------------------------------------------------------
    def hybrid(self, query: str, k: int = config.RETRIEVAL_K) -> list[Retrieved]:
        dense_ids = self.dense(query, k * 2)
        sparse_ids = self.bm25(query, k * 2)
        fused = rrf_fuse([dense_ids, sparse_ids])
        out: list[Retrieved] = []
        for cid, score in fused[:k]:
            out.append(
                Retrieved(
                    chunk=self._by_id[cid],
                    score=score,
                    dense_rank=dense_ids.index(cid) if cid in dense_ids else None,
                    sparse_rank=sparse_ids.index(cid) if cid in sparse_ids else None,
                )
            )
        return out


def rrf_fuse(ranked_lists: list[list[str]], rrf_k: int = config.RRF_K):
    """Reciprocal Rank Fusion. Returns [(id, fused_score), ...] sorted desc."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, cid in enumerate(ranked):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


# Module-level singleton (built lazily by callers that need it).
_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
