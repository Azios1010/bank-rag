"""Freeze the authoritative human review for the Stage 14A RAG baseline.

This script materializes only the human totals and the explicitly supplied
per-query annotations.  It deliberately does not infer missing semantic
labels from answers, traces, model output, or heuristics.  The original Stage
14A review pack and all Stage 14A result artifacts are read-only inputs.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.eval.gold_v2 import CanonicalGoldValidator, FrozenCorpusV2

GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.jsonl"
PILOT_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
STAGE14A_SUMMARY_PATH = ROOT / "dataset/evaluation/results/rag-answer-v2-expanded-summary.json"
STAGE14A_TRACE_PATH = ROOT / "dataset/evaluation/results/rag-answer-v2-expanded-traces.jsonl"
STAGE14A_REVIEW_PATH = ROOT / "docs/STAGE-14A-RAG-ANSWER-REVIEW.md"
GENERATOR_PATH = Path(r"D:\llm-models\Qwen_Qwen3.5-4B-Q4_K_S.gguf")
GENERATOR_SHA256 = "3a6e5e8144696a87d17f136b06fce7fe5008a42737938056df13e11ddba4a01b"

SUMMARY_PATH = ROOT / "dataset/evaluation/results/rag-answer-v2-expanded-human-review-summary.json"
KNOWN_LABELS_PATH = ROOT / (
    "dataset/evaluation/results/rag-answer-v2-expanded-human-review-known-labels.jsonl"
)
FROZEN_REVIEW_PATH = ROOT / "docs/STAGE-14A-RAG-ANSWER-REVIEW-FROZEN.md"
STAGE_DOC_PATH = ROOT / "docs/STAGE-14B-HUMAN-SEMANTIC-BASELINE-FREEZE.md"

EXPECTED_GOLD_SHA256 = "1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69"
EXPECTED_PILOT_SHA256 = "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"
EXPECTED_CORPUS_MANIFEST_SHA256 = "b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a"
EXPECTED_EMBEDDING_ARTIFACT_SHA256 = "3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c"
EXPECTED_EMBEDDING_MANIFEST_SHA256 = "cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863"
EXPECTED_RERANKER_SHA256 = "22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48"

PARTIAL_IDS = [
    "stage12a-004",
    "stage12a-011",
    "stage12a-013",
    "stage12a-014",
    "stage13e-037",
    "stage13e-043",
    "stage13e-049",
    "stage13e-050",
    "stage13e-059",
    "stage13e-065",
    "stage13e-068",
    "stage13e-073",
    "stage13e-080",
    "stage13e-083",
    "stage13e-084",
    "stage13e-090",
    "stage13e-091",
    "stage13e-099",
]
CITATION_PRIMARY_IDS = [
    "stage12a-003",
    "stage12a-008",
    "stage12a-019",
    "stage13e-034",
    "stage13e-036",
    "stage13e-038",
]
TRUNCATION_IDS = [
    "stage12a-004",
    "stage12a-013",
    "stage12a-024",
    "stage13e-050",
    "stage13e-059",
    "stage13e-091",
    "stage13e-099",
]
GOLD_ABSENT_IDS = ["stage12a-024", "stage13e-040", "stage13e-042"]
FULL_FAILURES = {
    "stage12a-002": {
        "gold_present_in_top5": True,
        "failure_source": "GENERATION",
        "note": "Generator reversed the legal polarity of the prohibited-purpose evidence.",
    },
    "stage12a-024": {
        "gold_present_in_top5": False,
        "failure_source": "MIXED",
        "note": "Gold evidence was absent and the answer did not abstain.",
    },
    "stage13e-040": {
        "gold_present_in_top5": False,
        "failure_source": "MIXED",
        "note": "Gold evidence was absent and the answer went beyond supplied evidence.",
    },
    "stage13e-042": {
        "gold_present_in_top5": False,
        "failure_source": "MIXED",
        "note": "Gold evidence was absent; unsupported approving authorities were asserted without a valid E1-E5 citation.",
    },
}

SCOPE_CORRECTNESS = {
    "credit": {"PASS": 17, "PARTIAL": 2, "FAIL": 1},
    "risk_management": {"PASS": 14, "PARTIAL": 4, "FAIL": 2},
    "legal_compliance": {"PASS": 15, "PARTIAL": 5, "FAIL": 0},
    "customer_relationship": {"PASS": 16, "PARTIAL": 4, "FAIL": 0},
    "collateral_appraisal": {"PASS": 16, "PARTIAL": 3, "FAIL": 1},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def validate_inputs() -> dict[str, Any]:
    required_paths = [
        GOLD_PATH,
        PILOT_PATH,
        STAGE14A_SUMMARY_PATH,
        STAGE14A_TRACE_PATH,
        STAGE14A_REVIEW_PATH,
        GENERATOR_PATH,
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise RuntimeError("missing Stage 14B input: " + ", ".join(missing))

    actual_hashes = {
        "gold": sha256(GOLD_PATH),
        "pilot": sha256(PILOT_PATH),
        "generator": sha256(GENERATOR_PATH),
    }
    expected_hashes = {
        "gold": EXPECTED_GOLD_SHA256,
        "pilot": EXPECTED_PILOT_SHA256,
        "generator": GENERATOR_SHA256,
    }
    if actual_hashes != expected_hashes:
        raise RuntimeError(f"frozen hash mismatch: {actual_hashes}")

    corpus = FrozenCorpusV2()
    if corpus.corpus_identity["corpus_manifest_sha256"] != f"sha256:{EXPECTED_CORPUS_MANIFEST_SHA256}":
        raise RuntimeError("frozen corpus manifest identity mismatch")
    if corpus.embedding_identity["embedding_artifact_sha256"] != f"sha256:{EXPECTED_EMBEDDING_ARTIFACT_SHA256}":
        raise RuntimeError("frozen embedding artifact identity mismatch")
    if corpus.embedding_identity["embedding_manifest_sha256"] != f"sha256:{EXPECTED_EMBEDDING_MANIFEST_SHA256}":
        raise RuntimeError("frozen embedding manifest identity mismatch")
    if len(corpus.rows) != 1610 or len(corpus.by_id) != 1610:
        raise RuntimeError("frozen corpus is not exactly 1610 unique chunks")

    validator = CanonicalGoldValidator(corpus)
    pilot_records = validator.parse_file(PILOT_PATH)
    gold_records = validator.parse_file(GOLD_PATH)
    if len(pilot_records) != 25 or any(row["status"] != "REVIEWED" for row in pilot_records):
        raise RuntimeError("Stage 12A pilot is not exactly 25 REVIEWED records")
    if len(gold_records) != 100 or any(row["status"] != "REVIEWED" for row in gold_records):
        raise RuntimeError("expanded gold is not exactly 100 REVIEWED records")
    if Counter(row["specialist_scope"] for row in gold_records) != Counter(
        {scope: 20 for scope in SCOPE_CORRECTNESS}
    ):
        raise RuntimeError("expanded gold scope distribution changed")
    if any("BankingOperations" in json.dumps(row, ensure_ascii=False) for row in gold_records):
        raise RuntimeError("unsupported BankingOperations content found in gold")

    stage14a_summary = json.loads(STAGE14A_SUMMARY_PATH.read_text(encoding="utf-8"))
    structural = stage14a_summary["structural"]
    expected_structural = {
        "answers_attempted": 100,
        "answers_generated": 100,
        "technical_failures": 0,
        "technical_retries": 0,
        "answers_with_valid_citations": 94,
        "answers_with_zero_citations": 4,
        "answers_with_invalid_citation_ids": 2,
        "abstentions_detected": 0,
        "gold_present_in_top5": 97,
        "gold_absent_in_top5": 3,
    }
    if structural != expected_structural:
        raise RuntimeError(f"Stage 14A structural baseline mismatch: {structural}")

    traces = load_jsonl(STAGE14A_TRACE_PATH)
    if len(traces) != 100 or len({row["evaluation_id"] for row in traces}) != 100:
        raise RuntimeError("Stage 14A trace artifact is not exactly 100 unique records")
    if "Status: `DRAFT`" not in STAGE14A_REVIEW_PATH.read_text(encoding="utf-8"):
        raise RuntimeError("original Stage 14A review pack is not visibly DRAFT")

    return {
        "actual_hashes": actual_hashes,
        "corpus": corpus,
        "gold_records": gold_records,
        "pilot_records": pilot_records,
        "stage14a_summary": stage14a_summary,
        "traces": traces,
        "review_pack_sha256": sha256(STAGE14A_REVIEW_PATH),
        "generator_bytes": GENERATOR_PATH.stat().st_size,
    }


def build_summary(inputs: dict[str, Any]) -> dict[str, Any]:
    structural = inputs["stage14a_summary"]["structural"]
    return {
        "stage": "14B — Human Semantic Review Freeze",
        "human_review_authoritative": True,
        "semantic_judge": "human",
        "per_query_label_materialization": {
            "status": "PARTIAL",
            "explanation": "Authoritative aggregate freeze and explicitly listed per-query classifications are materialized; a complete 100-record human label map is not available mechanically.",
        },
        "record_count": 100,
        "gold": {
            "path": str(GOLD_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": EXPECTED_GOLD_SHA256,
            "status_counts": {"REVIEWED": 100, "DRAFT": 0, "REJECTED": 0},
        },
        "frozen_retrieval": {
            "architecture": "Qwen3-Embedding-0.6B → vector Top20 → Qwen3-Reranker-0.6B Q8_0 → Top5",
            "candidate_k": 20,
            "final_k": 5,
            "reference_hit_at_5": 0.9700,
            "changed": False,
        },
        "stage14a_structural": structural,
        "correctness": {"PASS": 78, "PARTIAL": 18, "FAIL": 4},
        "groundedness": {"FULLY_GROUNDED": 87, "PARTIALLY_GROUNDED": 12, "UNGROUNDED": 1},
        "citation_quality": {"CORRECT": 81, "PARTIAL": 12, "INCORRECT": 7},
        "abstention": {
            "APPROPRIATE": 0,
            "UNNECESSARY": 0,
            "MISSING_WHEN_REQUIRED": 4,
            "N/A": 96,
        },
        "failure_source": {
            "NONE": 72,
            "GENERATION": 19,
            "CITATION": 6,
            "MIXED": 3,
            "RETRIEVAL": 0,
            "RERANKING": 0,
        },
        "clean_answers": 72,
        "gold_present_subset": {"count": 97, "PASS": 78, "PARTIAL": 18, "FAIL": 1},
        "gold_absent_subset": {
            "count": 3,
            "ids": GOLD_ABSENT_IDS,
            "FAIL": 3,
            "correct_abstentions": 0,
        },
        "partial_ids": PARTIAL_IDS,
        "full_failure_ids": sorted(FULL_FAILURES),
        "full_failures": [
            {"evaluation_id": key, **value} for key, value in sorted(FULL_FAILURES.items())
        ],
        "citation_primary_ids": CITATION_PRIMARY_IDS,
        "truncation_ids": TRUNCATION_IDS,
        "per_scope_correctness": SCOPE_CORRECTNESS,
        "latency_ms": {
            "classification": "LOCAL RTX 2050 REFERENCE ONLY — NOT A PRODUCTION SLA",
            "generation_p50": 13850.037,
            "generation_p95": 25595.020,
            "generation_mean": 14073.420,
            "ttft_p50": 1544.523,
            "tokens_per_second_p50": 21.418,
        },
        "generator_decision": "Qwen3.5-4B Q4_K_S retained as the V1 local generator",
        "frozen_identities": {
            "pilot_sha256": EXPECTED_PILOT_SHA256,
            "corpus": "policy-corpus-v2",
            "corpus_chunks": 1610,
            "corpus_manifest_sha256": EXPECTED_CORPUS_MANIFEST_SHA256,
            "embedding_artifact_sha256": EXPECTED_EMBEDDING_ARTIFACT_SHA256,
            "embedding_manifest_sha256": EXPECTED_EMBEDDING_MANIFEST_SHA256,
            "reranker_sha256": EXPECTED_RERANKER_SHA256,
            "generator_sha256": GENERATOR_SHA256,
        },
        "provenance_metadata_issue": {
            "status": "KNOWN METADATA / PRESENTATION BUG",
            "observed": "82 SCOPED synthetic evidence items in the Stage 14A Top5 artifact are serialized as real_regulation.",
            "root_cause": "The canonical retrieval DTO source_type falls back to real_regulation unless RPC metadata contains provenance_kind; the returned synthetic source metadata does not expose that key. Frozen local corpus source metadata identifies all three synthetic sources as synthetic.",
            "location": "Stage 14A evidence serialization / CanonicalV2RetrievalResult.source_type mapping",
            "mutation_performed": False,
            "proposed_fix": "Resolve presentation provenance from trusted frozen source identity when serializing evidence, then regenerate only a separately versioned presentation artifact after review. Do not rewrite the frozen Stage 14A baseline in this stage.",
        },
        "preserved_artifacts": {
            "original_review_pack": str(STAGE14A_REVIEW_PATH.relative_to(ROOT)).replace("\\", "/"),
            "original_review_pack_sha256": inputs["review_pack_sha256"],
            "complete_per_query_label_artifact_created": False,
        },
    }


def build_known_labels(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    trace_by_id = {row["evaluation_id"]: row for row in inputs["traces"]}
    ids = sorted(set(PARTIAL_IDS) | set(CITATION_PRIMARY_IDS) | set(TRUNCATION_IDS) | set(FULL_FAILURES))
    rows: list[dict[str, Any]] = []
    for evaluation_id in ids:
        known: dict[str, Any] = {}
        if evaluation_id in FULL_FAILURES:
            failure = FULL_FAILURES[evaluation_id]
            known.update(
                {
                    "answer_correctness": "FAIL",
                    "failure_source": failure["failure_source"],
                    "gold_present_in_top5": failure["gold_present_in_top5"],
                    "review_note": failure["note"],
                }
            )
        if evaluation_id in PARTIAL_IDS:
            known["answer_correctness"] = "PARTIAL"
        if evaluation_id in CITATION_PRIMARY_IDS:
            known["citation_primary_failure"] = True
            known["failure_source"] = "CITATION"
        if evaluation_id in TRUNCATION_IDS:
            known["truncation_known_stage14a"] = True
        trace = trace_by_id[evaluation_id]
        rows.append(
            {
                "artifact_status": "INCOMPLETE_EXPLICIT_HUMAN_ANNOTATIONS_ONLY",
                "evaluation_id": evaluation_id,
                "gold_present_in_top5_diagnostic": trace["gold_present_in_top5_diagnostic"],
                "human_review_authoritative": True,
                "known_labels": known,
                "unassigned_semantic_fields": [
                    "groundedness",
                    "citation_quality",
                    "abstention",
                    "review_notes_for_unlisted_dimensions",
                ],
            }
        )
    return rows


def render_freeze_docs(summary: dict[str, Any], known_rows: list[dict[str, Any]]) -> tuple[str, str]:
    counts = summary["stage14a_structural"]
    summary_json = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    known_ids = ", ".join(row["evaluation_id"] for row in known_rows)
    frozen_review = f"""# Stage 14A Review Artifact — Frozen Human Baseline

