"""Thin OpenAI wrapper — the ONE place model names and API calls live.

Phase 2 fills in chat() and embed(). The key is loaded from .env; importing this
module is still side-effect-free (no client is built until a call is made).
"""
from __future__ import annotations

import os
import time

from dotenv import load_dotenv

# Model assignments (see CLAUDE.md). Change here only.
MODEL_SYNTHESIS = "gpt-4o"
MODEL_ROUTING = "gpt-4o-mini"
MODEL_JUDGE = "gpt-4o"
EMBEDDING_MODEL = "text-embedding-3-small"

_MAX_RETRIES = 4
_BACKOFF_BASE = 1.5


class LLMClient:
    """Lazily constructs an OpenAI client so importing this module never needs a key."""

    def __init__(self) -> None:
        self._client = None

    def _ensure(self):
        if self._client is None:
            from openai import OpenAI

            load_dotenv()
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                raise RuntimeError("OPENAI_API_KEY not set (load it from .env).")
            self._client = OpenAI(api_key=key)
        return self._client

    def _with_retry(self, fn):
        last = None
        for attempt in range(_MAX_RETRIES):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 — retry transient API errors
                last = exc
                if attempt == _MAX_RETRIES - 1:
                    break
                time.sleep(_BACKOFF_BASE ** attempt)
        raise last

    def chat(
        self,
        messages,
        model: str = MODEL_SYNTHESIS,
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> str:
        client = self._ensure()
        kwargs = {"model": model, "messages": messages, "temperature": temperature}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._with_retry(lambda: client.chat.completions.create(**kwargs))
        return resp.choices[0].message.content

    def embed(self, texts, model: str = EMBEDDING_MODEL):
        """Embed a list of strings; returns a list of float vectors (order preserved)."""
        if isinstance(texts, str):
            texts = [texts]
        client = self._ensure()
        resp = self._with_retry(
            lambda: client.embeddings.create(model=model, input=list(texts))
        )
        return [d.embedding for d in resp.data]


# Module-level singleton for convenience.
client = LLMClient()
