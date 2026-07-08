"""FastAPI backend for the Industrial Equipment RAG Copilot (Phase 6).

A thin HTTP layer over `src.rag.pipeline.answer` — the pipeline holds all the logic
(routing, hybrid retrieval, bounded telemetry tools, grounded synthesis with verified
citations, abstention). This module only adds request/response shapes, per-query
latency logging, and a health endpoint.

    make serve            # uvicorn on http://127.0.0.1:8100  (interactive docs at /docs)
    curl -s localhost:8100/ask -H 'content-type: application/json' \\
         -d '{"question":"What is the alarm threshold for T50?"}' | jq
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

from src import config
from src.llm_client import MODEL_ROUTING, MODEL_SYNTHESIS

log = logging.getLogger("copilot.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the vector index + retriever at boot so the first request isn't slow (and so a
    # missing/corrupt index fails loudly at startup, not on a user's query).
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from src.rag.embed_store import build_index
    from src.rag.retrieve import get_retriever

    build_index()          # idempotent: cached unless the corpus changed
    get_retriever()        # build the singleton now
    log.info("copilot ready — models: routing=%s synthesis=%s", MODEL_ROUTING, MODEL_SYNTHESIS)
    yield


app = FastAPI(title="Industrial Equipment RAG Copilot", version=config.APP_VERSION,
              lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="A maintenance / troubleshooting question.")
    k: int | None = Field(None, ge=1, le=20, description="Override retrieval depth (default 5).")


class AskResponse(BaseModel):
    question: str
    route: str                     # doc | timeseries | fusion | out_of_scope
    answer: str
    citations: list[str]           # doc ids and/or telemetry handles backing the answer
    contexts: list[dict]           # provenance actually used (retrieved docs + telemetry)
    confidence: str
    abstained: bool
    latency_ms: int
    usage: dict                    # token counts + OpenAI cost (USD) for this query


@app.get("/health")
def health():
    return {"status": "ok", "version": config.APP_VERSION,
            "models": {"routing": MODEL_ROUTING, "synthesis": MODEL_SYNTHESIS}}


@app.get("/")
def index():
    return {"service": "Industrial Equipment RAG Copilot", "version": config.APP_VERSION,
            "docs": "/docs", "ask": "POST /ask", "health": "/health"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    from src.rag.pipeline import answer

    t0 = time.perf_counter()
    k = req.k or config.RETRIEVAL_K
    result = answer(req.question, k=k)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    usage = result.get("usage", {})
    log.info("ask route=%s abstained=%s k=%d latency_ms=%d cost_usd=%.6f tokens=%d q=%r",
             result.get("route"), result.get("abstained"), k, latency_ms,
             usage.get("cost_usd", 0.0), usage.get("total_tokens", 0), req.question[:120])

    return AskResponse(
        question=req.question,
        route=result.get("route", "out_of_scope"),
        answer=result.get("answer", ""),
        citations=result.get("citations", []),
        contexts=result.get("contexts", []),
        confidence=result.get("confidence", "low"),
        abstained=bool(result.get("abstained")),
        latency_ms=latency_ms,
        usage=usage,
    )


def main():
    import uvicorn

    print(f"Copilot API → http://{config.API_HOST}:{config.API_PORT}  (docs at /docs)")
    uvicorn.run("src.api:app", host=config.API_HOST, port=config.API_PORT, log_level="info")


if __name__ == "__main__":
    main()
