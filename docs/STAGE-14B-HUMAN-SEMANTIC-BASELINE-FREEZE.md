# Stage 14B — Human Semantic Baseline Freeze

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
| Gold SHA-256 | `1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69` |
| Retrieval | Qwen3-Embedding-0.6B → vector Top20 → Qwen3-Reranker-0.6B Q8_0 → Top5 |
| Candidate/final K | 20 / 5 |
| Corpus | `policy-corpus-v2`, 1610 chunks |
| Corpus manifest SHA-256 | `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a` |
| Embedding artifact SHA-256 | `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c` |
| Embedding manifest SHA-256 | `cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863` |
| Reranker SHA-256 | `22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48` |
| Generator | Qwen3.5-4B Q4_K_S, local llama.cpp/Vulkan1 RTX 2050 |
| Generator SHA-256 | `3a6e5e8144696a87d17f136b06fce7fe5008a42737938056df13e11ddba4a01b` |

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

`stage12a-004, stage12a-011, stage12a-013, stage12a-014, stage13e-037, stage13e-043, stage13e-049, stage13e-050, stage13e-059, stage13e-065, stage13e-068, stage13e-073, stage13e-080, stage13e-083, stage13e-084, stage13e-090, stage13e-091, stage13e-099`

Citation-primary IDs are frozen exactly as supplied:

`stage12a-003, stage12a-008, stage12a-019, stage13e-034, stage13e-036, stage13e-038`

