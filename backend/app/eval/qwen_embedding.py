from typing import Any, Protocol


class EncoderProtocol(Protocol):
    def encode(self, sentences: list[str], **kwargs: Any) -> Any:
        ...


class QwenEvaluationEmbeddingAdapter:
    """Evaluation embedding adapter for Qwen3-Embedding-0.6B."""
    
    MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
    REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
    DIMENSION = 1024
    MAX_SEQ_LENGTH = 3072
    QUERY_INSTRUCTION = "Given a Vietnamese banking legal question, retrieve authoritative passages that directly support the answer."
    
    def __init__(self, encoder: EncoderProtocol | None = None) -> None:
        self._encoder = encoder

    @classmethod
    def create_real(cls) -> "QwenEvaluationEmbeddingAdapter":
        from sentence_transformers import SentenceTransformer
        
        encoder = SentenceTransformer(
            model_name_or_path=cls.MODEL_NAME,
            revision=cls.REVISION,
            trust_remote_code=True,
        )
        encoder.max_seq_length = cls.MAX_SEQ_LENGTH
        return cls(encoder=encoder)

    def format_query(self, query: str) -> str:
        return f"Instruct: {self.QUERY_INSTRUCTION}\nQuery: {query}"

    def embed_queries(self, queries: list[str]) -> list[list[float]]:
        if self._encoder is None:
            raise RuntimeError("Encoder not initialized")
        
        formatted_queries = [self.format_query(q) for q in queries]
        
        embeddings = self._encoder.encode(
            formatted_queries,
            normalize_embeddings=True,
            # We don't return PyTorch tensors, just a list of lists or numpy arrays that we cast
        )
        
        import numpy as np
        if isinstance(embeddings, np.ndarray):
            return embeddings.tolist()
        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return [list(map(float, vec)) for vec in embeddings]


def validate_embedding_profile(manifest: dict[str, Any]) -> None:
    """Preflight validation of embedding manifest against expected profile."""
    if manifest.get("model_id") != QwenEvaluationEmbeddingAdapter.MODEL_NAME:
        raise ValueError(f"Profile mismatch: model_id expected {QwenEvaluationEmbeddingAdapter.MODEL_NAME}, got {manifest.get('model_id')}")
    
    if manifest.get("resolved_revision") != QwenEvaluationEmbeddingAdapter.REVISION:
        raise ValueError(f"Profile mismatch: revision expected {QwenEvaluationEmbeddingAdapter.REVISION}, got {manifest.get('resolved_revision')}")
        
    if manifest.get("embedding_dimension") != QwenEvaluationEmbeddingAdapter.DIMENSION:
        raise ValueError(f"Profile mismatch: dimension expected {QwenEvaluationEmbeddingAdapter.DIMENSION}, got {manifest.get('embedding_dimension')}")
        
    if manifest.get("normalize_embeddings") is not True:
        raise ValueError("Profile mismatch: normalize_embeddings must be True")
        
    if manifest.get("similarity") != "cosine":
        raise ValueError("Profile mismatch: similarity must be cosine")
        
    if manifest.get("max_sequence_length") != QwenEvaluationEmbeddingAdapter.MAX_SEQ_LENGTH:
        raise ValueError(f"Profile mismatch: max_sequence_length expected {QwenEvaluationEmbeddingAdapter.MAX_SEQ_LENGTH}")
        
    if manifest.get("query_instruction") != QwenEvaluationEmbeddingAdapter.QUERY_INSTRUCTION:
        raise ValueError("Profile mismatch: query_instruction does not match expected exact string")
        
    if "input_template_version" in manifest and manifest["input_template_version"] != "policy-title-heading-content-v1":
        raise ValueError("Profile mismatch: input_template_version must be policy-title-heading-content-v1")

