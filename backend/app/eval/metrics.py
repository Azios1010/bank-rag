import math
from collections.abc import Sequence


def hit_at_k(retrieved_ids: Sequence[str], gold_ids: set[str], k: int) -> int:
    """Hit@K: 1 if top-K contains at least one relevant canonical chunk, else 0."""
    if k <= 0:
        return 0
    for chunk_id in retrieved_ids[:k]:
        if chunk_id in gold_ids:
            return 1
    return 0


def recall_at_k(retrieved_ids: Sequence[str], gold_ids: set[str], k: int) -> float:
    """Recall@K: relevant retrieved in top-K / total gold relevant."""
    if k <= 0 or not gold_ids:
        return 0.0
    relevant_retrieved = sum(1 for chunk_id in retrieved_ids[:k] if chunk_id in gold_ids)
    return relevant_retrieved / len(gold_ids)


def mrr_at_k(retrieved_ids: Sequence[str], gold_ids: set[str], k: int) -> float:
    """MRR@K: 1 / rank of first relevant result within K, else 0."""
    if k <= 0:
        return 0.0
    for i, chunk_id in enumerate(retrieved_ids[:k]):
        if chunk_id in gold_ids:
            return 1.0 / (i + 1)
    return 0.0


def binary_ndcg_at_k(retrieved_ids: Sequence[str], gold_ids: set[str], k: int) -> float:
    """binary nDCG@K: normalized discounted cumulative gain for binary relevance."""
    if k <= 0 or not gold_ids:
        return 0.0

    dcg = 0.0
    for i, chunk_id in enumerate(retrieved_ids[:k]):
        if chunk_id in gold_ids:
            # relevance is 1, so 1 / log2(i + 2)
            dcg += 1.0 / math.log2(i + 2)
    
    # max possible relevance is if first min(k, len(gold_ids)) are all relevant
    idcg = 0.0
    for i in range(min(k, len(gold_ids))):
        idcg += 1.0 / math.log2(i + 2)

    return dcg / idcg if idcg > 0.0 else 0.0


def percentile(data: Sequence[float], p: float) -> float:
    """Deterministic percentile calculation."""
    if not data:
        return 0.0
    if p <= 0.0:
        return min(data)
    if p >= 100.0:
        return max(data)
    
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)
