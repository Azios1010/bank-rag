"""Canonical Corpus V2 query adapter for a local llama.cpp endpoint.

This module has no model-loading dependency.  It speaks only to the already
running OpenAI-compatible llama.cpp embeddings server and fails closed when
the server response does not satisfy the frozen 1024-dimensional profile.
The SentenceTransformer-backed adapter in :mod:`app.eval.qwen_embedding` is
legacy-only and is intentionally not imported here.
"""

from __future__ import annotations

import json
import math
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import get_settings


class LlamaEmbeddingResponseError(ValueError):
    """The embedding server response violated the V2 vector contract."""


class LlamaV2QueryEmbeddingAdapter:
    MODEL = "Qwen3-Embedding-0.6B"
    DIMENSION = 1024
    MAX_SEQ_LENGTH = 3072
    NORM_TOLERANCE = 1e-4
    QUERY_INSTRUCTION = (
        "Given a Vietnamese banking legal question, retrieve authoritative passages "
        "that directly support the answer."
    )

    def __init__(self, base_url: str | None = None, timeout_seconds: float = 30.0) -> None:
        configured_base_url = base_url or get_settings().llama_embedding_base_url
        self.endpoint = f"{configured_base_url.rstrip('/')}/v1/embeddings"
        self.timeout_seconds = timeout_seconds

    @classmethod
    def format_query(cls, query: str) -> str:
        return f"Instruct: {cls.QUERY_INSTRUCTION}\nQuery: {query}"

    def embed_query(self, query: str) -> list[float]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        payload = json.dumps(
            {"input": [self.format_query(query)], "model": self.MODEL},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if not isinstance(status, int) or not 200 <= status < 300:
                    raise LlamaEmbeddingResponseError(
                        f"llama.cpp embedding request returned HTTP {status}"
                    )
                raw_response = response.read()
        except (URLError, TimeoutError, OSError) as exc:
            raise LlamaEmbeddingResponseError("llama.cpp embedding request failed") from exc

        try:
            response_data: Any = json.loads(raw_response.decode("utf-8"))
            data = response_data["data"]
            if not isinstance(data, list) or len(data) != 1:
                raise LlamaEmbeddingResponseError(
                    "llama.cpp embedding response must contain exactly one data item"
                )
            item = data[0]
            if not isinstance(item, dict):
                raise LlamaEmbeddingResponseError(
                    "llama.cpp embedding response data item is malformed"
                )
            vector = item["embedding"]
        except (AttributeError, IndexError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LlamaEmbeddingResponseError("malformed llama.cpp embedding response") from exc
        return self._validate_server_vector(vector)

    @classmethod
    def _validate_server_vector(cls, vector: object) -> list[float]:
        if not isinstance(vector, list) or len(vector) != cls.DIMENSION:
            raise LlamaEmbeddingResponseError(
                f"embedding must contain exactly {cls.DIMENSION} dimensions"
            )
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in vector):
            raise LlamaEmbeddingResponseError("embedding values must be numeric")
        result = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in result):
            raise LlamaEmbeddingResponseError("embedding values must be finite")
        norm = math.sqrt(sum(value * value for value in result))
        if not math.isfinite(norm) or norm == 0.0:
            raise LlamaEmbeddingResponseError("embedding norm must be finite and non-zero")
        if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=cls.NORM_TOLERANCE):
            raise LlamaEmbeddingResponseError(
                f"embedding server response is not unit-normalized (norm={norm})"
            )
        # Do not normalize here: callers must reject a server that violates the
        # profile instead of silently changing the embedding space client-side.
        return result

    def embed_queries(self, queries: list[str]) -> list[list[float]]:
        """Embed queries serially to preserve the existing evaluation adapter interface."""

        return [self.embed_query(query) for query in queries]
