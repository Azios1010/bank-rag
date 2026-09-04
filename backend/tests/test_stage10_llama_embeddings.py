from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import run_stage10_llama_embeddings as stage10


def _vector(value: float = 1.0) -> list[float]:
    return [value] + [0.0] * (stage10.DIMENSION - 1)


def test_client_sends_explicit_utf8_json_body() -> None:
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

    with patch.object(stage10, "urlopen", fake_urlopen):
        result = stage10.LlamaCppEmbeddingClient(timeout_seconds=7.5).embed_one("Tiếng Việt")

    assert result == _vector()
    assert observed["body"] == '{"input":["Tiếng Việt"],"model":"Qwen3-Embedding-0.6B"}'.encode("utf-8")
    assert observed["content_type"] == "application/json; charset=utf-8"
    assert observed["timeout"] == 7.5


def test_client_rejects_non_unit_float32_server_vector() -> None:
    class Response:
        def read(self) -> bytes:
            return json.dumps({"data": [{"embedding": _vector(2.0)}]}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch.object(stage10, "urlopen", return_value=Response()):
        with pytest.raises(stage10.EmbeddingRequestError, match="embedding norm is 2.0"):
            stage10.LlamaCppEmbeddingClient().embed_one("test")


@pytest.mark.parametrize(
    "response",
    [
        {"data": [{"embedding": [0.0] * 1023}]},
        {"data": [{"embedding": _vector(float("nan"))}]},
        {"data": [{}]},
        {"data": []},
    ],
)
def test_client_rejects_malformed_or_wrong_dimension_response(response: dict) -> None:
    class Response:
        def read(self) -> bytes:
            return json.dumps(response).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch.object(stage10, "urlopen", return_value=Response()):
        with pytest.raises(stage10.EmbeddingRequestError):
            stage10.LlamaCppEmbeddingClient().embed_one("test")


def test_build_rows_preserves_canonical_id_order_and_rejects_duplicates() -> None:
    chunks = stage10._read_jsonl(stage10.CORPUS_PATH)
    rows = stage10.build_rows(chunks[:2])
    assert [row["chunk_id"] for row in rows] == [chunk["canonical_chunk_id"] for chunk in chunks[:2]]
    duplicate = [chunks[0], chunks[0]]
    with pytest.raises(ValueError, match="duplicate canonical_chunk_id"):
        stage10.build_rows(duplicate)


def test_partial_failure_does_not_publish_output(tmp_path: Path) -> None:
    chunks = stage10._read_jsonl(stage10.CORPUS_PATH)[:2]
    corpus_manifest = stage10._read_json(stage10.CORPUS_MANIFEST_PATH)

    class FailingClient:
        def __init__(self, *args):
            self.calls = 0

        def server_metadata(self):
            return {"data": [{"id": "Qwen3-Embedding-0.6B"}]}

        def embed_one(self, text: str):
            self.calls += 1
            if self.calls == 2:
                raise stage10.EmbeddingRequestError("simulated response failure")
            return _vector()

    with patch.object(stage10, "_read_jsonl", return_value=chunks), patch.object(
        stage10, "build_manifest", return_value=corpus_manifest
    ):
        with pytest.raises(stage10.EmbeddingRequestError, match="2/2"):
            stage10.run_embedding_job(output_dir=tmp_path, expected_count=2, client_factory=FailingClient)

    assert not (tmp_path / stage10.PARQUET_NAME).exists()
    assert not (tmp_path / stage10.MANIFEST_NAME).exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_mocked_bundle_passes_static_validator(tmp_path: Path) -> None:
    chunks = stage10._read_jsonl(stage10.CORPUS_PATH)[:2]
    corpus_manifest = stage10._read_json(stage10.CORPUS_MANIFEST_PATH)

    class SuccessfulClient:
        def __init__(self, *args):
            pass

        def server_metadata(self):
            return {"data": [{"id": "Qwen3-Embedding-0.6B", "pooling_type": "last"}]}

        def embed_one(self, text: str):
            return _vector()

    with patch.object(stage10, "_read_jsonl", return_value=chunks), patch.object(
        stage10, "build_manifest", return_value=corpus_manifest
    ):
        manifest = stage10.run_embedding_job(output_dir=tmp_path, expected_count=2, client_factory=SuccessfulClient)
        assert stage10.validate_bundle(
            tmp_path / stage10.PARQUET_NAME, tmp_path / stage10.MANIFEST_NAME, expected_count=2
        ) == []

    assert manifest["pooling"] == "LAST_TOKEN"
    assert manifest["model_id"] == stage10.REQUEST_MODEL
    assert manifest["model_family"] == "Qwen/Qwen3-Embedding-0.6B"
    assert manifest["endpoint"] == stage10.DEFAULT_ENDPOINT
    assert manifest["device_backend"] == "Vulkan"
    assert manifest["gpu"] == "NVIDIA GeForce RTX 2050"
    assert manifest["artifact_sha256"] == manifest["output"]["sha256"]
    assert manifest["artifact_byte_size"] == manifest["output"]["bytes"]
    assert manifest["validation"]["norm_percentile_convention"] == "linear interpolation at (n - 1) * p"
    assert manifest["validation"]["norm"]["p50"] == pytest.approx(1.0)
    assert manifest["validation"]["norm"]["p95"] == pytest.approx(1.0)
