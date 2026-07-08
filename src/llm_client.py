"""Thin OpenAI wrapper — the ONE place model names and API calls live.

Phase 2 fills in chat() and embed(). The key is loaded from .env; importing this
module is still side-effect-free (no client is built until a call is made).
"""
from __future__ import annotations

import contextlib
import contextvars
import os
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Model assignments (OpenAI only). Change here only.
MODEL_SYNTHESIS = "gpt-4o"
MODEL_ROUTING = "gpt-4o-mini"
MODEL_JUDGE = "gpt-4o"
EMBEDDING_MODEL = "text-embedding-3-small"

_MAX_RETRIES = 4
_BACKOFF_BASE = 1.5

# --- Cost accounting ---------------------------------------------------------
# USD per 1,000,000 tokens: (input/prompt, output/completion). Embeddings are
# input-only. Keep these next to the model names — the one place pricing lives.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4o-mini": (0.15, 0.60),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int = 0) -> float:
    """Cost of a single call. Unknown models cost 0 (and are surfaced in by_model)."""
    inp, outp = PRICING.get(model, (0.0, 0.0))
    return (prompt_tokens * inp + completion_tokens * outp) / 1_000_000


@dataclass
class UsageMeter:
    """Accumulates token usage + cost for all OpenAI calls made within a scope."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    n_calls: int = 0
    cost: float = 0.0
    by_model: dict = field(default_factory=dict)

    def add(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        c = cost_usd(model, prompt_tokens, completion_tokens)
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.n_calls += 1
        self.cost += c
        m = self.by_model.setdefault(
            model, {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0, "cost_usd": 0.0})
        m["prompt_tokens"] += prompt_tokens
        m["completion_tokens"] += completion_tokens
        m["calls"] += 1
        m["cost_usd"] = round(m["cost_usd"] + c, 6)

    def as_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "n_calls": self.n_calls,
            "cost_usd": round(self.cost, 6),
            "by_model": self.by_model,
        }


# Request-scoped so per-query cost stays isolated even when FastAPI runs sync
# endpoints concurrently in a threadpool. Default None = accounting off (no overhead).
_usage_meter: contextvars.ContextVar = contextvars.ContextVar("usage_meter", default=None)


@contextlib.contextmanager
def track_usage():
    """Scope in which OpenAI token usage + cost is tallied. Yields the UsageMeter.

        with track_usage() as meter:
            answer(question)
        meter.as_dict()  # {'total_tokens': ..., 'cost_usd': ..., 'by_model': {...}}
    """
    meter = UsageMeter()
    token = _usage_meter.set(meter)
    try:
        yield meter
    finally:
        _usage_meter.reset(token)


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

    @staticmethod
    def _record(model: str, usage) -> None:
        """Tally a response's token usage into the active meter, if any."""
        meter = _usage_meter.get()
        if meter is None or usage is None:
            return
        meter.add(model,
                  getattr(usage, "prompt_tokens", 0) or 0,
                  getattr(usage, "completion_tokens", 0) or 0)

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
        self._record(model, getattr(resp, "usage", None))
        return resp.choices[0].message.content

    def embed(self, texts, model: str = EMBEDDING_MODEL):
        """Embed a list of strings; returns a list of float vectors (order preserved)."""
        if isinstance(texts, str):
            texts = [texts]
        client = self._ensure()
        resp = self._with_retry(
            lambda: client.embeddings.create(model=model, input=list(texts))
        )
        self._record(model, getattr(resp, "usage", None))
        return [d.embedding for d in resp.data]


# Module-level singleton for convenience.
client = LLMClient()
