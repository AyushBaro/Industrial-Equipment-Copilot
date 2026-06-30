"""Thin OpenAI wrapper — the ONE place model names live.

Phase 1 STUB: the interface is defined but no network call is made. Phases 2+ fill in
the bodies. Keeping the surface here means swapping models later touches one file.
"""
from __future__ import annotations

import os

# Model assignments (see CLAUDE.md). Change here only.
MODEL_SYNTHESIS = "gpt-4o"
MODEL_ROUTING = "gpt-4o-mini"
MODEL_JUDGE = "gpt-4o"
EMBEDDING_MODEL = "text-embedding-3-small"


class LLMClient:
    """Lazily constructs an OpenAI client so importing this module never needs a key."""

    def __init__(self) -> None:
        self._client = None

    def _ensure(self):
        if self._client is None:
            from openai import OpenAI  # imported lazily; not needed in Phase 1

            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                raise RuntimeError("OPENAI_API_KEY not set (load it from .env).")
            self._client = OpenAI(api_key=key)
        return self._client

    def chat(self, messages, model: str = MODEL_SYNTHESIS, **kwargs) -> str:  # noqa: D401
        raise NotImplementedError("Implemented in Phase 2.")

    def embed(self, texts, model: str = EMBEDDING_MODEL):
        raise NotImplementedError("Implemented in Phase 2.")