Known truncation IDs: `stage12a-004, stage12a-013, stage12a-024, stage13e-050, stage13e-059, stage13e-091, stage13e-099`. This is a known Stage
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
{
  "abstention": {
    "APPROPRIATE": 0,
    "MISSING_WHEN_REQUIRED": 4,
    "N/A": 96,
    "UNNECESSARY": 0
  },
  "citation_primary_ids": [
    "stage12a-003",
    "stage12a-008",
    "stage12a-019",
    "stage13e-034",
    "stage13e-036",
    "stage13e-038"
  ],
  "citation_quality": {
    "CORRECT": 81,
    "INCORRECT": 7,
    "PARTIAL": 12
  },
  "clean_answers": 72,
  "correctness": {
    "FAIL": 4,
    "PARTIAL": 18,
    "PASS": 78
  },
  "failure_source": {
    "CITATION": 6,
    "GENERATION": 19,
    "MIXED": 3,
    "NONE": 72,
    "RERANKING": 0,
    "RETRIEVAL": 0
  },
  "frozen_identities": {
    "corpus": "policy-corpus-v2",
    "corpus_chunks": 1610,
    "corpus_manifest_sha256": "b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a",
    "embedding_artifact_sha256": "3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c",
    "embedding_manifest_sha256": "cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863",
    "generator_sha256": "3a6e5e8144696a87d17f136b06fce7fe5008a42737938056df13e11ddba4a01b",
    "pilot_sha256": "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a",
    "reranker_sha256": "22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48"
  },
  "frozen_retrieval": {
    "architecture": "Qwen3-Embedding-0.6B → vector Top20 → Qwen3-Reranker-0.6B Q8_0 → Top5",
    "candidate_k": 20,
    "changed": false,
    "final_k": 5,
    "reference_hit_at_5": 0.97
  },
  "full_failure_ids": [
    "stage12a-002",
    "stage12a-024",
    "stage13e-040",
    "stage13e-042"
  ],
  "full_failures": [
    {
      "evaluation_id": "stage12a-002",
      "failure_source": "GENERATION",
      "gold_present_in_top5": true,
      "note": "Generator reversed the legal polarity of the prohibited-purpose evidence."
    },
    {
      "evaluation_id": "stage12a-024",
      "failure_source": "MIXED",
      "gold_present_in_top5": false,
      "note": "Gold evidence was absent and the answer did not abstain."
    },
    {
      "evaluation_id": "stage13e-040",
      "failure_source": "MIXED",
      "gold_present_in_top5": false,
      "note": "Gold evidence was absent and the answer went beyond supplied evidence."
    },
    {
      "evaluation_id": "stage13e-042",
      "failure_source": "MIXED",
      "gold_present_in_top5": false,
      "note": "Gold evidence was absent; unsupported approving authorities were asserted without a valid E1-E5 citation."
    }
  ],
  "generator_decision": "Qwen3.5-4B Q4_K_S retained as the V1 local generator",
  "gold": {
    "path": "dataset/evaluation/retrieval-v2-gold-expanded.jsonl",
    "sha256": "1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69",
    "status_counts": {
      "DRAFT": 0,
      "REJECTED": 0,
      "REVIEWED": 100
    }
  },
  "gold_absent_subset": {
    "FAIL": 3,
    "correct_abstentions": 0,
    "count": 3,
    "ids": [
      "stage12a-024",
      "stage13e-040",
      "stage13e-042"
    ]
  },
  "gold_present_subset": {
    "FAIL": 1,
    "PARTIAL": 18,
    "PASS": 78,
    "count": 97
  },
  "groundedness": {
    "FULLY_GROUNDED": 87,
    "PARTIALLY_GROUNDED": 12,
    "UNGROUNDED": 1
  },
  "human_review_authoritative": true,
  "latency_ms": {
    "classification": "LOCAL RTX 2050 REFERENCE ONLY — NOT A PRODUCTION SLA",
    "generation_mean": 14073.42,
    "generation_p50": 13850.037,
    "generation_p95": 25595.02,
    "tokens_per_second_p50": 21.418,
    "ttft_p50": 1544.523
  },
  "partial_ids": [
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
    "stage13e-099"
  ],
  "per_query_label_materialization": {
    "explanation": "Authoritative aggregate freeze and explicitly listed per-query classifications are materialized; a complete 100-record human label map is not available mechanically.",
    "status": "PARTIAL"
  },
  "per_scope_correctness": {
    "collateral_appraisal": {
      "FAIL": 1,
      "PARTIAL": 3,
      "PASS": 16
    },
    "credit": {
      "FAIL": 1,
      "PARTIAL": 2,
      "PASS": 17
    },
    "customer_relationship": {
      "FAIL": 0,
      "PARTIAL": 4,
      "PASS": 16
    },
    "legal_compliance": {
      "FAIL": 0,
      "PARTIAL": 5,
      "PASS": 15
    },
    "risk_management": {
      "FAIL": 2,
      "PARTIAL": 4,
      "PASS": 14
    }
  },
  "preserved_artifacts": {
    "complete_per_query_label_artifact_created": false,
    "original_review_pack": "docs/STAGE-14A-RAG-ANSWER-REVIEW.md",
    "original_review_pack_sha256": "6f0585d400ea26326c37b4c0da39e3c09e83f609120a96bb46ac26391514c206"
  },
  "provenance_metadata_issue": {
    "location": "Stage 14A evidence serialization / CanonicalV2RetrievalResult.source_type mapping",
    "mutation_performed": false,
    "observed": "82 SCOPED synthetic evidence items in the Stage 14A Top5 artifact are serialized as real_regulation.",
    "proposed_fix": "Resolve presentation provenance from trusted frozen source identity when serializing evidence, then regenerate only a separately versioned presentation artifact after review. Do not rewrite the frozen Stage 14A baseline in this stage.",
    "root_cause": "The canonical retrieval DTO source_type falls back to real_regulation unless RPC metadata contains provenance_kind; the returned synthetic source metadata does not expose that key. Frozen local corpus source metadata identifies all three synthetic sources as synthetic.",
    "status": "KNOWN METADATA / PRESENTATION BUG"
  },
  "record_count": 100,
  "semantic_judge": "human",
  "stage": "14B — Human Semantic Review Freeze",
  "stage14a_structural": {
    "abstentions_detected": 0,
    "answers_attempted": 100,
    "answers_generated": 100,
    "answers_with_invalid_citation_ids": 2,
    "answers_with_valid_citations": 94,
    "answers_with_zero_citations": 4,
    "gold_absent_in_top5": 3,
    "gold_present_in_top5": 97,
    "technical_failures": 0,
    "technical_retries": 0
  },
  "truncation_ids": [
    "stage12a-004",
    "stage12a-013",
    "stage12a-024",
    "stage13e-050",
    "stage13e-059",
    "stage13e-091",
    "stage13e-099"
  ]
}
```

## Next

Stage 14C — BANK-RAG V1 Baseline Closure. No retrieval or generation research
is authorized by this freeze.
