"""Evidence-first gold-pilot contracts for frozen Corpus V2.

The historical :mod:`app.eval.gold` parser is intentionally left intact for
R01 data.  This module validates the Stage 12A V2 artifact without importing
SQLAlchemy models, legacy corpus tables, or an embedding runtime.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS_PATH = PROJECT_ROOT / "dataset/chunks/v2/policy-corpus-v2.jsonl"
DEFAULT_CORPUS_MANIFEST_PATH = PROJECT_ROOT / "dataset/manifests/policy-corpus-v2-manifest.json"
DEFAULT_EMBEDDING_MANIFEST_PATH = PROJECT_ROOT / "dataset/embeddings/v2/embedding-manifest.json"
DEFAULT_EMBEDDING_ARTIFACT_PATH = PROJECT_ROOT / "dataset/embeddings/v2/embeddings.parquet"

SUPPORTED_SCOPES = frozenset(
    {
        "customer_relationship",
        "credit",
        "risk_management",
        "legal_compliance",
        "collateral_appraisal",
    }
)
QUERY_TYPES = frozenset(
    {"POLICY_LOOKUP", "ELIGIBILITY_SUPPORT", "CALCULATION_GUIDANCE", "MULTI_SOURCE"}
)
STATUSES = frozenset({"DRAFT", "REVIEWED", "REJECTED"})
QUERY_INSTRUCTION = (
    "Given a Vietnamese banking legal question, retrieve authoritative passages "
    "that directly support the answer."
)
DOCUMENT_TEMPLATE = "Document: {title}\nSection: {heading_path}\nText:\n{content}"


class CanonicalGoldError(ValueError):
    """A V2 gold record or export violated the frozen evaluation contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _compact(value: object) -> str:
    return " ".join(str(value).split())


def _norm_question(value: str) -> str:
    return re.sub(r"[^\w\s]", " ", value.casefold(), flags=re.UNICODE).strip()


