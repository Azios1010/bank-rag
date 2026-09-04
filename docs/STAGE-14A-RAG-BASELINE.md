# Stage 14A — End-to-End Grounded RAG Baseline

This is the first local end-to-end grounded-answering baseline. Retrieval is frozen from Stage 13F; semantic answer quality remains pending human review.

## Frozen identities

- Gold: `dataset/evaluation/retrieval-v2-gold-expanded.jsonl`; SHA-256 `1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69`; 100 REVIEWED records.
- Corpus: `policy-corpus-v2`, 1610 canonical chunks; manifest SHA-256 `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`.
- Embedding: Qwen3-Embedding-0.6B, 1024D, frozen Stage 10 artifacts; no regeneration.
- Reranker: Qwen3-Reranker-0.6B Q8_0, frozen local GGUF; no model download.
- Generator: local `D:\llm-models\Qwen_Qwen3.5-4B-Q4_K_S.gguf`; SHA-256 `3a6e5e8144696a87d17f136b06fce7fe5008a42737938056df13e11ddba4a01b`; llama.cpp/Vulkan1/RTX 2050.

## Frozen retrieval and prompt contract

- Canonical query formatter → llama.cpp embedding → Supabase `public.match_policy_chunks` Top20 → llama.cpp Qwen3 reranker → ordered Top5.
- Candidate K = 20; final K = 5; no FTS, hybrid, RRF, fallback, gold injection, or manual result correction.
- Generator receives the original question and only the ordered E1–E5 context. It does not receive gold IDs, retrieval ranks, or evaluation diagnostics.
- Every material claim is instructed to cite `[E1]`–`[E5]`; insufficient evidence may be explicitly acknowledged.

## Automated structural results

- Answers attempted/generated: `100` / `100`; technical failures: `0`; retries: `0`.
- Answers with valid citations: `94`; zero citations: `4`; invalid citation outputs: `2`.
- Abstentions detected: `0`; gold present in supplied Top5: `97`; absent: `3`.
- These are structural diagnostics, not correctness, groundedness, hallucination, or citation-quality scores.

## Latency

- Generation p50/p95/mean: `13850.037249998422` / `25595.01972499711` / `14073.419899999353` ms.
- Classification: LOCAL RTX 2050 REFERENCE LATENCY; not a production SLA.

## Known retrieval limitations

- `stage12a-024`, `stage13e-040`, and `stage13e-042` remain known Top20 candidate-generation failures. Their approved evidence was not injected.

## Human review

- Review pack: `docs/STAGE-14A-RAG-ANSWER-REVIEW.md`.
- Semantic fields remain DRAFT and unassigned.

## Artifacts

- Live candidate freeze: `dataset/evaluation/results/rag-v2-expanded-top20-candidates.jsonl`.
- Frozen Top5 evidence: `dataset/evaluation/results/rag-v2-expanded-top5-evidence.jsonl`.
- Answer traces: `dataset/evaluation/results/rag-answer-v2-expanded-traces.jsonl`.
- Structural summary: `dataset/evaluation/results/rag-answer-v2-expanded-summary.json`.
- Repeatability subset: `dataset/evaluation/results/rag-answer-v2-expanded-repeatability.jsonl`.

## Predeclared repeatability subset

- Every tenth query in canonical order; records: `['stage12a-010', 'stage12a-020', 'stage13e-030', 'stage13e-040', 'stage13e-050', 'stage13e-060', 'stage13e-070', 'stage13e-080', 'stage13e-090', 'stage13e-100']`.
- Byte-identical answers: `True`; citation-structure agreement: `1.0`; abstention agreement: `1.0`.
