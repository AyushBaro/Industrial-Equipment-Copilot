"""Embed corpus chunks with OpenAI and persist them in a local Chroma index.

We compute embeddings ourselves via llm_client (so the model lives in one place) and
hand the vectors to Chroma. A content-hash manifest lets us skip re-embedding when the
corpus hasn't changed — repeat builds cost nothing.
"""
from __future__ import annotations

import hashlib
import json

import chromadb

from src import config
from src.llm_client import client as llm
from src.rag.chunk import Chunk, build_chunks


def _corpus_hash(chunks: list[Chunk]) -> str:
    h = hashlib.sha256()
    for c in sorted(chunks, key=lambda x: x.id):
        h.update(c.id.encode())
        h.update(c.text.encode())
    return h.hexdigest()


def _chroma():
    return chromadb.PersistentClient(path=str(config.CHROMA_DIR))


def build_index(force: bool = False) -> dict:
    """(Re)build the persistent vector index. Returns a small status dict."""
    config.ensure_build_dir()
    chunks = build_chunks()
    chash = _corpus_hash(chunks)

    manifest = {}
    if config.CORPUS_MANIFEST.exists():
        manifest = json.loads(config.CORPUS_MANIFEST.read_text())

    client = _chroma()
    existing = [c.name for c in client.list_collections()]
    up_to_date = (
        not force
        and manifest.get("hash") == chash
        and config.CHROMA_COLLECTION in existing
    )
    if up_to_date:
        return {"status": "cached", "n_chunks": len(chunks), "hash": chash}

    # Rebuild from scratch for determinism.
    if config.CHROMA_COLLECTION in existing:
        client.delete_collection(config.CHROMA_COLLECTION)
    collection = client.create_collection(
        config.CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"}
    )

    embeddings = llm.embed([c.text for c in chunks])
    collection.add(
        ids=[c.id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[c.to_metadata() for c in chunks],
    )
    config.CORPUS_MANIFEST.write_text(json.dumps({"hash": chash, "n_chunks": len(chunks)}))
    return {"status": "rebuilt", "n_chunks": len(chunks), "hash": chash}


def get_collection():
    return _chroma().get_collection(config.CHROMA_COLLECTION)


if __name__ == "__main__":
    print(build_index())
