from __future__ import annotations

import json
import math
from pathlib import Path

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
import pytest

from app.schemas import AgentID
from app.services.llm import OpenAICompatibleStructuredLLM, StaticStructuredLLM
from app.services.policy_catalog import parse_hhb_policy
from app.services.rag import DeterministicEmbeddingProvider, split_text


class ExampleStructuredResponse(BaseModel):
    decision: str = Field(min_length=1)
    score: int = Field(ge=0, le=100)


def test_split_text_is_bounded_ordered_and_handles_empty_content() -> None:
    text = ("Quy dinh tin dung doanh nghiep. " * 30) + "\n" + (
        "Tai san bao dam phai duoc tham dinh. " * 30
    )

    chunks = split_text(text, chunk_size=200, overlap=30)

    assert chunks
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert all(0 < len(chunk.content) <= 200 for chunk in chunks)
    assert split_text("  \n  ") == []


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(99, 0), (100, -1), (100, 100)],
)
def test_split_text_rejects_unsafe_chunk_parameters(
    chunk_size: int, overlap: int
) -> None:
    with pytest.raises(ValueError):
        split_text("policy text", chunk_size=chunk_size, overlap=overlap)


def test_deterministic_embedding_provider_returns_stable_1024d_unit_vectors() -> None:
    provider = DeterministicEmbeddingProvider(dimension=1024)

    first, second, repeated = provider.embed(
        ["chinh sach tin dung", "quy dinh tai san", "chinh sach tin dung"]
    )

    assert provider.dimension == 1024
    assert len(first) == len(second) == len(repeated) == 1024
    assert first == repeated
    assert first != second
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)


def test_create_embedding_provider_uses_only_embedding_credentials() -> None:
    from app.config import Settings
    from app.services.rag import (
        OpenAICompatibleEmbeddingProvider,
        create_embedding_provider,
    )

    settings = Settings(
        _env_file=None,
        llm_api_base="https://llm.example",
        llm_api_key="llm_key",
        embedding_api_base="https://emb.example",
        embedding_api_key="emb_key",
        embedding_provider="openai_compatible",
    )
    provider = create_embedding_provider(settings)
    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert str(provider._client.base_url) == "https://emb.example"
    assert provider._client.api_key == "emb_key"


def test_create_embedding_provider_fails_clearly_if_missing_embedding_key() -> None:
    from app.config import Settings
    from app.services.rag import create_embedding_provider

    settings = Settings(
        _env_file=None,
        llm_api_key="llm_key",
        embedding_api_key=None,
        embedding_provider="openai_compatible",
    )
    with pytest.raises(ValueError, match="EMBEDDING_API_KEY is required"):
        create_embedding_provider(settings)

    settings_blank = Settings(
        _env_file=None,
        llm_api_key="llm_key",
        embedding_api_key="   ",
        embedding_provider="openai_compatible",
    )
    with pytest.raises(ValueError, match="EMBEDDING_API_KEY is required"):
        create_embedding_provider(settings_blank)


def test_supplied_hhb_policy_parses_into_scoped_self_contained_sections() -> None:
    policy_path = Path(__file__).parents[1] / "resources/policies/QD-HHB-2026-01.txt"
    sections = parse_hhb_policy(policy_path.read_text(encoding="utf-8"))

    assert len(sections) == 54
    assert sections[0].section_id == "HHB-META-01"
    assert sections[-1].section_id == "HHB-PL-06"
    ltv = next(item for item in sections if item.section_id == "HHB-TC-05")
    assert AgentID.COLLATERAL_APPRAISAL in ltv.agent_ids
    assert "QĐ-HHB-2026/01" in ltv.content


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"decision": "review", "score": 80}', {"decision": "review", "score": 80}),
        (
            '```json\n{"decision": "review", "score": 80}\n```',
            {"decision": "review", "score": 80},
        ),
        (
            'Result follows: {"decision": "review", "score": 80}.',
            {"decision": "review", "score": 80},
        ),
    ],
)
def test_llm_json_extraction_accepts_supported_provider_shapes(
    content: str, expected: dict[str, object]
) -> None:
    assert OpenAICompatibleStructuredLLM._extract_json_object(content) == expected


def test_llm_json_extraction_rejects_non_json() -> None:
    with pytest.raises(json.JSONDecodeError):
        OpenAICompatibleStructuredLLM._extract_json_object("not structured output")


def test_static_structured_llm_validates_and_returns_isolated_copies() -> None:
    source = ExampleStructuredResponse(decision="manual_review", score=72)
    llm = StaticStructuredLLM(source)

    first = llm.invoke_structured(
        schema=ExampleStructuredResponse,
        system_prompt="ignored",
        user_prompt="ignored",
    )
    second = llm.invoke_structured(
        schema=ExampleStructuredResponse,
        system_prompt="ignored",
        user_prompt="ignored",
    )

    assert first == source
    assert first is not source
    assert second is not first


def test_real_llm_contract_repair_retries_with_validation_feedback() -> None:
    class FakeModel:
        def __init__(self) -> None:
            self.calls: list[object] = []

        def invoke(self, messages: object) -> AIMessage:
            self.calls.append(messages)
            if len(self.calls) == 1:
                return AIMessage(content='{"decision": "review", "score": 120}')
            return AIMessage(content='{"decision": "review", "score": 80}')

    llm = OpenAICompatibleStructuredLLM.__new__(OpenAICompatibleStructuredLLM)
    fake_model = FakeModel()
    llm._model = fake_model  # type: ignore[attr-defined]

    result = llm.invoke_structured(
        schema=ExampleStructuredResponse,
        system_prompt="Return a structured result.",
        user_prompt="Assess this test case.",
    )

    assert result.score == 80
    assert len(fake_model.calls) == 2
