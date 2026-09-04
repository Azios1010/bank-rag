"""Stage 14A: local end-to-end grounded RAG baseline.

The script deliberately separates the expensive GPU phases:

``candidates``
    one canonical query embedding and one canonical vector Top20 RPC call per
    frozen gold query;
``evidence``
    rerank the frozen Top20 candidates and freeze the resulting Top5 evidence;
``smoke``/``generate``
    use only the frozen evidence with the local Qwen3.5 generation server;
``repeat``
    repeat a predeclared every-tenth-query subset for descriptive stability.

No evaluation label is sent to the generation model.  The script performs
structural validation only; semantic answer fields in the human-review pack
remain unassigned and DRAFT.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import sys
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.eval.gold_v2 import CanonicalGoldValidator, FrozenCorpusV2
from app.eval.llama_v2_query_embedding import LlamaV2QueryEmbeddingAdapter
from app.eval.llama_v2_reranker import LlamaV2RerankerAdapter
from app.services.canonical_v2_evidence import (
    CanonicalV2EvidenceRetriever,
    serialize_citations,
)
from app.services.supabase_v2_retriever import (
    CanonicalV2RetrievalResult,
    CanonicalV2Retriever,
    normalize_specialist_scope,
)
from scripts.run_stage13b0_candidate_recall import (
    read_remote_state,
    validate_result_contract,
)

GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.jsonl"
PILOT_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
CORPUS_MANIFEST_PATH = ROOT / "dataset/manifests/policy-corpus-v2-manifest.json"
EMBEDDING_ARTIFACT_PATH = ROOT / "dataset/embeddings/v2/embeddings.parquet"
EMBEDDING_MANIFEST_PATH = ROOT / "dataset/embeddings/v2/embedding-manifest.json"
RESULTS_DIR = ROOT / "dataset/evaluation/results"
CANDIDATE_PATH = RESULTS_DIR / "rag-v2-expanded-top20-candidates.jsonl"
EVIDENCE_PATH = RESULTS_DIR / "rag-v2-expanded-top5-evidence.jsonl"
TRACE_PATH = RESULTS_DIR / "rag-answer-v2-expanded-traces.jsonl"
SUMMARY_PATH = RESULTS_DIR / "rag-answer-v2-expanded-summary.json"
REPEAT_PATH = RESULTS_DIR / "rag-answer-v2-expanded-repeatability.jsonl"
PROMPT_DOC_PATH = ROOT / "docs/STAGE-14A-GENERATION-PROMPT.md"
REVIEW_PATH = ROOT / "docs/STAGE-14A-RAG-ANSWER-REVIEW.md"
STAGE_DOC_PATH = ROOT / "docs/STAGE-14A-RAG-BASELINE.md"

EXPECTED_GOLD_SHA256 = "1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69"
EXPECTED_PILOT_SHA256 = "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"
EXPECTED_CORPUS_MANIFEST_SHA256 = "b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a"
EXPECTED_EMBEDDING_ARTIFACT_SHA256 = "3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c"
EXPECTED_EMBEDDING_MANIFEST_SHA256 = "cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863"
EXPECTED_CHUNK_COUNT = 1610
EXPECTED_QUERY_COUNT = 100
EXPECTED_CANDIDATE_K = 20
EXPECTED_FINAL_K = 5
SUPPORTED_SCOPES = {
    "credit",
    "risk_management",
    "legal_compliance",
    "customer_relationship",
    "collateral_appraisal",
}
KNOWN_FAILURES = {"stage12a-024", "stage13e-040", "stage13e-042"}

RERANKER_MODEL_PATH = Path(r"D:\llm-models\qwen3-reranker-0.6b-q8_0.gguf")
RERANKER_MODEL_SHA256 = "22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48"
RERANKER_BUILD = "0.2.0-dev (build 10603, commit c060ca974)"
RERANKER_ENDPOINT = "http://127.0.0.1:8082"

GENERATOR_MODEL_PATH = Path(r"D:\llm-models\Qwen_Qwen3.5-4B-Q4_K_S.gguf")
GENERATOR_MODEL_SHA256 = "3a6e5e8144696a87d17f136b06fce7fe5008a42737938056df13e11ddba4a01b"
GENERATOR_MODEL_BYTES = 2846156768
GENERATOR_BUILD = RERANKER_BUILD
GENERATOR_ENDPOINT = "http://127.0.0.1:8080"
GENERATOR_ALIAS = "qwen3.5-4b-local"
GENERATOR_CONTEXT = 4096
GENERATOR_TEMPERATURE = 0.0
GENERATOR_TOP_P = 1.0
GENERATOR_SEED = 42
GENERATOR_MAX_TOKENS = 512
GENERATOR_REASONING = "off"

QUERY_INSTRUCTION = (
    "Given a Vietnamese banking legal question, retrieve authoritative passages "
    "that directly support the answer."
)
SYSTEM_PROMPT = """You are a Vietnamese banking policy and regulatory assistant.

Answer the user's question using ONLY the evidence provided.

Rules:

1. Do not use outside knowledge.
2. Do not make claims unsupported by the supplied evidence.
3. Cite every material factual or legal claim using [E1]...[E5].
4. Never cite evidence that was not supplied.
5. Do not invent article numbers, thresholds, dates, exceptions, authorities, conditions, or internal rules.
6. Distinguish authoritative regulation from internal bank policy where relevant.
7. If the evidence is insufficient to answer the question fully, explicitly say that the supplied evidence is insufficient.
8. Do not guess missing information.
9. Answer in concise, natural Vietnamese.
10. Output only the final answer. Do not output internal reasoning."""
USER_PROMPT_TEMPLATE = """QUESTION:
{question}

