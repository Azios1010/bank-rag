import json
from pathlib import Path

from app.services.policy_chunking_v2 import HARD_LIMIT, PolicyChunkerV2


def provision(content, *, article="1", clause=None, point=None, content_hash="hash"):
    return {
        "source_id": "test-source", "version_id": "test-version", "chapter": "I",
        "section": "1", "article": article, "clause": clause, "point": point,
        "heading_path": ["I", "1"], "content": content, "page_start": 1,
        "page_end": 1, "content_hash": content_hash,
    }


def test_small_article_is_deterministic_and_lossless():
    provisions = [
        provision("Article 1. General rules.", content_hash="h1"),
        provision("1. First clause.", clause="1", content_hash="h2"),
        provision("a) First point.", clause="1", point="a", content_hash="h3"),
    ]
    first = PolicyChunkerV2()
    first.process_dataset(provisions)
    second = PolicyChunkerV2()
    second.process_dataset(provisions)

    assert len(first.chunks) == 1
    assert first.chunks[0]["content"] == "Article 1. General rules.\n1. First clause.\na) First point."
    assert first.chunks[0]["context_mode"] == "metadata_only"
    assert first.chunks[0]["canonical_chunk_id"] == second.chunks[0]["canonical_chunk_id"]


def test_long_article_clause_and_point_use_metadata_context_not_copied_parent_text():
    article = "A" * 6101
    clause = "C" * 6101
    point = "P" * 3622
    chunker = PolicyChunkerV2()
    chunker.process_dataset([
        provision(article, content_hash="article"),
        provision(clause, clause="1", content_hash="clause"),
        provision(point, clause="1", point="a", content_hash="point"),
    ])

    assert all(len(chunk["content"]) <= HARD_LIMIT for chunk in chunker.chunks)
    assert all(not chunk["is_long_unsplittable"] for chunk in chunker.chunks)
    assert all(chunk["context_mode"] == "metadata_only" for chunk in chunker.chunks)
    assert all("A" * 100 not in chunk["content"] for chunk in chunker.chunks if chunk["point"] == "a")
    assert "".join(chunk["content"] for chunk in chunker.chunks if chunk["point"] == "a") == point


def test_split_order_and_hard_fallback_preserve_every_character():
    text = ("Đoạn một. " * 260) + ("X" * 2600) + " kết thúc."
    chunks = PolicyChunkerV2._split_text(text, 2400)
    assert "".join(chunks) == text
    assert all(len(chunk) <= 2400 for chunk in chunks)


def test_repeated_labels_get_distinct_identities_and_are_retained():
    chunker = PolicyChunkerV2()
    chunker.process_dataset([
        provision("1. First occurrence.", clause="1", content_hash="one"),
        provision("1. Second occurrence.", clause="1", content_hash="two"),
    ])
    # The compact article causes one ordinary aggregate. Force the repeated
    # source records into a large article so their distinct metadata is emitted.
    chunker.process_dataset([
        provision("Article heading " + "H" * 2400, content_hash="heading"),
        provision("1. First occurrence.", clause="1", content_hash="one"),
        provision("1. Second occurrence.", clause="1", content_hash="two"),
    ])
    repeated = [chunk for chunk in chunker.chunks if chunk["clause"] == "1"]
    assert len(repeated) == 2
    assert len({chunk["hierarchy_instance"] for chunk in repeated}) == 2
    assert {chunk["hierarchy_classification"] for chunk in repeated} == {"REPEATED_LABEL_GENUINE"}
    assert any(item["anomaly_type"] == "REPEATED_HIERARCHY_LABEL" for item in chunker.anomalies)


def test_direct_article_points_are_explicitly_classified():
    chunker = PolicyChunkerV2()
    chunker.process_dataset([
        provision("Article heading " + "H" * 2400, content_hash="heading"),
        provision("a) Direct article point.", point="a", content_hash="a"),
        provision("b) Another direct article point.", point="b", content_hash="b"),
    ])
    direct = [chunk for chunk in chunker.chunks if chunk["point"] is not None]
    assert {chunk["hierarchy_classification"] for chunk in direct} == {"DIRECT_ARTICLE_POINT"}
    assert [item["input_ordinals"] for item in chunker.anomalies if item["anomaly_type"] == "DIRECT_ARTICLE_POINT"] == [[2], [3]]


def test_exact_legal_text_duplicate_is_not_context_replication():
    chunker = PolicyChunkerV2()
    chunker.process_dataset([
        provision("Article heading " + "H" * 2400, content_hash="heading"),
        provision("Same legal sentence.", clause="1", content_hash="one"),
        provision("Same legal sentence.", clause="2", content_hash="two"),
    ])
    duplicates = [item for item in chunker.anomalies if item["anomaly_type"] == "EXACT_DUPLICATE_LEGAL_TEXT"]
    assert len(duplicates) == 1
    assert duplicates[0]["input_ordinals"] == [2, 3]


def test_real_normalized_orphans_and_repeated_labels_have_explicit_decisions():
    root = Path(__file__).resolve().parents[2]
    provisions = [json.loads(line) for line in (root / "dataset/normalized/v2/policy-provisions.jsonl").read_text(encoding="utf-8").splitlines()]
    chunker = PolicyChunkerV2()
    chunker.process_dataset(provisions)

    direct = {
        tuple(item["input_ordinals"])
        for item in chunker.anomalies if item["anomaly_type"] == "DIRECT_ARTICLE_POINT"
    }
    assert direct == {(222,), (223,), (224,), (2157,), (2158,)}
    repeated = {
        tuple(item["input_ordinals"])
        for item in chunker.anomalies if item["anomaly_type"] == "REPEATED_HIERARCHY_LABEL"
    }
    assert {(200, 204, 208), (201, 205, 209), (2040, 2042), (2064, 2066), (2972, 2973), (3208, 3210, 3215)} <= repeated