This document freezes the authoritative Stage 14A-R1 human semantic review
without overwriting the original review pack.

The complete generated-answer review pack remains at
`docs/STAGE-14A-RAG-ANSWER-REVIEW.md` and remains unchanged with semantic
fields marked `DRAFT`. A complete mechanically available 100-row human label
map was not present, so this artifact freezes the aggregate verdict and the
explicit per-query classifications supplied by the human reviewer only.

## Authority and scope

- Semantic authority: human reviewer.
- Codex did not re-judge correctness, groundedness, citations, abstention, or
  failure source.
- The known-label JSONL is intentionally incomplete and contains {len(known_rows)}
  records: {known_ids}.
- Unlisted per-query semantic fields remain unassigned.

## Frozen aggregate

- Correctness: PASS 78, PARTIAL 18, FAIL 4.
- Groundedness: FULLY_GROUNDED 87, PARTIALLY_GROUNDED 12, UNGROUNDED 1.
- Citation quality: CORRECT 81, PARTIAL 12, INCORRECT 7.
- Abstention: APPROPRIATE 0, UNNECESSARY 0, MISSING_WHEN_REQUIRED 4, N/A 96.
- Failure source: NONE 72, GENERATION 19, CITATION 6, MIXED 3, RETRIEVAL 0,
  RERANKING 0.
