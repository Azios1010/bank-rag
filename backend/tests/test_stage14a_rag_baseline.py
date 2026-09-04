"""Offline structural tests for the Stage 14A grounded RAG baseline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_stage14a_rag_baseline import (
    GENERATOR_ALIAS,
    GENERATOR_MAX_TOKENS,
    GENERATOR_SEED,
    GENERATOR_TEMPERATURE,
    GENERATOR_TOP_P,
    SYSTEM_PROMPT,
    LocalQwenGenerationAdapter,
    build_generation_messages,
    detect_abstention,
    format_evidence_for_prompt,
    parse_citations,
)

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "dataset" / "evaluation" / "results"


def _evidence() -> list[dict[str, object]]:
    return [
        {
            "citation_id": f"E{index}",
            "canonical_chunk_id": f"chunk-{index}",
            "title": "Nguồn quy định",
            "heading_path": ["Chương I"],
            "locator": {"article": str(index), "clause": None, "point": None},
            "content": f"Nội dung chứng cứ {index}.",
        }
        for index in range(1, 6)
    ]


def test_evidence_prompt_is_ordered_and_has_no_internal_metadata() -> None:
    evidence = _evidence()
    prompt = format_evidence_for_prompt(evidence)
    assert prompt.index("[E1]") < prompt.index("[E2]") < prompt.index("[E5]")
    assert "chunk-1" not in prompt
    assert "gold_present_in_top5" not in prompt
    assert "vector_rank" not in prompt
    assert "reranker_score" not in prompt


def test_generation_messages_exclude_gold_diagnostics() -> None:
    messages = build_generation_messages("Câu hỏi thử nghiệm?", _evidence())
    assert [item["role"] for item in messages] == ["system", "user"]
    joined = json.dumps(messages, ensure_ascii=False)
    assert "gold_canonical_chunk_ids" not in joined
    assert "gold_present_in_top5" not in joined
    assert "benchmark" not in joined.casefold()
    assert messages[0]["content"] == SYSTEM_PROMPT


def test_citation_parser_accepts_only_e1_to_e5() -> None:
    valid, invalid = parse_citations("Đúng [E1] và [E5], sai [E0] [E6].")
    assert valid == ["E1", "E5"]
    assert invalid == ["E0", "E6"]


def test_citation_parser_rejects_unknown_bracket_identifier() -> None:
    valid, invalid = parse_citations("Nội dung [E7] [E7].")
    assert valid == []
    assert invalid == ["E7"]


def test_abstention_parser_is_structural_only() -> None:
    assert detect_abstention("Chưa đủ căn cứ trong tài liệu được cung cấp.") is True
    assert detect_abstention("Có thể thực hiện theo quy định. [E1]") is False


def test_generation_adapter_serializes_frozen_decoding(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {"choices": [{"message": {"content": "Trả lời [E1]."}}]},
                ensure_ascii=False,
            ).encode("utf-8")

    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> Response:
        captured["body"] = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("scripts.run_stage14a_rag_baseline.urlopen", fake_urlopen)
    response = LocalQwenGenerationAdapter().generate(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}]
    )
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == GENERATOR_ALIAS
    assert body["temperature"] == GENERATOR_TEMPERATURE
    assert body["top_p"] == GENERATOR_TOP_P
    assert body["seed"] == GENERATOR_SEED
    assert body["max_tokens"] == GENERATOR_MAX_TOKENS
    assert body["n"] == 1
    assert response["_answer"] == "Trả lời [E1]."


def test_prompt_context_policy_fails_closed_for_over_budget() -> None:
    evidence = _evidence()
    evidence[0]["content"] = "x" * 16000
    with pytest.raises(Exception, match="prompt exceeds context budget"):
        build_generation_messages("Câu hỏi?", evidence)


def test_frozen_generation_script_has_no_external_generation_stack() -> None:
    source = Path(__file__).resolve().parents[1] / "scripts" / "run_stage14a_rag_baseline.py"
    text = source.read_text(encoding="utf-8").casefold()
    assert "import openai" not in text
    assert "import sentence_transformers" not in text
    assert "fts" in text  # explicit false provenance guard is present


def test_completed_artifacts_have_100_evidence_and_answer_traces() -> None:
    evidence = [
        json.loads(line)
        for line in (RESULTS / "rag-v2-expanded-top5-evidence.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    traces = [
        json.loads(line)
        for line in (RESULTS / "rag-answer-v2-expanded-traces.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(evidence) == len(traces) == 100
    assert len({item["evaluation_id"] for item in traces}) == 100
    assert all([item["citation_id"] for item in row["evidence"]] == ["E1", "E2", "E3", "E4", "E5"] for row in evidence)
    assert all(row["serialized_evidence"].startswith("[E1]") for row in traces)
    assert all(row["semantic_review"]["status"] == "DRAFT" for row in traces)
    assert all(row["semantic_review"]["answer_correctness"] is None for row in traces)


def test_known_retrieval_failures_are_not_injected() -> None:
    rows = [
        json.loads(line)
        for line in (RESULTS / "rag-v2-expanded-top5-evidence.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_id = {row["evaluation_id"]: row for row in rows}
    for evaluation_id in ("stage12a-024", "stage13e-040", "stage13e-042"):
        assert by_id[evaluation_id]["known_retrieval_failure"] is True
        assert by_id[evaluation_id]["gold_present_in_top5"] is False
