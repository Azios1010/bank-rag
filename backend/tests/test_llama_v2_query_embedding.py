from __future__ import annotations

import json
from urllib.error import URLError
from unittest.mock import patch

import pytest

from app.eval.llama_v2_query_embedding import (
    LlamaEmbeddingResponseError,
    LlamaV2QueryEmbeddingAdapter,
)


def _vector(value: float = 1.0) -> list[float]:
    return [value] + [0.0] * (LlamaV2QueryEmbeddingAdapter.DIMENSION - 1)


def test_llama_v2_query_uses_exact_vietnamese_formatting_and_utf8_json() -> None:
    observed: dict[str, object] = {}

    class Response:
        def read(self) -> bytes:
            return json.dumps({"data": [{"embedding": _vector()}]}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        observed["body"] = request.data
        observed["content_type"] = request.get_header("Content-type")
        observed["timeout"] = timeout
        return Response()

    query = "Khoản vay có cần tài sản bảo đảm không?"
    with patch("app.eval.llama_v2_query_embedding.urlopen", fake_urlopen):
        result = LlamaV2QueryEmbeddingAdapter(
            base_url="http://llama.test:8081", timeout_seconds=7.5
        ).embed_query(query)

    expected_input = (
        "Instruct: Given a Vietnamese banking legal question, retrieve authoritative passages "
        "that directly support the answer.\n"
        f"Query: {query}"
    )
    assert result == _vector()
    assert observed["body"] == json.dumps(
        {"input": [expected_input], "model": "Qwen3-Embedding-0.6B"},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    assert observed["content_type"] == "application/json; charset=utf-8"
    assert observed["timeout"] == 7.5


@pytest.mark.parametrize(
    "response",
    [
        {"data": [{"embedding": [0.0] * 1023}]},
        {"data": [{"embedding": [0.0] * 1024}]},
        {"data": [{"embedding": _vector(float("nan"))}]},
        {"data": [{"embedding": _vector(float("inf"))}]},
        {"data": [{}]},
        {"data": []},
        {"data": [{"embedding": _vector()}, {"embedding": _vector()}]},
        {"other": []},
    ],
)
def test_llama_v2_query_rejects_malformed_or_wrong_dimension_response(response: dict) -> None:
    class Response:
        def read(self) -> bytes:
            return json.dumps(response).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("app.eval.llama_v2_query_embedding.urlopen", return_value=Response()):
        with pytest.raises(LlamaEmbeddingResponseError):
            LlamaV2QueryEmbeddingAdapter(base_url="http://llama.test").embed_query("test")


def test_llama_v2_query_surfaces_http_and_transport_failures() -> None:
    with patch(
        "app.eval.llama_v2_query_embedding.urlopen",
        side_effect=URLError("offline"),
    ):
        with pytest.raises(LlamaEmbeddingResponseError, match="request failed"):
            LlamaV2QueryEmbeddingAdapter(base_url="http://llama.test").embed_query("test")


def test_llama_v2_query_rejects_malformed_json() -> None:
    class Response:
        def read(self) -> bytes:
            return b"not-json"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("app.eval.llama_v2_query_embedding.urlopen", return_value=Response()):
        with pytest.raises(LlamaEmbeddingResponseError, match="malformed"):
            LlamaV2QueryEmbeddingAdapter(base_url="http://llama.test").embed_query("test")


def test_llama_v2_query_rejects_non_unit_server_vector_without_normalizing() -> None:
    class Response:
        def read(self) -> bytes:
            return json.dumps({"data": [{"embedding": _vector(2.0)}]}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("app.eval.llama_v2_query_embedding.urlopen", return_value=Response()):
        with pytest.raises(LlamaEmbeddingResponseError, match="not unit-normalized"):
            LlamaV2QueryEmbeddingAdapter(base_url="http://llama.test").embed_query("test")