- Clean answers: 72 / 100.

Gold-present subset is 97 queries: PASS 78, PARTIAL 18, FAIL 1. Gold-absent
queries are `stage12a-024`, `stage13e-040`, and `stage13e-042`: FAIL 3/3 and
correct abstentions 0/3.

## Preservation

Stage 14A structural totals remain: attempted {counts['answers_attempted']},
generated {counts['answers_generated']}, valid citations
{counts['answers_with_valid_citations']}, zero citations
{counts['answers_with_zero_citations']}, invalid citation answers
{counts['answers_with_invalid_citation_ids']}, technical failures
{counts['technical_failures']}. No generation or retrieval benchmark was run
for Stage 14B.
"""
    freeze_doc = f"""# Stage 14B — Human Semantic Baseline Freeze

## Decision

Stage 14A-R1 human semantic review is frozen as the V1 end-to-end baseline.
Human review is authoritative. This stage materializes supplied human totals
and explicitly supplied per-query classifications; it does not independently
label answers.

Human review status:

- Stage 12A seed: 25 / 25 REVIEWED.
- Stage 13E expansion: 75 / 75 APPROVED after R2 minor corrections by the
  human reviewer.
- Stage 14A answers: 100 reviewed semantically by the human reviewer at the
  aggregate level supplied for this freeze.

