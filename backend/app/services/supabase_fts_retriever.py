"""Canonical Corpus V2 lexical retrieval through the Supabase FTS RPC.

The database owns PostgreSQL ``simple`` text search, visibility filtering, and
lexical ranking.  This client only sends the original query text and validates
the canonical citation contract; it never queries legacy tables or recreates
FTS ranking in Python.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import math
import re
import time
from typing import Any
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings, get_settings
from app.services.supabase_v2_retriever import normalize_specialist_scope


class SupabaseFTSRetrievalError(RuntimeError):
    """Raised when the canonical FTS RPC cannot be called or returns bad data."""


@dataclass(frozen=True)
class CanonicalV2LexicalResult:
    """One citation returned by the canonical PostgreSQL FTS RPC."""

    canonical_chunk_id: str
    content: str
    lexical_score: float
    document_source_id: str
    document_version_id: str
    document_title: str
    heading_path: list[Any]
    locator: dict[str, Any]
    namespace: str
    visibility: str
    metadata: dict[str, Any]

    @property
    def source_type(self) -> str:
        if self.metadata.get("provenance_kind") == "synthetic_internal_policy":
            return "synthetic_internal_policy"
        return "real_regulation"


@dataclass(frozen=True)
class CanonicalV2LexicalTiming:
    retrieval_ms: float


RpcOpener = Callable[..., object]


class CanonicalV2LexicalRetriever:
    """Retrieve frozen Corpus V2 citations using one FTS RPC."""

    RPC_PATH = "/rest/v1/rpc/match_policy_chunks_fts"
    MAX_MATCH_COUNT = 100

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        opener: RpcOpener = urlopen,
        timeout_seconds: float = 30.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.settings = settings or get_settings()
        self._opener = opener
        self._timeout_seconds = timeout_seconds

    @property
    def rpc_endpoint(self) -> str:
        if not self.settings.supabase_url:
            return ""
        return self.settings.supabase_url.rstrip("/") + self.RPC_PATH

    def retrieve(
        self,
        query: str,
        scope: object,
        k: int = 5,
    ) -> list[CanonicalV2LexicalResult]:
        results, _ = self.retrieve_with_timing(query, scope, k=k)
        return results

    def retrieve_with_timing(
        self,
        query: str,
        scope: object,
        k: int = 5,
    ) -> tuple[list[CanonicalV2LexicalResult], CanonicalV2LexicalTiming]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        requested_scope = normalize_specialist_scope(scope)
        if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= self.MAX_MATCH_COUNT:
            raise ValueError(f"k must be an integer between 1 and {self.MAX_MATCH_COUNT}")

        payload = {
            "query_text": self._query_text_for_rpc(query),
            "requested_scope": requested_scope,
            "match_count": k,
        }
        started = time.perf_counter()
        raw_results = self._call_rpc(payload)
        elapsed_ms = (time.perf_counter() - started) * 1000
        mapped_results: list[CanonicalV2LexicalResult] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(raw_results):
            mapped = self._map_result(item, index)
            if mapped.canonical_chunk_id in seen_ids:
                raise SupabaseFTSRetrievalError(
                    "canonical FTS RPC returned duplicate canonical_chunk_id"
                )
            seen_ids.add(mapped.canonical_chunk_id)
            mapped_results.append(mapped)
        return mapped_results, CanonicalV2LexicalTiming(retrieval_ms=elapsed_ms)

    @staticmethod
    def _query_text_for_rpc(query: str) -> str:
        """Return the original query for the historical plainto FTS RPC."""

        return query

    def _call_rpc(self, payload: Mapping[str, object]) -> list[object]:
        if not self.settings.supabase_url or not self.settings.supabase_service_role_key:
            raise SupabaseFTSRetrievalError(
                "SUPABASE_URL and backend-only SUPABASE_SERVICE_ROLE_KEY are required"
            )
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        secret = self.settings.supabase_service_role_key.get_secret_value()
        request = Request(
            self.rpc_endpoint,
            data=body,
            headers={
                "Accept": "application/json",
                "apikey": secret,
                "Authorization": "Bearer " + secret,
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:  # type: ignore[operator]
                status = getattr(response, "status", 200)
                if not isinstance(status, int) or not 200 <= status < 300:
                    raise SupabaseFTSRetrievalError(
                        f"canonical FTS RPC returned HTTP {status}"
                    )
                raw = response.read()
        except HTTPError as exc:
            raise SupabaseFTSRetrievalError(
                f"canonical FTS RPC returned HTTP {exc.code}"
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise SupabaseFTSRetrievalError(
                f"canonical FTS RPC request failed: {type(exc).__name__}"
            ) from None

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SupabaseFTSRetrievalError(
                "canonical FTS RPC returned malformed UTF-8 JSON"
            ) from exc
        if not isinstance(decoded, list):
            raise SupabaseFTSRetrievalError("canonical FTS RPC response must be a JSON array")
        return decoded

    @classmethod
    def _map_result(cls, item: object, index: int) -> CanonicalV2LexicalResult:
        if not isinstance(item, dict):
            raise SupabaseFTSRetrievalError(
                f"canonical FTS RPC result {index + 1} is not an object"
            )
        required = (
            "canonical_chunk_id",
            "content",
            "document_source_id",
            "document_version_id",
            "document_title",
            "heading_path",
            "locator",
            "namespace",
            "visibility",
            "metadata",
            "lexical_score",
        )
        missing = [key for key in required if key not in item]
        if missing:
            raise SupabaseFTSRetrievalError(
                f"canonical FTS RPC result {index + 1} is missing: {', '.join(missing)}"
            )
        string_fields = (
            "canonical_chunk_id",
            "content",
            "document_source_id",
            "document_version_id",
            "document_title",
            "namespace",
            "visibility",
        )
        if any(not isinstance(item[key], str) or not item[key] for key in string_fields):
            raise SupabaseFTSRetrievalError(
                f"canonical FTS RPC result {index + 1} has invalid identity fields"
            )
        if item["visibility"] not in {"SHARED", "SCOPED"}:
            raise SupabaseFTSRetrievalError(
                f"canonical FTS RPC result {index + 1} has invalid visibility"
            )
        if not isinstance(item["heading_path"], list) or not isinstance(item["locator"], dict):
            raise SupabaseFTSRetrievalError(
                f"canonical FTS RPC result {index + 1} has invalid citation location"
            )
        if not isinstance(item["metadata"], dict):
            raise SupabaseFTSRetrievalError(
                f"canonical FTS RPC result {index + 1} has invalid metadata"
            )
        lexical_score = item["lexical_score"]
        if isinstance(lexical_score, bool) or not isinstance(lexical_score, (int, float)):
            raise SupabaseFTSRetrievalError(
                f"canonical FTS RPC result {index + 1} has invalid lexical score"
            )
        lexical_score_value = float(lexical_score)
        if not math.isfinite(lexical_score_value) or lexical_score_value < 0:
            raise SupabaseFTSRetrievalError(
                f"canonical FTS RPC result {index + 1} has invalid lexical score"
            )
        return CanonicalV2LexicalResult(
            canonical_chunk_id=item["canonical_chunk_id"],
            content=item["content"],
            lexical_score=lexical_score_value,
            document_source_id=item["document_source_id"],
            document_version_id=item["document_version_id"],
            document_title=item["document_title"],
            heading_path=list(item["heading_path"]),
            locator=dict(item["locator"]),
            namespace=item["namespace"],
            visibility=item["visibility"],
            metadata=dict(item["metadata"]),
        )


def normalize_fts_tokens(query: str) -> list[str]:
    """Normalize query text mechanically without stemming or accent removal."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    normalized = unicodedata.normalize("NFC", query).casefold()
    tokens = re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)
    return list(dict.fromkeys(token for token in tokens if token))


def build_or_tsquery(query: str) -> str:
    """Build the fixed OR expression consumed by the additive diagnostic RPC."""

    tokens = normalize_fts_tokens(query)
    if not tokens:
        raise ValueError("query produced no lexical tokens")
    return " | ".join(tokens)


class CanonicalV2OrLexicalRetriever(CanonicalV2LexicalRetriever):
    """Diagnostic OR-FTS retriever over the existing canonical FTS index."""

    RPC_PATH = "/rest/v1/rpc/match_policy_chunks_fts_or"

    @staticmethod
    def _query_text_for_rpc(query: str) -> str:
        return build_or_tsquery(query)