EVIDENCE:
{evidence}

ANSWER REQUIREMENT:

Answer only from the supplied evidence and cite supporting evidence with [E1]...[E5]."""
ABSTENTION_PHRASES = (
    "chưa đủ căn cứ",
    "chưa đủ thông tin",
    "không đủ căn cứ",
    "không đủ thông tin",
    "chưa đủ bằng chứng",
)
CITATION_RE = re.compile(r"\[E(\d+)\]", re.IGNORECASE)


class Stage14AError(RuntimeError):
    """Raised when a frozen Stage 14A contract is violated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def status_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def gold_ids(record: dict[str, Any]) -> list[str]:
    return list(record["expected_canonical_chunk_ids"])


def first_rank(ranks: dict[str, int | None]) -> int | None:
    present = [rank for rank in ranks.values() if rank is not None]
    return min(present) if present else None


def rank_gold(ids: list[str], expected: list[str]) -> dict[str, int | None]:
    ranks = {chunk_id: rank for rank, chunk_id in enumerate(ids, 1)}
    return {chunk_id: ranks.get(chunk_id) for chunk_id in expected}


def validate_frozen_inputs() -> tuple[list[dict[str, Any]], FrozenCorpusV2, dict[str, Any]]:
    if sha256_file(GOLD_PATH) != EXPECTED_GOLD_SHA256:
        raise Stage14AError("expanded gold SHA-256 does not match the frozen identity")
    if sha256_file(PILOT_PATH) != EXPECTED_PILOT_SHA256:
        raise Stage14AError("Stage 12A pilot SHA-256 changed")
    expected_files = {
        CORPUS_MANIFEST_PATH: EXPECTED_CORPUS_MANIFEST_SHA256,
        EMBEDDING_ARTIFACT_PATH: EXPECTED_EMBEDDING_ARTIFACT_SHA256,
        EMBEDDING_MANIFEST_PATH: EXPECTED_EMBEDDING_MANIFEST_SHA256,
    }
    for path, expected in expected_files.items():
        if sha256_file(path) != expected:
            raise Stage14AError(f"frozen identity changed: {path}")
    for path, expected in (
        (RERANKER_MODEL_PATH, RERANKER_MODEL_SHA256),
        (GENERATOR_MODEL_PATH, GENERATOR_MODEL_SHA256),
    ):
        if not path.is_file() or sha256_file(path) != expected:
            raise Stage14AError(f"local model identity changed or is missing: {path}")
    if GENERATOR_MODEL_PATH.stat().st_size != GENERATOR_MODEL_BYTES:
        raise Stage14AError("generation GGUF byte size changed")

    corpus = FrozenCorpusV2()
    records = CanonicalGoldValidator(corpus).parse_file(GOLD_PATH)
    if len(records) != EXPECTED_QUERY_COUNT:
        raise Stage14AError(f"expected 100 REVIEWED gold records, got {len(records)}")
    ids = [record["evaluation_id"] for record in records]
    questions = [record["query"] for record in records]
    if len(set(ids)) != len(ids) or len(set(questions)) != len(questions):
        raise Stage14AError("gold contains duplicate evaluation IDs or questions")
    if any(status_value(record["status"]) != "REVIEWED" for record in records):
        raise Stage14AError("expanded gold contains a non-REVIEWED record")
    scopes = {normalize_specialist_scope(record["specialist_scope"]) for record in records}
    if scopes != SUPPORTED_SCOPES:
        raise Stage14AError(f"unsupported/missing scopes: {sorted(scopes)}")
    if any(record["specialist_scope"] == "BankingOperations" for record in records):
        raise Stage14AError("BankingOperations must remain rejected")
    expected_gold = {chunk_id for record in records for chunk_id in gold_ids(record)}
    if not expected_gold.issubset(corpus.by_id):
        raise Stage14AError("gold contains a non-V2 canonical ID")
    stage004 = next(record for record in records if record["evaluation_id"] == "stage12a-004")
    if len(gold_ids(stage004)) != 2 or set(gold_ids(stage004)) != {
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    }:
        raise Stage14AError("stage12a-004 two-gold contract changed")
    if len(corpus.rows) != EXPECTED_CHUNK_COUNT or len(corpus.by_id) != EXPECTED_CHUNK_COUNT:
        raise Stage14AError("local Corpus V2 is not exactly 1610 unique chunks")

    from app.config import get_settings

    remote = read_remote_state(get_settings())
    for key, expected in {
        "documents": 10,
        "chunks": 1610,
        "distinct_ids": 1610,
        "vectors": 1610,
        "shared": 1573,
        "scoped": 37,
        "scope_rows": 125,
        "dimension_failures": 0,
        "null_search_documents": 0,
    }.items():
        if remote.get(key) != expected:
            raise Stage14AError(f"remote canonical state mismatch for {key}: {remote.get(key)}")
    if remote.get("hnsw_ef_search") != "40":
        raise Stage14AError(f"hnsw.ef_search changed: {remote.get('hnsw_ef_search')}")
    if remote.get("corpus_name") != "policy-corpus-v2" or remote.get(
        "corpus_manifest_sha256"
    ) != EXPECTED_CORPUS_MANIFEST_SHA256:
        raise Stage14AError("remote corpus identity mismatch")
    if remote.get("embedding_model") != "Qwen3-Embedding-0.6B" or remote.get(
        "embedding_dimension"
    ) != 1024:
        raise Stage14AError("remote embedding identity mismatch")
    return records, corpus, remote