## Frozen identities

| Item | Value |
|---|---|
| Gold | `dataset/evaluation/retrieval-v2-gold-expanded.jsonl` |
| Gold SHA-256 | `{summary['gold']['sha256']}` |
| Retrieval | Qwen3-Embedding-0.6B → vector Top20 → Qwen3-Reranker-0.6B Q8_0 → Top5 |
| Candidate/final K | 20 / 5 |
| Corpus | `policy-corpus-v2`, 1610 chunks |
| Corpus manifest SHA-256 | `{EXPECTED_CORPUS_MANIFEST_SHA256}` |
| Embedding artifact SHA-256 | `{EXPECTED_EMBEDDING_ARTIFACT_SHA256}` |
| Embedding manifest SHA-256 | `{EXPECTED_EMBEDDING_MANIFEST_SHA256}` |
| Reranker SHA-256 | `{EXPECTED_RERANKER_SHA256}` |
| Generator | Qwen3.5-4B Q4_K_S, local llama.cpp/Vulkan1 RTX 2050 |
| Generator SHA-256 | `{GENERATOR_SHA256}` |

## Stage 14A structural baseline

- 100 attempted and 100 generated; technical failures 0; retries 0.
- 94 answers had valid citations; 4 had zero citations; 2 had invalid
  citation IDs; structural abstentions detected: 0.
