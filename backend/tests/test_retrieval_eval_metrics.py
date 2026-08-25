import math

from app.eval.metrics import (
    binary_ndcg_at_k,
    hit_at_k,
    mrr_at_k,
    percentile,
    recall_at_k,
)


def test_hit_at_k():
    gold = {"a", "b"}
    assert hit_at_k(["c", "d"], gold, 2) == 0
    assert hit_at_k(["c", "a"], gold, 2) == 1
    assert hit_at_k(["a", "c"], gold, 1) == 1
    assert hit_at_k(["c", "a"], gold, 1) == 0


def test_recall_at_k():
    gold = {"a", "b", "c"}
    assert recall_at_k(["x", "y", "z"], gold, 3) == 0.0
    assert recall_at_k(["a", "y", "z"], gold, 3) == 1.0 / 3.0
    assert recall_at_k(["a", "b", "x"], gold, 3) == 2.0 / 3.0
    assert recall_at_k(["a", "b", "c"], gold, 3) == 1.0
    assert recall_at_k(["a", "b", "c"], gold, 2) == 2.0 / 3.0
    assert recall_at_k(["x"], set(), 1) == 0.0


def test_mrr_at_k():
    gold = {"a", "b"}
    assert mrr_at_k(["x", "y"], gold, 2) == 0.0
    assert mrr_at_k(["a", "y"], gold, 2) == 1.0
    assert mrr_at_k(["x", "a"], gold, 2) == 0.5
    assert mrr_at_k(["x", "y", "a"], gold, 2) == 0.0


def test_binary_ndcg_at_k():
    gold = {"a", "b", "c"}
    # Perfect retrieval
    ndcg = binary_ndcg_at_k(["a", "b", "c"], gold, 3)
    assert math.isclose(ndcg, 1.0)
    
    # Worst retrieval
    ndcg = binary_ndcg_at_k(["x", "y", "z"], gold, 3)
    assert math.isclose(ndcg, 0.0)
    
    # Partial
    idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3) + 1.0 / math.log2(4)
    dcg = 1.0 / math.log2(3)  # hit at rank 2
    expected = dcg / idcg
    ndcg = binary_ndcg_at_k(["x", "a", "y"], gold, 3)
    assert math.isclose(ndcg, expected)

def test_percentile():
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(data, 0.0) == 1.0
    assert percentile(data, 100.0) == 5.0
    assert percentile(data, 50.0) == 3.0
    assert percentile(data, 25.0) == 2.0
    assert percentile(data, 75.0) == 4.0
    
    data_even = [1.0, 2.0, 3.0, 4.0]
    assert percentile(data_even, 50.0) == 2.5