def candidate_payload(result: CanonicalV2RetrievalResult, rank: int) -> dict[str, Any]:
    return {
        "canonical_chunk_id": result.canonical_chunk_id,
        "rank": rank,
        "content": result.content,
        "similarity": float(result.similarity),
        "document_source_id": result.document_source_id,
        "document_version_id": result.document_version_id,
        "document_title": result.document_title,
        "heading_path": list(result.heading_path),
        "locator": dict(result.locator),
        "namespace": result.namespace,
        "visibility": result.visibility,
        "metadata": dict(result.metadata),
    }


def reconstruct_candidate(item: dict[str, Any]) -> CanonicalV2RetrievalResult:
    return CanonicalV2RetrievalResult(
        canonical_chunk_id=item["canonical_chunk_id"],
        content=item["content"],
        similarity=float(item["similarity"]),
        document_source_id=item["document_source_id"],
        document_version_id=item["document_version_id"],
        document_title=item["document_title"],
        heading_path=list(item["heading_path"]),
        locator=dict(item["locator"]),
        namespace=item["namespace"],
        visibility=item["visibility"],
        metadata=dict(item["metadata"]),
    )


def collect_candidates(
    records: list[dict[str, Any]], corpus: FrozenCorpusV2
) -> dict[str, Any]:
    adapter = LlamaV2QueryEmbeddingAdapter()
    retriever = CanonicalV2Retriever(embedding_adapter=adapter)
    traces: list[dict[str, Any]] = []
    for record in records:
        evaluation_id = record["evaluation_id"]
        scope = normalize_specialist_scope(record["specialist_scope"])
        embedding_started = time.perf_counter()
        vector = adapter.embed_query(record["query"])
        embedding_ms = (time.perf_counter() - embedding_started) * 1000
        norm = math.sqrt(sum(value * value for value in vector))
        if len(vector) != 1024 or not math.isfinite(norm) or not math.isclose(
            norm, 1.0, rel_tol=0.0, abs_tol=1e-4
        ):
            raise Stage14AError(f"invalid canonical query vector for {evaluation_id}")
        vector_hash = hashlib.sha256(
            json.dumps(vector, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        retrieval_started = time.perf_counter()
        results = retriever.retrieve_with_query_vector(vector, scope, k=EXPECTED_CANDIDATE_K)
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        if len(results) != EXPECTED_CANDIDATE_K:
            raise Stage14AError(f"{evaluation_id} returned {len(results)} vector candidates")
        ids = [result.canonical_chunk_id for result in results]
        if len(set(ids)) != EXPECTED_CANDIDATE_K or any(chunk_id not in corpus.by_id for chunk_id in ids):
            raise Stage14AError(f"{evaluation_id} has invalid/duplicate V2 candidates")
        for result in results:
            validate_result_contract(result, corpus, scope)
        expected = gold_ids(record)
        ranks = rank_gold(ids, expected)
        traces.append(
            {
                "evaluation_id": evaluation_id,
                "scope": scope,
                "question": record["query"],
                "gold_canonical_chunk_ids": expected,
                "gold_present_in_top5": any(rank is not None and rank <= 5 for rank in ranks.values()),
                "vector_gold_ranks": {key: value if value is not None else ">20" for key, value in ranks.items()},
                "vector_first_gold_rank": first_rank(ranks) or ">20",
                "query_vector": {"dimension": len(vector), "norm": norm, "sha256": vector_hash},
                "candidate_depth": EXPECTED_CANDIDATE_K,
                "candidate_source": "canonical llama.cpp query embedding -> public.match_policy_chunks",
                "rpc": "public.match_policy_chunks",
                "vector_candidates": [candidate_payload(result, rank) for rank, result in enumerate(results, 1)],
                "timing_ms": {"embedding": embedding_ms, "vector_retrieval": retrieval_ms},
                "scope_contract_satisfied": True,
                "v2_only": True,
                "fts_used": False,
                "hybrid_used": False,
                "legacy_tables_used": False,
            }
        )
    if len(traces) != EXPECTED_QUERY_COUNT or any(
        len(trace["vector_candidates"]) != EXPECTED_CANDIDATE_K for trace in traces
    ):
        raise Stage14AError("candidate freeze count invariant failed")
    payload = {
        "schema_version": "stage14a-vector-top20-candidates-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gold_path": str(GOLD_PATH.relative_to(ROOT)).replace("\\", "/"),
        "gold_sha256": EXPECTED_GOLD_SHA256,
        "corpus": "policy-corpus-v2",
        "corpus_manifest_sha256": EXPECTED_CORPUS_MANIFEST_SHA256,
        "query_count": EXPECTED_QUERY_COUNT,
        "candidate_depth": EXPECTED_CANDIDATE_K,
        "traces": traces,
    }
    write_jsonl(CANDIDATE_PATH, [payload, *traces])
    return {"metadata": payload, "traces": traces}


def load_candidates(records: list[dict[str, Any]], corpus: FrozenCorpusV2) -> list[dict[str, Any]]:
    if not CANDIDATE_PATH.is_file():
        raise Stage14AError(f"candidate artifact missing: {CANDIDATE_PATH}")
    rows = read_jsonl(CANDIDATE_PATH)
    if not rows or rows[0].get("schema_version") != "stage14a-vector-top20-candidates-v1":
        raise Stage14AError("candidate artifact header is invalid")
    traces = rows[1:]
    if len(traces) != EXPECTED_QUERY_COUNT:
        raise Stage14AError("candidate artifact does not contain 100 traces")
    expected_ids = [record["evaluation_id"] for record in records]
    if [trace.get("evaluation_id") for trace in traces] != expected_ids:
        raise Stage14AError("candidate artifact ordering does not match frozen gold")
    for record, trace in zip(records, traces):
        candidates = trace.get("vector_candidates")
        if trace.get("candidate_depth") != EXPECTED_CANDIDATE_K or not isinstance(candidates, list):
            raise Stage14AError(f"{record['evaluation_id']} candidate depth is invalid")
        if len(candidates) != EXPECTED_CANDIDATE_K:
            raise Stage14AError(f"{record['evaluation_id']} does not have exactly 20 candidates")
        ids = [item.get("canonical_chunk_id") for item in candidates]
        if len(set(ids)) != EXPECTED_CANDIDATE_K or any(chunk_id not in corpus.by_id for chunk_id in ids):
            raise Stage14AError(f"{record['evaluation_id']} candidate identity is invalid")
        if trace.get("gold_canonical_chunk_ids") != gold_ids(record):
            raise Stage14AError(f"{record['evaluation_id']} gold diagnostic changed")
        if trace.get("scope") != normalize_specialist_scope(record["specialist_scope"]):
            raise Stage14AError(f"{record['evaluation_id']} scope changed")
        if trace.get("rpc") != "public.match_policy_chunks" or trace.get("fts_used") or trace.get("hybrid_used"):
            raise Stage14AError("candidate provenance is not canonical vector-only")
        for item in candidates:
            result = reconstruct_candidate(item)
            validate_result_contract(result, corpus, trace["scope"])
    return traces


def format_locator(locator: dict[str, Any], heading_path: list[Any]) -> str:
    fields = []
    for name in ("article", "clause", "point"):
        if locator.get(name) is not None:
            fields.append(f"{name} {locator[name]}")
    if heading_path:
        fields.append(" / ".join(str(item) for item in heading_path))
    return "; ".join(fields) if fields else "Không có định vị chi tiết trong bản ghi."


def prompt_evidence_item(item: dict[str, Any]) -> str:
    return "\n".join(
        (
            f"[{item['citation_id']}]",
            f"Source: {item['title']}",
            f"Locator: {format_locator(item['locator'], item['heading_path'])}",
            "Text:",
            item["content"],
        )
    )


def format_evidence_for_prompt(evidence: list[dict[str, Any]]) -> str:
    if not 1 <= len(evidence) <= EXPECTED_FINAL_K:
        raise Stage14AError("generation evidence must contain one through five items")
    expected = [f"E{index}" for index in range(1, len(evidence) + 1)]
    if [item.get("citation_id") for item in evidence] != expected:
        raise Stage14AError("evidence citation order is not contiguous E1..E5")
    if any("canonical_chunk_id" not in item for item in evidence):
        raise Stage14AError("internal evidence mapping is incomplete")
    return "\n\n".join(prompt_evidence_item(item) for item in evidence)


def build_generation_messages(question: str, evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    serialized = format_evidence_for_prompt(evidence)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_PROMPT_TEMPLATE.format(question=question, evidence=serialized),
        },
    ]
    # This is a conservative, deterministic preflight.  No evidence is silently
    # dropped; an over-budget prompt fails before generation begins.
    estimated_tokens = math.ceil(sum(len(message["content"]) for message in messages) / 4)
    if estimated_tokens + GENERATOR_MAX_TOKENS > GENERATOR_CONTEXT:
        raise Stage14AError(f"prompt exceeds context budget: estimate={estimated_tokens}")
    return messages


class LocalQwenGenerationAdapter:
    """Minimal local-only OpenAI-compatible chat adapter."""

    def __init__(self, base_url: str = GENERATOR_ENDPOINT, timeout_seconds: float = 180.0) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
        self.timeout_seconds = timeout_seconds

    def generate(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        body = {
            "model": GENERATOR_ALIAS,
            "messages": messages,
            "temperature": GENERATOR_TEMPERATURE,
            "top_p": GENERATOR_TOP_P,
            "seed": GENERATOR_SEED,
            "max_tokens": GENERATOR_MAX_TOKENS,
            "n": 1,
            "stream": False,
        }
        request = Request(
            self.endpoint,
            data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            headers={"Accept": "application/json", "Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if not isinstance(status, int) or not 200 <= status < 300:
                    raise Stage14AError(f"generator returned HTTP {status}")
                decoded = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise Stage14AError(f"generator returned HTTP {exc.code}: {detail}") from None
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Stage14AError("local generator request failed") from exc
        if not isinstance(decoded, dict) or not isinstance(decoded.get("choices"), list) or not decoded["choices"]:
            raise Stage14AError("malformed local generator response")
        choice = decoded["choices"][0]
        if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
            raise Stage14AError("generator response choice is malformed")
        content = choice["message"].get("content")
        if not isinstance(content, str) or not content.strip():
            raise Stage14AError("generator returned empty content")
        decoded["_answer"] = content.strip()
        return decoded


def parse_citations(answer: str) -> tuple[list[str], list[str]]:
    found = [f"E{int(value)}" for value in CITATION_RE.findall(answer)]
    valid: list[str] = []
    invalid: list[str] = []
    for citation in found:
        if citation in {"E1", "E2", "E3", "E4", "E5"}:
            if citation not in valid:
                valid.append(citation)
        elif citation not in invalid:
            invalid.append(citation)
    # Catch explicit bracket citations outside the accepted syntax as invalid.
    for raw in re.findall(r"\[E[^\]]+\]", answer, flags=re.IGNORECASE):
        normalized = raw.upper().strip("[]")
        if not re.fullmatch(r"\[E[1-5]\]", raw, flags=re.IGNORECASE) and normalized not in invalid:
            invalid.append(normalized)
    return valid, invalid


def detect_abstention(answer: str) -> bool:
    lowered = answer.casefold()
    return any(phrase in lowered for phrase in ABSTENTION_PHRASES)


def citation_structure(answer: str, supplied: list[dict[str, Any]]) -> dict[str, Any]:
    valid, invalid = parse_citations(answer)
    allowed = {item["citation_id"] for item in supplied}
    valid_supplied = [item for item in valid if item in allowed]
    return {
        "valid_citation_ids": valid_supplied,
        "invalid_citation_ids": invalid,
        "citation_count": len(valid_supplied),
        "only_supplied_evidence": not invalid and set(valid_supplied).issubset(allowed),
    }


def evidence_from_candidate_trace(
    trace: dict[str, Any], corpus: FrozenCorpusV2
) -> list[dict[str, Any]]:
    candidates = [reconstruct_candidate(item) for item in trace["vector_candidates"]]
    service = CanonicalV2EvidenceRetriever(
        vector_retriever=object(), reranker=LlamaV2RerankerAdapter(base_url=RERANKER_ENDPOINT)
    )
    ranked = service.rerank_candidates(trace["question"], trace["scope"], candidates)
    evidence = serialize_citations(ranked)
    if len(evidence) != EXPECTED_FINAL_K:
        raise Stage14AError(f"{trace['evaluation_id']} did not yield exactly five evidence items")
    for item in evidence:
        if item["canonical_chunk_id"] not in corpus.by_id:
            raise Stage14AError("reranker produced non-V2 evidence")
    return evidence


def freeze_evidence(records: list[dict[str, Any]], corpus: FrozenCorpusV2) -> list[dict[str, Any]]:
    candidate_traces = load_candidates(records, corpus)
    all_rows: list[dict[str, Any]] = []
    for trace in candidate_traces:
        started = time.perf_counter()
        evidence = evidence_from_candidate_trace(trace, corpus)
        reranker_ms = (time.perf_counter() - started) * 1000
        gold = set(trace["gold_canonical_chunk_ids"])
        evidence_ids = [item["canonical_chunk_id"] for item in evidence]
        all_rows.append(
            {
                "evaluation_id": trace["evaluation_id"],
                "scope": trace["scope"],
                "question": trace["question"],
                "evidence": evidence,
                "gold_present_in_top5": bool(gold.intersection(evidence_ids)),
                "gold_canonical_chunk_ids": trace["gold_canonical_chunk_ids"],
                "known_retrieval_failure": trace["evaluation_id"] in KNOWN_FAILURES,
                "candidate_source": "frozen canonical vector Top20",
                "candidate_depth": EXPECTED_CANDIDATE_K,
                "reranker": "Qwen3-Reranker-0.6B Q8_0 / llama.cpp",
                "timing_ms": {
                    "embedding": trace["timing_ms"]["embedding"],
                    "vector_retrieval": trace["timing_ms"]["vector_retrieval"],
                    "reranker": reranker_ms,
                    "retrieval_total": trace["timing_ms"]["embedding"]
                    + trace["timing_ms"]["vector_retrieval"]
                    + reranker_ms,
                },
                "scope_contract_satisfied": True,
                "v2_only": True,
                "fts_used": False,
                "hybrid_used": False,
                "gold_metadata_not_for_prompt": True,
            }
        )
    if len(all_rows) != EXPECTED_QUERY_COUNT or any(len(row["evidence"]) != EXPECTED_FINAL_K for row in all_rows):
        raise Stage14AError("Top5 evidence freeze count invariant failed")
    write_jsonl(EVIDENCE_PATH, all_rows)
    return all_rows


def load_evidence() -> list[dict[str, Any]]:
    if not EVIDENCE_PATH.is_file():
        raise Stage14AError(f"evidence artifact missing: {EVIDENCE_PATH}")
    rows = read_jsonl(EVIDENCE_PATH)
    if len(rows) != EXPECTED_QUERY_COUNT:
        raise Stage14AError("evidence artifact must contain exactly 100 records")
    expected_ids = [f"stage12a-{index:03d}" for index in range(1, 26)] + [
        f"stage13e-{index:03d}" for index in range(26, 101)
    ]
    if [row.get("evaluation_id") for row in rows] != expected_ids:
        raise Stage14AError("evidence artifact ordering/IDs are invalid")
    for row in rows:
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or len(evidence) != EXPECTED_FINAL_K:
            raise Stage14AError(f"{row.get('evaluation_id')} must have exactly five evidence items")
        if [item.get("citation_id") for item in evidence] != ["E1", "E2", "E3", "E4", "E5"]:
            raise Stage14AError("evidence citation order is not E1..E5")
        if len({item.get("canonical_chunk_id") for item in evidence}) != EXPECTED_FINAL_K:
            raise Stage14AError("evidence contains duplicate canonical IDs")
    return rows


def generation_trace(row: dict[str, Any], response: dict[str, Any], latency_ms: float, retry_count: int) -> dict[str, Any]:
    answer = response["_answer"]
    structure = citation_structure(answer, row["evidence"])
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    timings = response.get("timings") if isinstance(response.get("timings"), dict) else {}
    return {
        "evaluation_id": row["evaluation_id"],
        "scope": row["scope"],
        "question": row["question"],
        "evidence_ids": [item["canonical_chunk_id"] for item in row["evidence"]],
        "evidence_citations": [item["citation_id"] for item in row["evidence"]],
        "serialized_evidence": format_evidence_for_prompt(row["evidence"]),
        "gold_canonical_chunk_ids_internal": row["gold_canonical_chunk_ids"],
        "gold_present_in_top5_diagnostic": row["gold_present_in_top5"],
        "known_retrieval_failure": row["known_retrieval_failure"],
        "answer": answer,
        "citation_structure": structure,
        "abstention_detected": detect_abstention(answer),
        "generation_latency_ms": latency_ms,
        "ttft_ms": timings.get("prompt_ms"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "tokens_per_second": timings.get("predicted_per_second"),
        "technical_retries": retry_count,
        "generation_error": None,
        "generator_model": GENERATOR_ALIAS,
        "external_generation_api": False,
        "semantic_review": {
            "status": "DRAFT",
            "answer_correctness": None,
            "groundedness": None,
            "citation_quality": None,
            "abstention": None,
            "failure_source": None,
            "review_notes": None,
        },
    }


def run_generation(rows: list[dict[str, Any]], *, subset_ids: set[str] | None = None) -> list[dict[str, Any]]:
    adapter = LocalQwenGenerationAdapter()
    selected = [row for row in rows if subset_ids is None or row["evaluation_id"] in subset_ids]
    traces: list[dict[str, Any]] = []
    for row in selected:
        messages = build_generation_messages(row["question"], row["evidence"])
        retries = 0
        started = time.perf_counter()
        while True:
            try:
                response = adapter.generate(messages)
                break
            except Stage14AError:
                if retries >= 1:
                    raise
                retries += 1
        latency_ms = (time.perf_counter() - started) * 1000
        traces.append(generation_trace(row, response, latency_ms, retries))
    return traces


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return float(ordered[lower])
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower))


def structural_summary(traces: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(trace["generation_latency_ms"]) for trace in traces]
    valid = sum(bool(trace["citation_structure"]["only_supplied_evidence"]) and bool(trace["citation_structure"]["valid_citation_ids"]) for trace in traces)
    no_citation = sum(not trace["citation_structure"]["valid_citation_ids"] for trace in traces)
    invalid = sum(bool(trace["citation_structure"]["invalid_citation_ids"]) for trace in traces)
    return {
        "schema_version": "stage14a-rag-answer-summary-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gold": {"path": str(GOLD_PATH.relative_to(ROOT)).replace("\\", "/"), "sha256": EXPECTED_GOLD_SHA256, "records": EXPECTED_QUERY_COUNT, "all_reviewed": True},
        "retrieval": {"candidate_k": 20, "final_k": 5, "architecture": "canonical llama.cpp embedding -> Supabase vector Top20 -> Qwen3-Reranker-0.6B -> Top5", "changed": False, "reference_hit_at_5": 0.97},
        "generator": {"model": GENERATOR_ALIAS, "path": str(GENERATOR_MODEL_PATH), "sha256": GENERATOR_MODEL_SHA256, "bytes": GENERATOR_MODEL_BYTES, "llama_cpp": GENERATOR_BUILD, "device": "Vulkan1 / NVIDIA GeForce RTX 2050", "context": GENERATOR_CONTEXT, "temperature": GENERATOR_TEMPERATURE, "top_p": GENERATOR_TOP_P, "seed": GENERATOR_SEED, "max_output_tokens": GENERATOR_MAX_TOKENS, "thinking_mode": GENERATOR_REASONING, "external_api": False},
        "prompt": {"system_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(), "user_template_sha256": hashlib.sha256(USER_PROMPT_TEMPLATE.encode("utf-8")).hexdigest(), "query_instruction_not_sent_to_generator": True},
        "structural": {"answers_attempted": len(traces), "answers_generated": len(traces), "technical_failures": 0, "technical_retries": sum(trace["technical_retries"] for trace in traces), "answers_with_valid_citations": valid, "answers_with_zero_citations": no_citation, "answers_with_invalid_citation_ids": invalid, "abstentions_detected": sum(trace["abstention_detected"] for trace in traces), "gold_present_in_top5": sum(row["gold_present_in_top5"] for row in evidence), "gold_absent_in_top5": sum(not row["gold_present_in_top5"] for row in evidence)},
        "latency_ms": {"generation_p50": percentile(latencies, 0.50), "generation_p95": percentile(latencies, 0.95), "generation_mean": statistics.fmean(latencies) if latencies else None, "ttft_p50": percentile([float(t["ttft_ms"]) for t in traces if t["ttft_ms"] is not None], 0.50), "tokens_per_second_p50": percentile([float(t["tokens_per_second"]) for t in traces if t["tokens_per_second"] is not None], 0.50), "classification": "LOCAL RTX 2050 REFERENCE LATENCY"},
        "known_retrieval_failure_behavior": {evaluation_id: {"gold_present_in_top5": next(row["gold_present_in_top5"] for row in evidence if row["evaluation_id"] == evaluation_id), "abstention_detected": next(t["abstention_detected"] for t in traces if t["evaluation_id"] == evaluation_id), "answer_generated": True, "semantic_judgment": "NOT ASSIGNED"} for evaluation_id in sorted(KNOWN_FAILURES) if any(row["evaluation_id"] == evaluation_id for row in evidence)},
        "constraints": {"no_gold_in_prompt": True, "no_manual_answer_correction": True, "no_semantic_auto_scoring": True, "fts_used": False, "hybrid_used": False, "legacy_fallback_used": False, "retrieval_tuning": False},
    }


def write_prompt_doc() -> None:
    PROMPT_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROMPT_DOC_PATH.write_text(
        "# Stage 14A Generation Prompt Freeze\n\n"
        "Frozen before the 100-query generation run. The generator receives only the original question and the ordered E1–E5 evidence context. Gold IDs, ranks, gold-present diagnostics, and human-review metadata are excluded.\n\n"
        "## System prompt\n\n```text\n" + SYSTEM_PROMPT + "\n```\n\n"
        "## User template\n\n```text\n" + USER_PROMPT_TEMPLATE + "\n```\n\n"
        "## Decoding\n\n"
        f"- temperature: `{GENERATOR_TEMPERATURE}`\n- top_p: `{GENERATOR_TOP_P}`\n- seed: `{GENERATOR_SEED}`\n- max output tokens: `{GENERATOR_MAX_TOKENS}`\n- context: `{GENERATOR_CONTEXT}`\n- reasoning mode: `{GENERATOR_REASONING}`\n- output: one final Vietnamese answer only\n",
        encoding="utf-8",
    )


def write_review_pack(rows: list[dict[str, Any]], traces: list[dict[str, Any]]) -> None:
    trace_by_id = {trace["evaluation_id"]: trace for trace in traces}
    lines = [
        "# Stage 14A RAG Answer Review",
        "",
        "Human semantic review status: PENDING — all answer records are DRAFT.",
        "Structural fields below are automated diagnostics only and are not correctness judgments.",
        "",
    ]
    for row in rows:
        trace = trace_by_id[row["evaluation_id"]]
        lines.extend(
            [
                f"## {row['evaluation_id']}",
                "",
                f"- Scope: `{row['scope']}`",
                f"- Question: {row['question']}",
                f"- Gold present in supplied Top5: `{'YES' if row['gold_present_in_top5'] else 'NO'}` (evaluation diagnostic only)",
                "",
                "### Retrieved evidence",
                "",
            ]
        )
        for item in row["evidence"]:
            lines.extend(
                [
                    f"#### {item['citation_id']}",
                    f"- Canonical ID: `{item['canonical_chunk_id']}`",
                    f"- Source: `{item['document_source_id']}` — {item['title']}",
                    f"- Locator: {format_locator(item['locator'], item['heading_path'])}",
                    f"- Visibility/provenance: `{item['visibility']}` / `{item['provenance']}`",
                    "",
                    item["content"],
                    "",
                ]
            )
        lines.extend(
            [
                "### Generated answer",
                "",
                trace["answer"],
                "",
                "### Structural result",
                "",
                f"- Valid citation IDs: `{', '.join(trace['citation_structure']['valid_citation_ids']) or 'none'}`",
                f"- Invalid citation IDs: `{', '.join(trace['citation_structure']['invalid_citation_ids']) or 'none'}`",
                f"- Abstention detected: `{trace['abstention_detected']}`",
                "",
                "### Human review (leave unassigned until review)",
                "",
                "- Status: `DRAFT`",
                "- A. Answer correctness: `DRAFT`",
                "- B. Groundedness: `DRAFT`",
                "- C. Citation quality: `DRAFT`",
                "- D. Abstention: `DRAFT`",
                "- E. Failure source: `DRAFT`",
                "- F. Review notes: `DRAFT`",
                "",
            ]
        )
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_stage_doc(summary: dict[str, Any], repeatability: dict[str, Any] | None = None) -> None:
    structural = summary["structural"]
    latency = summary["latency_ms"]
    lines = [
        "# Stage 14A — End-to-End Grounded RAG Baseline",
        "",
        "This is the first local end-to-end grounded-answering baseline. Retrieval is frozen from Stage 13F; semantic answer quality remains pending human review.",
        "",
        "## Frozen identities",
        "",
        f"- Gold: `{summary['gold']['path']}`; SHA-256 `{summary['gold']['sha256']}`; 100 REVIEWED records.",
        "- Corpus: `policy-corpus-v2`, 1610 canonical chunks; manifest SHA-256 `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`.",
        "- Embedding: Qwen3-Embedding-0.6B, 1024D, frozen Stage 10 artifacts; no regeneration.",
        "- Reranker: Qwen3-Reranker-0.6B Q8_0, frozen local GGUF; no model download.",
        f"- Generator: local `{summary['generator']['path']}`; SHA-256 `{summary['generator']['sha256']}`; llama.cpp/Vulkan1/RTX 2050.",
        "",
        "## Frozen retrieval and prompt contract",
        "",
        "- Canonical query formatter → llama.cpp embedding → Supabase `public.match_policy_chunks` Top20 → llama.cpp Qwen3 reranker → ordered Top5.",
        "- Candidate K = 20; final K = 5; no FTS, hybrid, RRF, fallback, gold injection, or manual result correction.",
        "- Generator receives the original question and only the ordered E1–E5 context. It does not receive gold IDs, retrieval ranks, or evaluation diagnostics.",
        "- Every material claim is instructed to cite `[E1]`–`[E5]`; insufficient evidence may be explicitly acknowledged.",
        "",
        "## Automated structural results",
        "",
        f"- Answers attempted/generated: `{structural['answers_attempted']}` / `{structural['answers_generated']}`; technical failures: `{structural['technical_failures']}`; retries: `{structural['technical_retries']}`.",
        f"- Answers with valid citations: `{structural['answers_with_valid_citations']}`; zero citations: `{structural['answers_with_zero_citations']}`; invalid citation outputs: `{structural['answers_with_invalid_citation_ids']}`.",
        f"- Abstentions detected: `{structural['abstentions_detected']}`; gold present in supplied Top5: `{structural['gold_present_in_top5']}`; absent: `{structural['gold_absent_in_top5']}`.",
        "- These are structural diagnostics, not correctness, groundedness, hallucination, or citation-quality scores.",
        "",
        "## Latency",
        "",
        f"- Generation p50/p95/mean: `{latency['generation_p50']}` / `{latency['generation_p95']}` / `{latency['generation_mean']}` ms.",
        "- Classification: LOCAL RTX 2050 REFERENCE LATENCY; not a production SLA.",
        "",
        "## Known retrieval limitations",
        "",
        "- `stage12a-024`, `stage13e-040`, and `stage13e-042` remain known Top20 candidate-generation failures. Their approved evidence was not injected.",
        "",
        "## Human review",
        "",
        "- Review pack: `docs/STAGE-14A-RAG-ANSWER-REVIEW.md`.",
        "- Semantic fields remain DRAFT and unassigned.",
        "",
        "## Artifacts",
        "",
        "- Live candidate freeze: `dataset/evaluation/results/rag-v2-expanded-top20-candidates.jsonl`.",
        "- Frozen Top5 evidence: `dataset/evaluation/results/rag-v2-expanded-top5-evidence.jsonl`.",
        "- Answer traces: `dataset/evaluation/results/rag-answer-v2-expanded-traces.jsonl`.",
        "- Structural summary: `dataset/evaluation/results/rag-answer-v2-expanded-summary.json`.",
        "- Repeatability subset: `dataset/evaluation/results/rag-answer-v2-expanded-repeatability.jsonl`.",
    ]
    if repeatability is not None:
        lines.extend(["", "## Predeclared repeatability subset", "", f"- Every tenth query in canonical order; records: `{repeatability['query_ids']}`.", f"- Byte-identical answers: `{repeatability['byte_identical_answers']}`; citation-structure agreement: `{repeatability['citation_structure_agreement']}`; abstention agreement: `{repeatability['abstention_agreement']}`."])
    STAGE_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAGE_DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_repeatability(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = {row["evaluation_id"] for index, row in enumerate(rows, 1) if index % 10 == 0}
    traces = run_generation(rows, subset_ids=selected)
    write_jsonl(REPEAT_PATH, traces)
    primary = {trace["evaluation_id"]: trace for trace in read_jsonl(TRACE_PATH)}
    repeat = {trace["evaluation_id"]: trace for trace in traces}
    ids = sorted(selected)
    return {
        "query_ids": ids,
        "count": len(ids),
        "byte_identical_answers": all(primary[item]["answer"] == repeat[item]["answer"] for item in ids),
        "citation_structure_agreement": sum(primary[item]["citation_structure"] == repeat[item]["citation_structure"] for item in ids) / len(ids),
        "abstention_agreement": sum(primary[item]["abstention_detected"] == repeat[item]["abstention_detected"] for item in ids) / len(ids),
        "repeatability_artifact": str(REPEAT_PATH.relative_to(ROOT)).replace("\\", "/"),
    }


def main(mode: str) -> None:
    if mode not in {"candidates", "evidence", "smoke", "generate", "repeat"}:
        raise SystemExit("usage: run_stage14a_rag_baseline.py candidates|evidence|smoke|generate|repeat")
    records, corpus, _remote = validate_frozen_inputs()
    write_prompt_doc()
    if mode == "candidates":
        result = collect_candidates(records, corpus)
        print(json.dumps({"candidate_artifact": str(CANDIDATE_PATH), "queries": len(result["traces"])}, ensure_ascii=False))
        return
    if mode == "evidence":
        rows = freeze_evidence(records, corpus)
        print(json.dumps({"evidence_artifact": str(EVIDENCE_PATH), "queries": len(rows)}, ensure_ascii=False))
        return
    rows = load_evidence()
    if mode == "smoke":
        smoke = run_generation(rows[:1])
        if not smoke or not smoke[0]["answer"].strip():
            raise Stage14AError("technical generation smoke returned no answer")
        print(json.dumps({"smoke": "PASS", "citation_structure": smoke[0]["citation_structure"]}, ensure_ascii=False))
        return
    if mode == "generate":
        traces = run_generation(rows)
        if len(traces) != EXPECTED_QUERY_COUNT:
            raise Stage14AError("generation trace count is not 100")
        write_jsonl(TRACE_PATH, traces)
        summary = structural_summary(traces, rows)
        write_json(SUMMARY_PATH, summary)
        write_review_pack(rows, traces)
        write_stage_doc(summary)
        print(json.dumps({"trace_artifact": str(TRACE_PATH), "summary_artifact": str(SUMMARY_PATH), "queries": len(traces)}, ensure_ascii=False))
        return
    if not TRACE_PATH.is_file():
        raise Stage14AError("primary generation traces are required before repeatability")
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    repeatability = run_repeatability(rows)
    summary["repeatability"] = repeatability
    write_json(SUMMARY_PATH, summary)
    write_stage_doc(summary, repeatability)
    print(json.dumps(repeatability, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) == 2 else "")
    except (Stage14AError, ValueError, KeyError) as exc:
        print(f"STAGE14A ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