- Gold present in Top5: 97. Gold absent: 3.

Reference latency is local RTX 2050 only, not a production SLA: generation
p50 13850.037 ms, p95 25595.020 ms, mean 14073.420 ms, TTFT p50 1544.523 ms,
tokens/sec p50 21.418.

## Human semantic verdict

### Correctness

PASS 78; PARTIAL 18; FAIL 4.

### Groundedness

FULLY_GROUNDED 87; PARTIALLY_GROUNDED 12; UNGROUNDED 1.

### Citation quality

CORRECT 81; PARTIAL 12; INCORRECT 7.

### Abstention

APPROPRIATE 0; UNNECESSARY 0; MISSING_WHEN_REQUIRED 4; N/A 96.

### Failure source

NONE 72; GENERATION 19; CITATION 6; MIXED 3; standalone RETRIEVAL 0;
RERANKING 0. Clean answer means PASS + FULLY_GROUNDED + CORRECT citation + no
missing-required abstention: 72 / 100.

## Explicit failure register

Full failures: `stage12a-002` (GENERATION: legal polarity reversal),
`stage12a-024`, `stage13e-040`, and `stage13e-042` (MIXED; gold absent and
the generator did not appropriately abstain or stayed within supplied
evidence as described in the human review).

Partial IDs are frozen exactly as supplied:

