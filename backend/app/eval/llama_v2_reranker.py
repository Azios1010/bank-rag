"""Dedicated llama.cpp reranker adapter for the frozen Corpus V2 experiment.

The adapter speaks only the OpenAI-compatible ``/v1/rerank`` endpoint exposed
by llama.cpp.  It deliberately returns API indexes rather than canonical IDs;
the caller owns the explicit index-to-candidate mapping and can therefore
prove that the reranker neither injects nor drops a candidate.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import get_settings


class LlamaRerankerResponseError(ValueError):
    """The reranker response violated the strict native API contract."""


@dataclass(frozen=True)
class LlamaRerankScore:
    """One native reranker result before candidate-ID mapping."""

    index: int
    relevance_score: float


class LlamaV2RerankerAdapter:
    """Call llama.cpp's dedicated reranking endpoint without any fallback."""

    MODEL = "Qwen3-Reranker-0.6B"
    DOCUMENT_TEMPLATE = "Title: {title}\nSection: {heading_path}\nText:\n{content}"

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_seconds: float = 120.0,
        opener=urlopen,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        configured = base_url or get_settings().llama_reranker_base_url
        self.endpoint = f"{configured.rstrip('/')}/v1/rerank"
        self.timeout_seconds = timeout_seconds
        self._opener = opener

    @classmethod
    def format_document(
        cls, *, title: str, heading_path: list[object], content: str
    ) -> str:
        if not isinstance(title, str) or not isinstance(content, str):
            raise ValueError("reranker document title and content must be strings")
        if not isinstance(heading_path, list):
            raise ValueError("reranker heading_path must be a list")
        heading = json.dumps(heading_path, ensure_ascii=False, separators=(",", ":"))
        return cls.DOCUMENT_TEMPLATE.format(
            title=title, heading_path=heading, content=content
        )

    def rerank(self, query: str, documents: list[str]) -> list[LlamaRerankScore]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("reranker query must be a non-empty string")
        if not isinstance(documents, list) or not documents:
            raise ValueError("reranker documents must be a non-empty list")
        if any(not isinstance(document, str) for document in documents):
            raise ValueError("reranker documents must contain only strings")

        payload = json.dumps(
            {"model": self.MODEL, "query": query, "documents": documents},
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
            with self._opener(request, timeout=self.timeout_seconds) as response:  # type: ignore[operator]
                status = getattr(response, "status", 200)
                if not isinstance(status, int) or not 200 <= status < 300:
                    raise LlamaRerankerResponseError(
                        f"llama.cpp reranker request returned HTTP {status}"
                    )
                raw_response = response.read()
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except OSError:
                detail = ""
            raise LlamaRerankerResponseError(
                f"llama.cpp reranker request returned HTTP {exc.code}"
                + (f": {detail}" if detail else "")
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise LlamaRerankerResponseError(
                "llama.cpp reranker request failed"
            ) from exc

        try:
            response_data: Any = json.loads(raw_response.decode("utf-8"))
            raw_results = response_data["results"]
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, KeyError, TypeError) as exc:
            raise LlamaRerankerResponseError(
                "malformed llama.cpp reranker response"
            ) from exc
        if not isinstance(raw_results, list) or len(raw_results) != len(documents):
            raise LlamaRerankerResponseError(
                "reranker response must contain exactly one result per input document"
            )

        scores: list[LlamaRerankScore] = []
        seen_indexes: set[int] = set()
        for position, item in enumerate(raw_results):
            if not isinstance(item, dict) or "index" not in item or "relevance_score" not in item:
                raise LlamaRerankerResponseError(
                    f"reranker result {position + 1} is missing index or relevance_score"
                )
            index = item["index"]
            score = item["relevance_score"]
            if isinstance(index, bool) or not isinstance(index, int):
                raise LlamaRerankerResponseError(
                    f"reranker result {position + 1} has an invalid index"
                )
            if not 0 <= index < len(documents) or index in seen_indexes:
                raise LlamaRerankerResponseError(
                    f"reranker result {position + 1} has a duplicate or out-of-range index"
                )
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise LlamaRerankerResponseError(
                    f"reranker result {position + 1} has an invalid relevance score"
                )
            score_value = float(score)
            if not math.isfinite(score_value):
                raise LlamaRerankerResponseError(
                    f"reranker result {position + 1} has a non-finite relevance score"
                )
            seen_indexes.add(index)
            scores.append(LlamaRerankScore(index=index, relevance_score=score_value))
        if seen_indexes != set(range(len(documents))):
            raise LlamaRerankerResponseError(
                "reranker response did not cover every input document index"
            )
        return scores
