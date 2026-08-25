from typing import Any

import pytest
from app.eval.qwen_embedding import (
    QwenEvaluationEmbeddingAdapter,
    validate_embedding_profile,
)


class FakeEncoder:
    def __init__(self):
        self.received_sentences = []
        self.kwargs = {}

    def encode(self, sentences: list[str], **kwargs: Any) -> list[list[float]]:
        self.received_sentences.extend(sentences)
        self.kwargs = kwargs
        # Return fake vectors
        return [[0.1] * 1024 for _ in sentences]


def test_qwen_adapter_query_format():
    fake = FakeEncoder()
    adapter = QwenEvaluationEmbeddingAdapter(encoder=fake)
    
    test_query = "What is the policy on late fees?"
    adapter.embed_queries([test_query])
    
    expected_formatted = (
        "Instruct: Given a Vietnamese banking legal question, retrieve authoritative passages that directly support the answer.\n"
        f"Query: {test_query}"
    )
    
    assert fake.received_sentences == [expected_formatted]
    assert fake.kwargs.get("normalize_embeddings") is True


def test_profile_preflight_validation():
    valid_manifest = {
        "model_id": QwenEvaluationEmbeddingAdapter.MODEL_NAME,
        "resolved_revision": QwenEvaluationEmbeddingAdapter.REVISION,
        "embedding_dimension": QwenEvaluationEmbeddingAdapter.DIMENSION,
        "normalize_embeddings": True,
        "similarity": "cosine",
        "max_sequence_length": QwenEvaluationEmbeddingAdapter.MAX_SEQ_LENGTH,
        "query_instruction": QwenEvaluationEmbeddingAdapter.QUERY_INSTRUCTION,
        "input_template_version": "policy-title-heading-content-v1"
    }
    
    # Should not raise
    validate_embedding_profile(valid_manifest)
    
    # Test failures
    with pytest.raises(ValueError, match="model_id expected"):
        invalid = valid_manifest.copy()
        invalid["model_id"] = "wrong-model"
        validate_embedding_profile(invalid)
        
    with pytest.raises(ValueError, match="revision expected"):
        invalid = valid_manifest.copy()
        invalid["resolved_revision"] = "wrong-rev"
        validate_embedding_profile(invalid)

    with pytest.raises(ValueError, match="dimension expected"):
        invalid = valid_manifest.copy()
        invalid["embedding_dimension"] = 512
        validate_embedding_profile(invalid)
        
    with pytest.raises(ValueError, match="normalize_embeddings must be True"):
        invalid = valid_manifest.copy()
        invalid["normalize_embeddings"] = False
        validate_embedding_profile(invalid)
        
    with pytest.raises(ValueError, match="query_instruction does not match"):
        invalid = valid_manifest.copy()
        invalid["query_instruction"] = "Wrong instruction"
        validate_embedding_profile(invalid)