`{', '.join(PARTIAL_IDS)}`

Citation-primary IDs are frozen exactly as supplied:

`{', '.join(CITATION_PRIMARY_IDS)}`

Known truncation IDs: `{', '.join(TRUNCATION_IDS)}`. This is a known Stage
14A generation failure mode associated with the fixed max output token setting;
these answers were not rerun.

Per-scope correctness:

- credit: PASS 17, PARTIAL 2, FAIL 1.
- risk_management: PASS 14, PARTIAL 4, FAIL 2 (weakest at 70% PASS).
- legal_compliance: PASS 15, PARTIAL 5, FAIL 0.
- customer_relationship: PASS 16, PARTIAL 4, FAIL 0.
- collateral_appraisal: PASS 16, PARTIAL 3, FAIL 1.

## Provenance metadata issue

Read-only inspection found 82 SCOPED synthetic evidence items in the Stage
14A Top5 evidence artifact serialized with `provenance: real_regulation`.
The frozen local corpus manifest/source identity correctly marks the three
synthetic sources as synthetic. The presentation mismatch is caused by the
retrieval DTO's `source_type` fallback when RPC metadata lacks
`provenance_kind`. No corpus, Supabase, embedding, or Stage 14A artifact was
mutated. A proposed future fix is to resolve presentation provenance from
trusted source identity during serialization and regenerate a separately
versioned presentation artifact after review.

## Generator decision and constraints

Qwen3.5-4B Q4_K_S remains the V1 local generator. No prompt, evidence
packaging, retrieval, model, decoding, citation repair, or abstention
optimization was started. No generation or retrieval benchmark was rerun.

The original DRAFT review pack is preserved. The aggregate machine summary is
`dataset/evaluation/results/rag-answer-v2-expanded-human-review-summary.json`.
The incomplete explicit-label artifact is
`dataset/evaluation/results/rag-answer-v2-expanded-human-review-known-labels.jsonl`;
it is not a substitute for a complete 100-row label map.

## Machine summary snapshot

```json
{summary_json}
```

## Next

Stage 14C — BANK-RAG V1 Baseline Closure. No retrieval or generation research
is authorized by this freeze.
"""
    return frozen_review, freeze_doc


def main() -> None:
    inputs = validate_inputs()
    summary = build_summary(inputs)
    known_rows = build_known_labels(inputs)
    frozen_review, freeze_doc = render_freeze_docs(summary, known_rows)

    write_json(SUMMARY_PATH, summary)
    write_text(
        KNOWN_LABELS_PATH,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in known_rows),
    )
    write_text(FROZEN_REVIEW_PATH, frozen_review)
    write_text(STAGE_DOC_PATH, freeze_doc)
    print(
        json.dumps(
            {
                "summary": str(SUMMARY_PATH),
                "known_labels": str(KNOWN_LABELS_PATH),
                "known_label_rows": len(known_rows),
                "frozen_review": str(FROZEN_REVIEW_PATH),
                "stage_document": str(STAGE_DOC_PATH),
                "gold_sha256": EXPECTED_GOLD_SHA256,
                "pilot_sha256": EXPECTED_PILOT_SHA256,
                "generator_sha256": GENERATOR_SHA256,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
