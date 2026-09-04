"""Read and validate the small Stage 8 synthetic-policy source set.

This module is intentionally input-only: it validates complete source documents
and their manifest before a future normalization stage consumes them.  It does
not create chunks or mutate the frozen real-policy corpus.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


EXPECTED_SOURCES = {
    "synthetic-sme-working-capital-v1": "BANK_PRODUCT",
    "synthetic-sme-underwriting-v1": "UNDERWRITING_POLICY",
    "synthetic-credit-approval-v1": "UNDERWRITING_POLICY",
}
REQUIRED_RECORD_FIELDS = {
    "source_id", "version_id", "title", "namespace", "synthetic", "issuer",
    "organization_label", "effective_date", "document_version", "agent_scopes",
    "content_hash", "path", "format",
}
RULE_ID_RE = re.compile(r"^Rule ID: ([A-Z]+-[A-Z0-9-]+)\.", re.MULTILINE)
REFERENCE_RE = re.compile(r"\[\[([A-Z]+-[A-Z0-9-]+)\]\]")
LAW_ASSERTION_RE = re.compile(
    r"\b(?:is|are|constitutes?|represent)\s+(?:Vietnamese\s+)?law\b|"
    r"\bVietnamese law (?:requires|sets|mandates)\b",
    re.IGNORECASE,
)

# Each literal is a policy decision frozen in the Stage 8 matrix.  Keeping
# these as document text checks makes drift visible without manufacturing any
# retrieval-shaped artifacts.
MATRIX_TEXT = {
    "synthetic-sme-working-capital-v1": (
        "24 completed months", "18–23 completed months", "VND 10 billion",
        "VND 8 billion", "VND 5 billion", "12 months", "Bullet repayment is prohibited",
        "No collateral is required", "active CIC Group 3 or higher",
        "Gambling, unlicensed financial intermediation, weapons trafficking",
    ),
    "synthetic-sme-underwriting-v1": (
        "DSCR is >= 1.30", "DSCR >= 1.15 and < 1.30", "DSCR < 1.15",
        "equity <= 3.00x", "Debt-to-Equity > 3.00x and <= 4.00x", "Debt-to-Equity > 4.00x",
        "Current Ratio is >= 1.00x", "Current Ratio >= 0.80x and < 1.00x",
        "Current Ratio < 0.80x", "revenue decline > 10% and <= 20%",
        "Grade C means exactly one soft exception", "unsupported or recurring negative cash flow",
    ),
    "synthetic-credit-approval-v1": (
        "up to VND 1 billion", "above VND 1 billion and up to VND 3 billion",
        "above VND 3 billion and up to VND 5 billion", "up to VND 3 billion",
        "two soft exceptions", "60 calendar days", "30 calendar days", "more than 10%",
    ),
}
APPROVAL_BAND_TEXT = (
    "greater than VND 0 and up to VND 1 billion",
    "above VND 1 billion and up to VND 3 billion",
    "above VND 3 billion and up to VND 5 billion for Grade A/B",
    "single-exception Grade C case with total exposure up to VND 3 billion",
    "single-exception Grade C case with total exposure above VND 3 billion and up to VND 5 billion",
)
EXCEPTION_AUTHORITY_TEXT = (
    "A Grade C case has exactly one soft exception",
    "Exactly two soft exceptions are Grade C-EXCEPTION-2 and are eligible only for Tier 4 when every hard stop is absent, total exposure is > VND 3 billion and <= VND 5 billion, Risk and LegalCompliance concur, and the full rationale and mitigants are recorded.",
    "Grade C-EXCEPTION-2 is not eligible for Tier 1, Tier 2, or Tier 3.",
    "More than two soft exceptions are not permitted.",
    "no grade or tier may override a hard stop",
)
EXCEPTION_ROUTE_TEXT = (
    "Exactly two soft exceptions are Grade C-EXCEPTION-2 and are eligible only for Tier 4 when every hard stop is absent, total exposure is > VND 3 billion and <= VND 5 billion, Risk and LegalCompliance concur, and the full rationale and mitigants are recorded",
    "Grade C-EXCEPTION-2 is not eligible for Tier 1, Tier 2, or Tier 3.",
    "More than two soft exceptions are not permitted.",
    "No grade or tier may override a hard stop",
)
BOUNDARY_GAP_LANGUAGE = (
    "1.15 through 1.29", "3.01x through 4.00x", "0.80x through 0.99x",
    "1.15–1.29", "3.01–4.00x", "0.80–0.99x",
)


def normalize_source_text(text: str) -> str:
    """Apply the frozen Stage 7 normalization rule used for source hashes."""
    return unicodedata.normalize("NFC", text).replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")


def source_content_hash(text: str) -> str:
    return hashlib.sha256(normalize_source_text(text).encode("utf-8")).hexdigest()


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    with manifest_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_synthetic_policy_set(manifest_path: Path) -> list[str]:
    """Return deterministic contract violations for a Stage 8 manifest."""
    manifest_path = manifest_path.resolve()
    manifest = load_manifest(manifest_path)
    errors: list[str] = []
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 3:
        return ["manifest must contain exactly three records"]

    source_ids = [record.get("source_id") for record in records]
    version_ids = [record.get("version_id") for record in records]
    hashes = [record.get("content_hash") for record in records]
    if set(source_ids) != set(EXPECTED_SOURCES):
        errors.append("manifest source IDs must be exactly the approved Stage 8 source set")
    for label, values in (("source_id", source_ids), ("version_id", version_ids), ("content_hash", hashes)):
        if len(values) != len(set(values)):
            errors.append(f"duplicate {label}")

    declared_rules: set[str] = set()
    references: list[tuple[str, str]] = []
    documents: dict[str, str] = {}
    for record in records:
        source_id = record.get("source_id", "<missing>")
        missing = REQUIRED_RECORD_FIELDS - set(record)
        if missing:
            errors.append(f"{source_id}: missing manifest fields {sorted(missing)}")
            continue
        if record["namespace"] == "REGULATION" or record["namespace"] != EXPECTED_SOURCES.get(source_id):
            errors.append(f"{source_id}: invalid namespace")
        if record["synthetic"] is not True:
            errors.append(f"{source_id}: synthetic must be true")
        if record["organization_label"] != "Ngân hàng Thương mại Cổ phần Hồng Hà (HHB)":
            errors.append(f"{source_id}: unexpected organization label")
        if record["format"] != "markdown" or not isinstance(record["agent_scopes"], list):
            errors.append(f"{source_id}: invalid adapter metadata")
        document_path = (manifest_path.parents[4] / record["path"]).resolve()
        if not document_path.is_file():
            errors.append(f"{source_id}: source document is missing")
            continue
        text = document_path.read_text(encoding="utf-8")
        documents[source_id] = text
        if source_content_hash(text) != record["content_hash"]:
            errors.append(f"{source_id}: content hash mismatch")
        if "synthetic=true" not in text or "fictional internal organization" not in text or "not Vietnamese law" not in text:
            errors.append(f"{source_id}: required synthetic/legal boundary text is missing")
        if "`synthetic`: `true`" not in text:
            errors.append(f"{source_id}: document synthetic flag is missing")
        if LAW_ASSERTION_RE.search(text):
            errors.append(f"{source_id}: synthetic policy labels a value as law")
        normalized_text = text.casefold()
        for required_text in MATRIX_TEXT.get(source_id, ()):
            if required_text.casefold() not in normalized_text:
                errors.append(f"{source_id}: matrix decision missing: {required_text}")
        declared_rules.update(RULE_ID_RE.findall(text))
        references.extend((source_id, rule_id) for rule_id in REFERENCE_RE.findall(text))

    for source_id, rule_id in references:
        if rule_id not in declared_rules:
            errors.append(f"{source_id}: unresolved cross-document reference {rule_id}")

    underwriting_text = documents.get("synthetic-sme-underwriting-v1", "")
    for gap_language in BOUNDARY_GAP_LANGUAGE:
        if gap_language in underwriting_text:
            errors.append(f"synthetic-sme-underwriting-v1: boundary-gap language is not permitted: {gap_language}")
    if not all(item in underwriting_text for item in EXCEPTION_ROUTE_TEXT):
        errors.append("underwriting exception-count or authority language is invalid")
    product_text = documents.get("synthetic-sme-working-capital-v1", "")
    if not all(item in product_text for item in EXCEPTION_ROUTE_TEXT):
        errors.append("product exception-count or authority language is invalid")

    required_tiers = {"APR-TIER-1", "APR-TIER-2", "APR-TIER-3", "APR-TIER-4"}
    approval_text = documents.get("synthetic-credit-approval-v1", "")
    if not required_tiers <= declared_rules or not all(item in approval_text for item in APPROVAL_BAND_TEXT):
        errors.append("approval tiers do not cover every exposure band through the VND 5 billion cap")
    if (
        not {"APR-EXCEPTIONS", "APR-HARD-STOPS", "UW-SOFT-EXCEPTIONS", "UW-HARD-STOPS"} <= declared_rules
        or not all(item in approval_text for item in EXCEPTION_AUTHORITY_TEXT)
    ):
        errors.append("exception logic is not mapped to underwriting and approval authorities")
    return errors