def _as_sha256(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"


def _scope_slug(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).casefold()


def _short_excerpt(content: str, max_chars: int = 360) -> str:
    """Return a compact whitespace-normalized excerpt from frozen content."""

    compact = _compact(content)
    if len(compact) <= max_chars:
        return compact
    excerpt = compact[:max_chars]
    return excerpt.rsplit(" ", 1)[0] + "…"


class FrozenCorpusV2:
    """Read-only view of the frozen corpus and its source identity metadata."""

    def __init__(
        self,
        corpus_path: Path = DEFAULT_CORPUS_PATH,
        corpus_manifest_path: Path = DEFAULT_CORPUS_MANIFEST_PATH,
        embedding_manifest_path: Path = DEFAULT_EMBEDDING_MANIFEST_PATH,
        embedding_artifact_path: Path = DEFAULT_EMBEDDING_ARTIFACT_PATH,
    ) -> None:
        self.corpus_path = Path(corpus_path)
        self.corpus_manifest_path = Path(corpus_manifest_path)
        self.embedding_manifest_path = Path(embedding_manifest_path)
        self.embedding_artifact_path = Path(embedding_artifact_path)
        if not self.corpus_path.exists():
            raise CanonicalGoldError(f"Frozen Corpus V2 is missing: {self.corpus_path}")
        if not self.corpus_manifest_path.exists():
            raise CanonicalGoldError(f"Corpus V2 manifest is missing: {self.corpus_manifest_path}")
        if not self.embedding_manifest_path.exists():
            raise CanonicalGoldError(
                f"Embedding manifest is missing: {self.embedding_manifest_path}"
            )

        self.corpus_manifest = json.loads(self.corpus_manifest_path.read_text(encoding="utf-8"))
        self.embedding_manifest = json.loads(
            self.embedding_manifest_path.read_text(encoding="utf-8")
        )
        self.rows = self._load_rows()
        self.by_id = {row["canonical_chunk_id"]: row for row in self.rows}
        self.sources = self._load_sources()
        self._validate_frozen_identity()

    def _load_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self.corpus_path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise CanonicalGoldError(
                        f"Invalid frozen corpus JSON at line {line_no}: {exc}"
                    ) from exc
                rows.append(row)
        return rows

    def _load_sources(self) -> dict[str, dict[str, Any]]:
        sources: dict[str, dict[str, Any]] = {}
        normalized_sources_path = PROJECT_ROOT / "dataset/normalized/v2/policy-sources.json"
        normalized_sources = {
            item["source_id"]: item
            for item in json.loads(normalized_sources_path.read_text(encoding="utf-8"))
        }
        for source in self.corpus_manifest["artifacts"]["real"]["documents"]:
            sources[source["source_id"]] = {
                **normalized_sources[source["source_id"]],
                **source,
                "synthetic": False,
                "namespace": "REGULATION",
            }
        synthetic_titles = {
            "synthetic-sme-working-capital-v1": "SME Unsecured Working Capital Product Policy",
            "synthetic-sme-underwriting-v1": "SME Credit Underwriting Policy",
            "synthetic-credit-approval-v1": "Credit Approval & Exception Policy",
        }
        for source in self.corpus_manifest["artifacts"]["synthetic"]["documents"]:
            metadata = next(
                item
                for item in self.corpus_manifest["synthetic_source_metadata_mapping"]
                if item["source_id"] == source["source_id"]
            )
            sources[source["source_id"]] = {
                **source,
                **metadata,
                "synthetic": True,
                "title": synthetic_titles[source["source_id"]],
            }
        return sources

    def _validate_frozen_identity(self) -> None:
        expected_count = self.corpus_manifest["chunk_counts"]["total"]
        if len(self.rows) != expected_count or expected_count != 1610:
            raise CanonicalGoldError(
                f"Frozen Corpus V2 row count is {len(self.rows)}, expected 1610"
            )
        if len(self.by_id) != len(self.rows):
            raise CanonicalGoldError("Frozen Corpus V2 contains duplicate canonical_chunk_id values")
        if _sha256(self.corpus_path) != self.corpus_manifest["artifacts"]["combined_chunks"]["sha256"]:
            raise CanonicalGoldError("Frozen Corpus V2 JSONL hash does not match its manifest")
        if self.embedding_manifest["chunk_count"] != 1610:
            raise CanonicalGoldError("Embedding manifest is not bound to 1610 chunks")
        if self.embedding_artifact_path.exists():
            actual = _sha256(self.embedding_artifact_path)
            expected = self.embedding_manifest["artifact_sha256"].removeprefix("sha256:")
            if actual != expected:
                raise CanonicalGoldError("Frozen embedding artifact hash does not match its manifest")

    @property
    def corpus_identity(self) -> dict[str, Any]:
        manifest = self.corpus_manifest
        return {
            "version": "V2",
            "corpus_name": "policy-corpus-v2",
            "chunk_count": 1610,
            "corpus_jsonl_sha256": _as_sha256(manifest["artifacts"]["combined_chunks"]["sha256"]),
            "corpus_manifest_sha256": _as_sha256(_sha256(self.corpus_manifest_path)),
            "corpus_v2_hash": _as_sha256(manifest["corpus_v2_hash"]),
            "manifest_hash": _as_sha256(manifest["manifest_hash"]),
        }

    @property
    def embedding_identity(self) -> dict[str, Any]:
        manifest = self.embedding_manifest
        return {
            "model": manifest["model_id"],
            "format": f"{manifest['model_format']} {manifest['quantization']}",
            "dimension": manifest["embedding_dimension"],
            "dtype": "float32",
            "normalization": "L2 unit",
            "pooling": "last",
            "runtime": manifest["runtime"]["backend"],
            "backend": manifest["device_backend"],
            "embedding_artifact_sha256": manifest["artifact_sha256"],
            "embedding_manifest_sha256": _as_sha256(_sha256(self.embedding_manifest_path)),
            "query_instruction": QUERY_INSTRUCTION,
            "document_template": manifest["input_template"],
        }

    def source_identity(self, source_id: str) -> dict[str, Any]:
        try:
            source = self.sources[source_id]
        except KeyError as exc:
            raise CanonicalGoldError(f"Unknown frozen source_id '{source_id}'") from exc
        return {
            "source_id": source["source_id"],
            "version_id": source["version_id"],
            "title": source["title"],
            "issuer": source.get("issuer"),
            "document_number": source.get("document_number"),
            "issue_date": source.get("issue_date"),
            "effective_date": source.get("effective_date"),
            "source_artifact_path": source["path"],
            "source_artifact_sha256": _as_sha256(source["sha256"]),
            "provenance": "synthetic" if source["synthetic"] else "real_authoritative",
            "synthetic": source["synthetic"],
            "namespace": source["namespace"],
        }

    def make_evidence(
        self,
        canonical_chunk_id: str,
        rationale: str,
        excerpt: str | None = None,
    ) -> dict[str, Any]:
        if canonical_chunk_id not in self.by_id:
            raise CanonicalGoldError(f"Unknown frozen canonical_chunk_id '{canonical_chunk_id}'")
        row = self.by_id[canonical_chunk_id]
        source = self.sources[row["source_id"]]
        return {
            "canonical_chunk_id": canonical_chunk_id,
            "source_id": row["source_id"],
            "version_id": row["version_id"],
            "document_title": source["title"],
            "heading_path": row.get("heading_path", []),
            "locator": {
                "article": row.get("article"),
                "clause": row.get("clause"),
                "point": row.get("point"),
                "page_start": row.get("page_start"),
                "page_end": row.get("page_end"),
                "jsonl_line": self.rows.index(row) + 1,
            },
            "excerpt": excerpt if excerpt is not None else _short_excerpt(row["content"]),
            "rationale": rationale,
            "visibility": "SCOPED" if source["synthetic"] else "SHARED",
            "is_synthetic": source["synthetic"],
            "namespace": source["namespace"],
        }


def leakage_flags(record: dict[str, Any], corpus: FrozenCorpusV2) -> list[str]:
    """Return obvious prompt leakage indicators for human review."""

    query = _compact(record.get("query", ""))
    normalized_query = _norm_question(query)
    flags: list[str] = []
    for canonical_id in record.get("expected_canonical_chunk_ids", []):
        if canonical_id in query:
            flags.append("canonical_chunk_id appears in query")
    if "rule id:" in query.casefold() or "[[" in query:
        flags.append("internal evidence identifier appears in query")
    for evidence in record.get("gold_evidence", []):
        excerpt = _compact(evidence.get("excerpt", ""))
        if len(excerpt) >= 80 and _norm_question(excerpt) in normalized_query:
            flags.append("long evidence substring copied into query")
        for heading in evidence.get("heading_path", []):
            heading_norm = _norm_question(_compact(heading))
            if len(heading_norm) >= 24 and heading_norm == normalized_query:
                flags.append("query is an exact heading lookup")
    return sorted(set(flags))


class CanonicalGoldValidator:
    """Validate evidence-first V2 records against the local frozen corpus."""

    def __init__(self, corpus: FrozenCorpusV2 | None = None) -> None:
        self.corpus = corpus or FrozenCorpusV2()

    def parse_file(self, path: Path) -> list[dict[str, Any]]:
        path = Path(path)
        if not path.exists():
            raise CanonicalGoldError(f"Canonical gold file is missing: {path}")
        records: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise CanonicalGoldError(f"Line {line_no}: invalid JSON: {exc}") from exc
                self.validate_record(record, records, line_no)
                records.append(record)
        if not records:
            raise CanonicalGoldError("Canonical gold file contains no records")
        return records

    def validate_record(
        self, record: dict[str, Any], prior_records: Iterable[dict[str, Any]] = (), line_no: int = 0
    ) -> None:
        prefix = f"Line {line_no}: " if line_no else ""
        if not isinstance(record, dict):
            raise CanonicalGoldError(prefix + "record must be an object")
        required = {
            "schema_version",
            "evaluation_id",
            "query",
            "query_type",
            "specialist_scope",
            "assessment_date",
            "filters",
            "expected_canonical_chunk_ids",
            "gold_evidence",
            "forbidden_version_ids",
            "expected_coverage",
            "tags",
            "document",
            "visibility",
            "is_synthetic",
            "corpus_identity",
            "embedding_identity",
            "status",
            "creation_provenance",
            "review",
        }
        missing = sorted(required.difference(record))
        if missing:
            raise CanonicalGoldError(prefix + f"missing required fields: {', '.join(missing)}")
        if record["schema_version"] != "retrieval-gold-v2.0.0":
            raise CanonicalGoldError(prefix + "unsupported schema_version")
        evaluation_id = record["evaluation_id"]
        query = record["query"]
        if not isinstance(evaluation_id, str) or not evaluation_id.strip():
            raise CanonicalGoldError(prefix + "evaluation_id must be non-empty")
        if not isinstance(query, str) or not query.strip():
            raise CanonicalGoldError(prefix + "query must be non-empty")
        prior = list(prior_records)
        if evaluation_id in {item.get("evaluation_id") for item in prior}:
            raise CanonicalGoldError(prefix + f"duplicate evaluation_id '{evaluation_id}'")
        normalized = _norm_question(query)
        if normalized in {_norm_question(item.get("query", "")) for item in prior}:
            raise CanonicalGoldError(prefix + "duplicate question")
        for item in prior:
            if SequenceMatcher(None, normalized, _norm_question(item.get("query", ""))).ratio() >= 0.94:
                raise CanonicalGoldError(prefix + "near-duplicate question")
        scope = record["specialist_scope"]
        if scope not in SUPPORTED_SCOPES:
            raise CanonicalGoldError(prefix + f"unsupported specialist scope '{scope}'")
        if record["query_type"] not in QUERY_TYPES:
            raise CanonicalGoldError(prefix + f"invalid query_type '{record['query_type']}'")
        if record["status"] not in STATUSES:
            raise CanonicalGoldError(prefix + f"invalid status '{record['status']}'")
        if record["status"] == "DRAFT" and record["review"] is not None:
            raise CanonicalGoldError(prefix + "automated DRAFT cannot self-review")
        if record["status"] in {"REVIEWED", "REJECTED"}:
            self._validate_review(record["review"], record["status"], prefix)
        provenance = record["creation_provenance"]
        if not isinstance(provenance, dict) or provenance.get("retrieval_used") is not False:
            raise CanonicalGoldError(prefix + "creation provenance must state retrieval_used=false")
        for field in ("method", "evidence_source", "generated_by", "created_at"):
            if not isinstance(provenance.get(field), str) or not provenance[field].strip():
                raise CanonicalGoldError(prefix + f"creation provenance missing '{field}'")
        if record["status"] == "DRAFT" and "human" not in provenance["method"]:
            raise CanonicalGoldError(prefix + "DRAFT provenance must identify evidence-first human-authored drafting")
        identity_errors = self._identity_errors(record)
        if identity_errors:
            raise CanonicalGoldError(prefix + "; ".join(identity_errors))
        ids = record["expected_canonical_chunk_ids"]
        evidence = record["gold_evidence"]
        if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids):
            raise CanonicalGoldError(prefix + "expected canonical IDs must be a unique non-empty list")
        if not isinstance(evidence, list) or not evidence:
            raise CanonicalGoldError(prefix + "evidence provenance is required")
        evidence_ids = [item.get("canonical_chunk_id") for item in evidence]
        if evidence_ids != ids:
            raise CanonicalGoldError(prefix + "expected IDs must match evidence IDs in order")
        self._validate_document_and_evidence(record, evidence, scope, prefix)
        if leakage_flags(record, self.corpus):
            raise CanonicalGoldError(prefix + "obvious query leakage: " + ", ".join(leakage_flags(record, self.corpus)))

    def _identity_errors(self, record: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        expected_corpus = self.corpus.corpus_identity
        expected_embedding = self.corpus.embedding_identity
        for field, expected in expected_corpus.items():
            if record.get("corpus_identity", {}).get(field) != expected:
                errors.append(f"corpus identity mismatch at '{field}'")
        for field, expected in expected_embedding.items():
            if record.get("embedding_identity", {}).get(field) != expected:
                errors.append(f"embedding identity mismatch at '{field}'")
        return errors

    def _validate_document_and_evidence(
        self, record: dict[str, Any], evidence: list[dict[str, Any]], scope: str, prefix: str
    ) -> None:
        expected_document = self.corpus.source_identity(evidence[0]["source_id"])
        document = record["document"]
        for field in ("source_id", "version_id", "title", "issuer", "document_number", "source_artifact_path", "source_artifact_sha256", "provenance", "synthetic", "namespace"):
            if document.get(field) != expected_document.get(field):
                raise CanonicalGoldError(prefix + f"document identity mismatch at '{field}'")
        expected_visibility = "SCOPED" if expected_document["synthetic"] else "SHARED"
        if record["visibility"] != expected_visibility or record["is_synthetic"] != expected_document["synthetic"]:
            raise CanonicalGoldError(prefix + "invalid visibility or synthetic semantics")
        for item in evidence:
            chunk_id = item.get("canonical_chunk_id")
            if chunk_id not in self.corpus.by_id:
                raise CanonicalGoldError(prefix + f"invalid Corpus V2 ID '{chunk_id}'")
            row = self.corpus.by_id[chunk_id]
            source = self.corpus.sources[row["source_id"]]
            if item.get("source_id") != row["source_id"] or item.get("version_id") != row["version_id"]:
                raise CanonicalGoldError(prefix + f"evidence source/version mismatch for '{chunk_id}'")
            if item.get("document_title") != source["title"]:
                raise CanonicalGoldError(prefix + f"evidence document title mismatch for '{chunk_id}'")
            if item.get("heading_path") != row.get("heading_path", []):
                raise CanonicalGoldError(prefix + f"evidence heading_path mismatch for '{chunk_id}'")
            if item.get("visibility") != expected_visibility or item.get("is_synthetic") != source["synthetic"]:
                raise CanonicalGoldError(prefix + f"evidence visibility mismatch for '{chunk_id}'")
            if item.get("namespace") != source["namespace"]:
                raise CanonicalGoldError(prefix + f"evidence namespace mismatch for '{chunk_id}'")
            if not isinstance(item.get("excerpt"), str) or not item["excerpt"].strip():
                raise CanonicalGoldError(prefix + f"evidence excerpt missing for '{chunk_id}'")
            if _compact(item["excerpt"]).rstrip("…") not in _compact(row["content"]):
                raise CanonicalGoldError(prefix + f"evidence excerpt is not grounded in '{chunk_id}'")
            if not isinstance(item.get("rationale"), str) or not item["rationale"].strip():
                raise CanonicalGoldError(prefix + f"evidence rationale missing for '{chunk_id}'")
            if source["synthetic"]:
                allowed = {_scope_slug(name) for name in source.get("agent_scopes", [])}
                if _scope_slug(scope) not in allowed:
                    raise CanonicalGoldError(prefix + f"scope '{scope}' is not declared for synthetic evidence '{chunk_id}'")
            locator = item.get("locator")
            if not isinstance(locator, dict) or locator.get("article") != row.get("article") or locator.get("clause") != row.get("clause") or locator.get("point") != row.get("point"):
                raise CanonicalGoldError(prefix + f"evidence locator mismatch for '{chunk_id}'")

    @staticmethod
    def _validate_review(review: object, status: str, prefix: str) -> None:
        if not isinstance(review, dict):
            raise CanonicalGoldError(prefix + f"{status} record requires review metadata")
        for field in ("reviewer_id", "reviewed_at", "decision"):
            if not isinstance(review.get(field), str) or not review[field].strip():
                raise CanonicalGoldError(prefix + f"review metadata missing '{field}'")
        if review["decision"] != status:
            raise CanonicalGoldError(prefix + "review decision does not match status")


def export_reviewed_canonical_gold(input_path: Path, output_path: Path) -> int:
    """Export only a fully human-reviewed V2 file; drafts are never promoted."""

    validator = CanonicalGoldValidator()
    records = validator.parse_file(Path(input_path))
    if any(record["status"] != "REVIEWED" for record in records):
        raise CanonicalGoldError("only REVIEWED records are exportable as frozen gold")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return len(records)


__all__ = [
    "CanonicalGoldError",
    "CanonicalGoldValidator",
    "FrozenCorpusV2",
    "SUPPORTED_SCOPES",
    "QUERY_INSTRUCTION",
    "DOCUMENT_TEMPLATE",
    "export_reviewed_canonical_gold",
    "leakage_flags",
]
