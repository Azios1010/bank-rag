"""Apply the explicitly approved Stage 13E1-R1 gold corrections.

This is a narrow, evidence-first revision.  It loads the existing expanded
draft, preserves the frozen seed and every unauthorized draft, changes only
the sixteen human-authorized IDs, validates the complete result, and writes a
revisioned human-review pack.

No retrieval, embedding runtime, FTS, reranker, or Supabase client is used.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.eval.gold_v2 import CanonicalGoldValidator, FrozenCorpusV2, leakage_flags


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_PATH = PROJECT_ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
INPUT_PATH = PROJECT_ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.draft.jsonl"
OUTPUT_PATH = INPUT_PATH
REVIEW_PATH = PROJECT_ROOT / "docs/STAGE-13E-EXPANDED-GOLD-REVIEW-R1.md"
PILOT_SHA256 = "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _compact(value: str) -> str:
    return " ".join(value.split())


# Each replacement keeps the existing record ID and scope, but selects a new
# canonical chunk from source inspection.  The selected synthetic targets are
# all declared for their requested scopes in Corpus V2.
REPLACEMENTS: dict[str, dict[str, Any]] = {
    "stage13e-037": {
        "chunk_id": "1ad078503e952d4c010471185961e8f00a5580e6ecb80b7b46efff824a9a9f09",
        "query": "Khi tính tổng mức phơi nhiễm để áp dụng hạn mức và tuyến phê duyệt, những khoản nghĩa vụ nào phải được tính vào?",
        "query_type": "POLICY_LOOKUP",
        "question_category": "direct",
        "difficulty": "MEDIUM",
        "rationale": "Quy tắc APR-EXPOSURE xác định tổng dư nợ gồm khoản cấp tín dụng đề xuất, các nghĩa vụ tín dụng hiện hữu của HHB và các bảo lãnh hoặc nghĩa vụ tiềm ẩn áp dụng; hạn mức và tuyến phê duyệt phải dùng tổng này.",
        "tags": ["exposure", "approval-authority"],
    },
    "stage13e-038": {
        "chunk_id": "7b94c1d235374306aa2b1ab6ab9da4a9d8335c288ad88515cc4e85463d30c02e",
        "query": "Khoản cấp tín dụng trên 1 tỷ đồng đến 3 tỷ đồng có thể do cấp nào phê duyệt và phải đáp ứng những điều kiện gì?",
        "query_type": "ELIGIBILITY_SUPPORT",
        "question_category": "threshold",
        "difficulty": "MEDIUM",
        "rationale": "Quy tắc APR-TIER-2 đặt ngưỡng tổng dư nợ trên 1 tỷ đồng đến 3 tỷ đồng, yêu cầu hồ sơ Grade A/B không có ngoại lệ và yêu cầu thẩm định Risk độc lập.",
        "tags": ["approval-tier", "threshold"],
    },
    "stage13e-039": {
        "chunk_id": "964bf8d08a30cdc684c80f3d672844e92d7cca27879e9cc2b055c3206eeacc42",
        "query": "Bộ phận quản lý nợ và cam kết ngoại bảng phải đảm nhiệm những trách nhiệm nào trong việc vận hành hệ thống xếp hạng, phân loại nợ và dự phòng?",
        "query_type": "POLICY_LOOKUP",
        "question_category": "role",
        "difficulty": "HARD",
        "rationale": "Điều 12 quy định bộ phận chuyên trách phải quản lý việc phân loại nợ và dự phòng, vận hành hệ thống xếp hạng, xây dựng hoặc trình ban hành chính sách, theo dõi đơn vị thực hiện và báo cáo các nội dung thuộc thẩm quyền.",
        "tags": ["debt-management", "provisioning", "responsibility"],
    },
    "stage13e-067": {
        "chunk_id": "dcaaa7a6994303d7850c83a21693a418aba2420b7928337993e6be84a1842c21",
        "query": "Những thay đổi nào buộc hồ sơ tín dụng phải được phê duyệt lại trước khi tiếp tục xử lý?",
        "query_type": "POLICY_LOOKUP",
        "question_category": "consequence",
        "difficulty": "HARD",
        "rationale": "Quy tắc APR-REAPPROVAL liệt kê các sự kiện buộc phê duyệt lại, gồm thay đổi đáng kể về số tiền hoặc tổng dư nợ, mục đích hoặc kỳ hạn, sở hữu hoặc kiểm soát, tín dụng quá hạn, DSCR, báo cáo tài chính và thời hạn phê duyệt.",
        "tags": ["reapproval", "change-control"],
    },
    "stage13e-083": {
        "chunk_id": "40cc0096b54df95d426fdf7c249200893e39320e287bce97205a7e751213b465",
        "query": "Sản phẩm vốn lưu động SME không bảo đảm cho phép những cấu trúc trả nợ nào và cấm hình thức nào?",
        "query_type": "POLICY_LOOKUP",
        "question_category": "distinction",
        "difficulty": "MEDIUM",
        "rationale": "Quy tắc PROD-REPAYMENT cho phép khoản vay trả dần với lãi hàng tháng và trả gốc ít nhất hàng quý, hoặc hạn mức quay vòng có thời gian clean-down 30 ngày liên tiếp; trả nợ một lần bị cấm.",
        "tags": ["repayment", "product-structure"],
    },
}


EDIT_SPECS: dict[str, dict[str, Any]] = {
    "stage13e-046": {
        "query": "Quy định nội bộ phải đặt ra yêu cầu quản lý như thế nào để bảo đảm tuân thủ các giới hạn và tỷ lệ an toàn do Ngân hàng Nhà nước quy định?",
        "rationale": "Điểm d khoản 2 Điều 6 yêu cầu quy định quản lý trong quy định nội bộ bảo đảm tuân thủ các giới hạn và tỷ lệ bảo đảm an toàn do Ngân hàng Nhà nước quy định; đoạn này không tự liệt kê các tỷ lệ cụ thể.",
    },
    "stage13e-050": {
        "query": "Khi thẩm định SME, cần xác minh và đánh giá những nhóm thông tin nào về pháp lý, sở hữu, quản lý, ngành nghề và mức độ tập trung?",
        "rationale": "Quy tắc UW-IDENTITY-AND-INDUSTRY yêu cầu xác minh đăng ký, thẩm quyền, sở hữu, tính liên tục của quản lý, thời điểm bắt đầu kinh doanh, ngành và mục đích; đồng thời đánh giá kinh nghiệm quản lý, mức độ tập trung khách hàng hoặc nhà cung cấp, triển vọng ngành và sự phụ thuộc vào một đối tác.",
    },
    "stage13e-053": {
        "query": "Với hồ sơ Grade C có đúng một ngoại lệ mềm, hồ sơ phải ghi nhận những nội dung nào về quy tắc bị lệch, bằng chứng, nguyên nhân, biện pháp giảm thiểu và rủi ro còn lại?",
        "rationale": "Quy tắc APR-EXCEPTIONS yêu cầu một hồ sơ Grade C có đúng một ngoại lệ mềm phải nêu quy tắc bị lệch, chứng cứ, nguyên nhân gốc, biện pháp giảm thiểu và rủi ro còn lại; nội dung về Grade C-EXCEPTION-2 không còn là phạm vi của câu hỏi này.",
    },
    "stage13e-059": {
        "rationale": "Toàn bộ Điều 15 liệt kê năm nhóm hành vi bị cấm: hoạt động ngoài Giấy phép, hoạt động ngân hàng của chủ thể không phải tổ chức tín dụng ngoài ngoại lệ được nêu, can thiệp trái pháp luật, hạn chế cạnh tranh hoặc cạnh tranh không lành mạnh gây hại, và gắn bán bảo hiểm không bắt buộc với sản phẩm hoặc dịch vụ ngân hàng.",
    },
    "stage13e-062": {
        "query": "Sau khi nhận đủ hồ sơ hợp lệ, thời hạn cấp hoặc từ chối cấp phép đối với tổ chức tín dụng hoặc chi nhánh ngân hàng nước ngoài và đối với văn phòng đại diện nước ngoài khác nhau như thế nào?",
        "rationale": "Điều 31 phân biệt thời hạn 180 ngày đối với giấy phép thành lập và hoạt động của tổ chức tín dụng hoặc giấy phép thành lập chi nhánh ngân hàng nước ngoài với thời hạn 60 ngày đối với giấy phép thành lập văn phòng đại diện nước ngoài; trường hợp từ chối phải thông báo bằng văn bản và nêu rõ lý do.",
    },
    "stage13e-098": {
        "query": "Thế chấp quyền sử dụng đất có thuộc trường hợp phải đăng ký biện pháp bảo đảm không?",
        "rationale": "Điểm a khoản 1 Điều 25 nêu riêng thế chấp quyền sử dụng đất là trường hợp đăng ký biện pháp bảo đảm tại Văn phòng đăng ký đất đai.",
    },
}


METADATA_EDITS: dict[str, dict[str, Any]] = {
    "stage13e-032": {"question_category": "direct"},
    "stage13e-058": {"question_category": "direct"},
    "stage13e-069": {
        "rationale": "Điều 16 yêu cầu cung cấp trước hợp đồng các thông tin chủ yếu về khoản vay, lãi suất, phí, điều kiện và các nội dung liên quan để khách hàng nắm rõ giao dịch.",
    },
    "stage13e-075": {"question_category": "direct"},
    "stage13e-079": {"question_category": "role"},
}


AUTHORIZED_IDS = set(REPLACEMENTS) | set(EDIT_SPECS) | set(METADATA_EDITS)
OLD_REJECTED_TARGETS = {
    "stage13e-037": "091aa50fc0b4c61d328f77a7dce21fb53717691ad6aa9a78cb58bca57798c561",
    "stage13e-038": "459549a81e609b0873fef571ec14740da30e756e49fc433b4dae18fed47cffdd",
    "stage13e-039": "db851918c51c6e95542b44b1cf160bd15ca0b3627daffe3d9053983f9f564c17",
    "stage13e-067": "4d11b36bf8230373ba733f43a1a956ee9831aa237b2368eff29a5384732a121d",
    "stage13e-083": "61dc9e901fd1c303e9b6969e1037bf5a9a3c1009bb4c3e018a0b242e2294d2ce",
}

CHANGE_NOTES = {
    "stage13e-032": "Question category changed from threshold to direct; the question itself and evidence target were retained.",
    "stage13e-037": "Replaced the duplicated UW-DSCR target with APR-EXPOSURE to cover total-exposure calculation and approval limits.",
    "stage13e-038": "Replaced the duplicated APR-TIER-4/two-exception target with the distinct Grade A/B Tier 2 approval rule.",
    "stage13e-039": "Replaced the duplicated Article 4 information-collection target with Article 12 responsibilities of the debt and off-balance-sheet management function.",
    "stage13e-046": "Narrowed the question to the management requirement actually stated by the evidence; it no longer asks the chunk to enumerate ratios.",
    "stage13e-050": "Removed the unsupported approval-routing workflow phrase and retained the evidence-supported SME information groups.",
    "stage13e-053": "Refocused the question from the two-exception/Tier 4 case to ordinary Grade C with exactly one soft exception.",
    "stage13e-058": "Question category changed from consequence to direct; the question and evidence target were retained.",
    "stage13e-059": "Retained the supported question and gold chunk, and expanded the rationale/evidence presentation to cover all five prohibited-conduct paragraphs.",
    "stage13e-062": "Reworded the question to preserve the Article 31 distinction between 180-day and 60-day licensing deadlines.",
    "stage13e-067": "Replaced the duplicated maker-checker target with the distinct re-approval triggers rule.",
    "stage13e-069": "Removed the unsupported collateral-security phrase from the rationale; question and evidence target were retained.",
    "stage13e-075": "Question category changed from consequence to direct; the question and evidence target were retained.",
    "stage13e-079": "Question category changed from customer-facing to role; the question and evidence target were retained.",
    "stage13e-083": "Replaced the duplicated required-document/hold-refer target with the distinct permitted repayment-structures rule.",
    "stage13e-098": "Narrowed the plural question to the single land-use-right mortgage point contained in the selected chunk.",
}


def _load_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _refresh_evidence(record: dict[str, Any], corpus: FrozenCorpusV2, rationale: str) -> None:
    chunk_id = record["expected_canonical_chunk_ids"][0]
    row = corpus.by_id[chunk_id]
    record["gold_evidence"] = [
        corpus.make_evidence(chunk_id, rationale, excerpt=_compact(row["content"]))
    ]


def _apply_replacement(record: dict[str, Any], spec: dict[str, Any], corpus: FrozenCorpusV2) -> None:
    chunk_id = spec["chunk_id"]
    row = corpus.by_id[chunk_id]
    source = corpus.source_identity(row["source_id"])
    record["query"] = spec["query"]
    record["query_type"] = spec["query_type"]
    record["question_category"] = spec["question_category"]
    record["difficulty"] = spec["difficulty"]
    record["expected_canonical_chunk_ids"] = [chunk_id]
    record["document"] = source
    record["visibility"] = "SCOPED" if source["synthetic"] else "SHARED"
    record["is_synthetic"] = source["synthetic"]
    record["filters"] = {**record["filters"], "namespace": source["namespace"]}
    record["tags"] = [
        "stage-13e-expanded-gold",
        record["specialist_scope"],
        spec["question_category"],
        spec["difficulty"].casefold(),
        *spec["tags"],
        "r1-replacement",
    ]
    _refresh_evidence(record, corpus, spec["rationale"])


def _apply_edit(record: dict[str, Any], spec: dict[str, Any], corpus: FrozenCorpusV2) -> None:
    if "query" in spec:
        record["query"] = spec["query"]
    _refresh_evidence(record, corpus, spec["rationale"])


def _apply_metadata(record: dict[str, Any], spec: dict[str, Any], corpus: FrozenCorpusV2) -> None:
    if "question_category" in spec:
        category = spec["question_category"]
        record["question_category"] = category
        tags = list(record["tags"])
        if len(tags) >= 3:
            tags[2] = category
        record["tags"] = tags
    if "rationale" in spec:
        _refresh_evidence(record, corpus, spec["rationale"])


def _display_evidence(record: dict[str, Any], changed: bool) -> str:
    text = _compact(record["gold_evidence"][0]["excerpt"])
    if changed:
        return text
    if len(text) <= 900:
        return text
    return text[:900].rsplit(" ", 1)[0] + "…"


def _write_review(records: list[dict[str, Any]], changed_ids: set[str]) -> None:
    seed = records[:25]
    new_records = records[25:]
    scope_counts = Counter(record["specialist_scope"] for record in records)
    provenance_counts = Counter("synthetic" if record["is_synthetic"] else "real_authoritative" for record in records)
    lines = [
        "# Stage 13E1-R1 — Expanded Gold Human-Review Corrections",
        "",
        "## Review scope",
        "",
        "Human review round: **R1**. The 25 Stage 12A records remain the frozen",
        "REVIEWED seed. The 75 Stage 13E records remain DRAFT and are not",
        "promoted by this revision.",
        "",
        "Changes from R0: 5 evidence targets replaced; 6 substantive question or",
        "gold-alignment edits; 5 metadata/rationale edits; 59 drafts untouched.",
        "Evidence below is fetched directly from frozen Corpus V2. No retrieval",
        "output was used to select or validate expected IDs.",
        "",
        f"- Combined records: {len(records)} (seed {len(seed)} REVIEWED + new {len(new_records)} DRAFT)",
        f"- Scope distribution: {dict(sorted(scope_counts.items()))}",
        f"- Provenance: {dict(sorted(provenance_counts.items()))}",
        "- Supported scopes only; BankingOperations is not present.",
        "",
        "## Final R1 DRAFT records",
        "",
    ]
    for record in new_records:
        record_id = record["evaluation_id"]
        evidence = record["gold_evidence"][0]
        locator = evidence["locator"]
        locator_text = ", ".join(
            f"{key}={locator[key]}"
            for key in ("article", "clause", "point", "jsonl_line")
            if locator.get(key) is not None
        )
        change_note = CHANGE_NOTES[record_id] if record_id in changed_ids else "Untouched from R0."
        lines.extend(
            [
                f"### {record_id}",
                "",
                f"- **Scope:** `{record['specialist_scope']}`",
                f"- **Question:** {record['query']}",
                f"- **Expected canonical chunk ID:** `{evidence['canonical_chunk_id']}`",
                f"- **Source:** {record['document']['title']} (`{record['document']['source_id']}` / `{record['document']['version_id']}`)",
                f"- **Visibility:** `{record['visibility']}`; provenance `{record['document']['provenance']}`",
                f"- **Locator:** {locator_text}; heading `{ ' › '.join(evidence['heading_path']) }`",
                f"- **Question type:** `{record['question_category']}`; **Difficulty:** `{record['difficulty']}`",
                f"- **Evidence:** {_display_evidence(record, record_id in changed_ids)}",
                f"- **Rationale:** {evidence['rationale']}",
                f"- **Change note:** {change_note}",
                "- **Status:** `DRAFT`",
                "",
            ]
        )
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def build() -> dict[str, Any]:
    if _sha256(PILOT_PATH) != PILOT_SHA256:
        raise ValueError("Frozen Stage 12A pilot SHA mismatch")
    before = _load_records(INPUT_PATH)
    if len(before) != 100:
        raise ValueError(f"Expected 100 pre-R1 records, found {len(before)}")
    if [record["status"] for record in before[:25]] != ["REVIEWED"] * 25:
        raise ValueError("Frozen seed is not exactly 25 REVIEWED records")
    if any(record["status"] != "DRAFT" for record in before[25:]):
        raise ValueError("All new pre-R1 records must be DRAFT")

    corpus = FrozenCorpusV2()
    after = copy.deepcopy(before)
    by_id = {record["evaluation_id"]: record for record in after}
    if set(REPLACEMENTS) & set(EDIT_SPECS) or set(REPLACEMENTS) & set(METADATA_EDITS) or set(EDIT_SPECS) & set(METADATA_EDITS):
        raise ValueError("Overlapping authorized change sets")
    if len(AUTHORIZED_IDS) != 16:
        raise ValueError(f"Expected 16 authorized IDs, found {len(AUTHORIZED_IDS)}")
    if not AUTHORIZED_IDS <= set(by_id):
        raise ValueError("An authorized ID is missing from the expanded artifact")

    for record_id, spec in REPLACEMENTS.items():
        _apply_replacement(by_id[record_id], spec, corpus)
    for record_id, spec in EDIT_SPECS.items():
        _apply_edit(by_id[record_id], spec, corpus)
    for record_id, spec in METADATA_EDITS.items():
        _apply_metadata(by_id[record_id], spec, corpus)

    for record in after:
        record_id = record["evaluation_id"]
        if record_id.startswith("stage13e-") and record["status"] != "DRAFT":
            raise ValueError(f"R1 changed status of {record_id}")
        if record_id not in AUTHORIZED_IDS and record != before[after.index(record)]:
            raise ValueError(f"Unauthorized mutation detected: {record_id}")
        if record_id in OLD_REJECTED_TARGETS and record["expected_canonical_chunk_ids"][0] == OLD_REJECTED_TARGETS[record_id]:
            raise ValueError(f"Rejected old evidence target retained for {record_id}")

    validator = CanonicalGoldValidator(corpus)
    for line_no, record in enumerate(after, 1):
        validator.validate_record(record, after[: line_no - 1], line_no)
    leakage = {record["evaluation_id"]: leakage_flags(record, corpus) for record in after if leakage_flags(record, corpus)}
    if leakage:
        raise ValueError(f"R1 leakage flags: {leakage}")
    if Counter(record["status"] for record in after) != Counter({"REVIEWED": 25, "DRAFT": 75}):
        raise ValueError("Unexpected R1 status distribution")
    if Counter(record["specialist_scope"] for record in after) != Counter({scope: 20 for scope in ("credit", "risk_management", "legal_compliance", "customer_relationship", "collateral_appraisal")}):
        raise ValueError("R1 scope distribution drifted")
    if Counter("synthetic" if record["is_synthetic"] else "real_authoritative" for record in after) != Counter({"real_authoritative": 80, "synthetic": 20}):
        raise ValueError("R1 provenance distribution drifted")
    if len({record["evaluation_id"] for record in after}) != 100 or len({record["query"] for record in after}) != 100:
        raise ValueError("R1 duplicate IDs or questions")
    item004 = by_id["stage12a-004"]
    if item004["expected_canonical_chunk_ids"] != [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]:
        raise ValueError("stage12a-004 multi-gold seed changed")

    seed_lines = INPUT_PATH.read_text(encoding="utf-8").splitlines()[:25]
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for line in seed_lines:
            handle.write(line + "\n")
        for record in after[25:]:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    _write_review(after, AUTHORIZED_IDS)
    return {
        "records": len(after),
        "authorized_changes": len(AUTHORIZED_IDS),
        "status": dict(Counter(record["status"] for record in after)),
        "expanded_sha256": _sha256(OUTPUT_PATH),
        "review_pack": str(REVIEW_PATH.relative_to(PROJECT_ROOT)),
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, sort_keys=True))
