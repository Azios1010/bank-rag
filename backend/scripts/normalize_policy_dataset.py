"""Extract and normalize official policy PDFs into the dataset contract.

The raw PDFs remain immutable. This command only writes reviewable records
under dataset/normalized/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "dataset" / "raw" / "policies"
NORMALIZED_DIR = REPO_ROOT / "dataset" / "normalized"
MANIFEST_PATH = RAW_DIR / "provenance.json"

PRODUCT_CODE = "SME_UNSECURED_WORKING_CAPITAL"
PARSER_VERSION = "pypdf-structure-v1"
CHUNKER_VERSION = "article-clause-v1"
MAX_CHUNK_CHARS = 8_000

EFFECTIVE_FROM = {
    "vn-nhnn-21-vbhn-2024-lending": "2017-03-15",
    "vn-nhnn-52-2025-amendment": "2025-12-25",
    "vn-nhnn-4033-2025-correction": "2025-12-25",
    "vn-qh15-law-91-2025-personal-data": "2026-01-01",
    "vn-cp-decree-356-2025-personal-data": "2026-01-01",
    "vn-vpqh-158-vbhn-2025-part-1": "2024-07-01",
    "vn-vpqh-158-vbhn-2025-part-2": "2024-07-01",
}

AUTHORITY_LEVEL = {
    "vn-qh15-law-91-2025-personal-data": "STATUTE",
    "vn-vpqh-158-vbhn-2025-part-1": "STATUTE",
    "vn-vpqh-158-vbhn-2025-part-2": "STATUTE",
    "vn-nhnn-4033-2025-correction": "OFFICIAL_GUIDANCE",
}

AGENT_SCOPES = {
    "lending": ["Credit", "LegalCompliance", "ReviewerAgent", "RiskManagement"],
    "privacy": ["CustomerRelationship", "LegalCompliance", "ReviewerAgent"],
    "credit_law": ["Credit", "LegalCompliance", "ReviewerAgent", "RiskManagement"],
}


@dataclass(frozen=True)
class Line:
    page: int
    text: str


@dataclass
class Article:
    article_number: str
    title: str
    chapter: str | None
    section: str | None
    lines: list[Line]


@dataclass
class ChunkCandidate:
    content: str
    page_start: int
    page_end: int
    chapter: str | None
    section: str | None
    article_number: str | None
    article_title: str | None
    clause: str | None
    point: str | None


def _clean_line(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\u00a0", " ").replace("\u200b", "")
    value = re.sub(r"[ \t]+", " ", value).strip()
    # Official gazette footnote markers can be concatenated to a legal
    # clause number by PDF extraction (for example "1.4 Cho vay").
    value = re.sub(r"^(\d+)\.\d+\s+", r"\1. ", value)
    # A few embedded-font PDFs put a space before a Vietnamese diacritic
    # (for example "c òn" or "b ảo"). Joining this safe subset improves
    # lexical retrieval without guessing at normal word boundaries.
    diacritics = "àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ"
    value = re.sub(
        rf"(?<!\w)([A-Za-zĐđ])\s+(?=[{diacritics}])",
        r"\1",
        value,
    )
    if len(value) >= 2 and value[0].isupper() and value[1] == " ":
        value = value[0] + value[2:]
    return value


def _page_lines(page_number: int, text: str) -> list[Line]:
    footer_prefixes = (
        "VĂN PHÒNG CHÍNH PHỦ XUẤT BẢN",
        "Địa chỉ: Số 1, Hoàng Hoa Thám",
        "Điện thoại liên hệ:",
        "- Nội dung:",
        "- Phát hành:",
        "Email:",
        "Website http://congbao.chinhphu.vn",
    )
    lines: list[Line] = []
    for index, raw_line in enumerate(text.splitlines()):
        line = _clean_line(raw_line)
        if not line:
            continue
        if line.startswith("CÔNG BÁO/") or re.match(r"^\d+\s+CÔNG BÁO/", line):
            continue
        if line.startswith(footer_prefixes):
            continue
        if index < 6 and re.fullmatch(r"\d{1,4}", line):
            continue
        if set(line) <= {"-", "_", "=", " "}:
            continue
        lines.append(Line(page=page_number, text=line))
    return lines


def _extract_lines(path: Path) -> list[Line]:
    reader = PdfReader(str(path))
    lines: list[Line] = []
    for page_number, page in enumerate(reader.pages, start=1):
        lines.extend(_page_lines(page_number, page.extract_text() or ""))
    return lines


def _is_heading_title(value: str) -> bool:
    letters = [char for char in value if char.isalpha()]
    return bool(letters) and sum(char.isupper() for char in letters) / len(letters) > 0.7


def _detect_chapter(text: str) -> str | None:
    match = re.match(r"^(Chương\s+[IVXLCDM\d]+)\b(?:\s+(.*))?$", text, re.IGNORECASE)
    if not match:
        return None
    suffix = (match.group(2) or "").strip()
    return f"{match.group(1)} {suffix}".strip()


def _detect_section(text: str) -> str | None:
    match = re.match(r"^(Mục|Phần)\s+([IVXLCDM\d]+)\b(?:\s+(.*))?$", text, re.IGNORECASE)
    if not match:
        return None
    suffix = (match.group(3) or "").strip()
    return f"{match.group(1)} {match.group(2)} {suffix}".strip()


def _detect_article(text: str) -> tuple[str, str] | None:
    match = re.match(r"^Điều\s+([0-9]+[A-Za-z]?)\.\s*(.*)$", text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1), match.group(2).strip()


def _detect_clause(text: str) -> str | None:
    match = re.match(r"^(\d+)\.\s+.+", text)
    return match.group(1) if match else None


def _detect_point(text: str) -> str | None:
    match = re.match(r"^([a-zđ])\)\s+.+", text, re.IGNORECASE)
    return match.group(1).lower() if match else None


def _normalize_articles(lines: list[Line]) -> tuple[list[Article], list[Line]]:
    articles: list[Article] = []
    orphan_lines: list[Line] = []
    current: Article | None = None
    chapter: str | None = None
    section: str | None = None
    pending_heading: str | None = None
    last_article_number = -1

    def flush() -> None:
        nonlocal current
        if current is not None:
            articles.append(current)
            current = None

    for line in lines:
        chapter_heading = _detect_chapter(line.text)
        section_heading = _detect_section(line.text)
        article_heading = _detect_article(line.text)

        if chapter_heading:
            flush()
            chapter = chapter_heading
            pending_heading = chapter_heading
            orphan_lines.append(line)
            continue
        if section_heading:
            flush()
            section = section_heading
            pending_heading = section_heading
            orphan_lines.append(line)
            continue
        if article_heading:
            candidate_number = int(re.match(r"\d+", article_heading[0]).group())
            # Quoted amendment text can contain a heading such as
            # "Điều 3. Quy định chuyển tiếp" after the main document has
            # already reached Điều 209. Article numbering is monotonic in
            # each source PDF, so a decrease is treated as body text.
            if candidate_number < last_article_number:
                if current is None:
                    orphan_lines.append(line)
                else:
                    current.lines.append(line)
                continue
            flush()
            article_number, article_title = article_heading
            current = Article(
                article_number=article_number,
                title=article_title,
                chapter=chapter,
                section=section,
                lines=[line],
            )
            last_article_number = candidate_number
            pending_heading = None
            continue

        if pending_heading and _is_heading_title(line.text) and len(line.text) <= 300:
            if pending_heading in orphan_lines[-1].text:
                orphan_lines[-1] = Line(
                    page=orphan_lines[-1].page,
                    text=f"{pending_heading} - {line.text}",
                )
                pending_heading = None
                continue

        if current is None:
            orphan_lines.append(line)
        else:
            current.lines.append(line)

    flush()
    return articles, orphan_lines


def _join_lines(lines: Iterable[Line]) -> str:
    return "\n".join(line.text for line in lines).strip()


def _split_text(
    lines: list[Line],
    *,
    header: str,
    chapter: str | None,
    section: str | None,
    article_number: str | None,
    article_title: str | None,
    clause: str | None,
) -> list[ChunkCandidate]:
    if not lines:
        return []

    chunks: list[ChunkCandidate] = []
    current: list[Line] = []
    header_len = len(header) + 1

    def flush() -> None:
        if not current:
            return
        content = _join_lines([Line(current[0].page, header), *current])
        if len(content) >= 20:
            chunks.append(
                ChunkCandidate(
                    content=content,
                    page_start=min(line.page for line in current),
                    page_end=max(line.page for line in current),
                    chapter=chapter,
                    section=section,
                    article_number=article_number,
                    article_title=article_title,
                    clause=clause,
                    point=None,
                )
            )
        current.clear()

    for line in lines:
        proposed = len(_join_lines([Line(line.page, header), *current, line]))
        if current and proposed > MAX_CHUNK_CHARS:
            flush()
        current.append(line)
        if len(_join_lines(current)) + header_len > MAX_CHUNK_CHARS:
            flush()
    flush()
    return chunks


def _article_chunks(article: Article) -> list[ChunkCandidate]:
    header = f"Điều {article.article_number}"
    if article.title:
        header = f"{header}. {article.title}"

    body = article.lines[1:]
    clause_positions = [
        (index, _detect_clause(line.text))
        for index, line in enumerate(body)
        if _detect_clause(line.text) is not None
    ]
    if not clause_positions:
        return _split_text(
            body or article.lines,
            header=header,
            chapter=article.chapter,
            section=article.section,
            article_number=article.article_number,
            article_title=article.title or None,
            clause=None,
        )

    chunks: list[ChunkCandidate] = []
    prefix = body[: clause_positions[0][0]]
    if prefix:
        chunks.extend(
            _split_text(
                prefix,
                header=header,
                chapter=article.chapter,
                section=article.section,
                article_number=article.article_number,
                article_title=article.title or None,
                clause=None,
            )
        )

    for position, (start, clause) in enumerate(clause_positions):
        end = clause_positions[position + 1][0] if position + 1 < len(clause_positions) else len(body)
        clause_lines = body[start:end]
        chunks.extend(
            _split_text(
                clause_lines,
                header=header,
                chapter=article.chapter,
                section=article.section,
                article_number=article.article_number,
                article_title=article.title or None,
                clause=clause,
            )
        )
    return chunks


def _orphan_chunks(lines: list[Line]) -> list[ChunkCandidate]:
    by_page: dict[int, list[Line]] = {}
    for line in lines:
        by_page.setdefault(line.page, []).append(line)

    chunks: list[ChunkCandidate] = []
    for page, page_lines in sorted(by_page.items()):
        heading = page_lines[0].text[:200]
        chunks.extend(
            _split_text(
                page_lines,
                header=heading,
                chapter=None,
                section="PreambleOrBackMatter",
                article_number=None,
                article_title=None,
                clause=None,
            )
        )
    return chunks


def _bundle_for(document_id: str) -> str:
    if document_id.startswith("vn-nhnn-"):
        return "lending"
    if "personal-data" in document_id:
        return "privacy"
    return "credit_law"


def _source_record(document: dict[str, Any]) -> dict[str, Any]:
    document_id = document["document_id"]
    version_id = f"{document_id}-v1"
    amendment_ids = [
        relation["target_document_id"]
        for relation in document.get("relations", [])
        if relation["type"] in {"AMENDED_BY", "CORRECTED_BY"}
    ]
    return {
        "source_id": document_id,
        "title": document["title"],
        "namespace": "REGULATION",
        "issuer": document["issuer"],
        "authority_level": AUTHORITY_LEVEL.get(document_id, "REGULATION"),
        "jurisdiction": "VN",
        "language": "vi",
        "canonical_url": document["canonical_url"],
        "synthetic": False,
        "usage_rights": {
            "license_id": None,
            "redistribution": "UNKNOWN",
            "notes": (
                "Official gazette source; attribution to congbao.chinhphu.vn "
                "is required. Verify redistribution terms before publication."
            ),
        },
        "allowed_product_codes": [PRODUCT_CODE],
        "allowed_agent_scopes": AGENT_SCOPES[_bundle_for(document_id)],
        "versions": [
            {
                "version_id": version_id,
                "version_label": f"{document['document_number']} snapshot {document['issued_on']}",
                "effective_from": EFFECTIVE_FROM[document_id],
                "effective_to": None,
                "status": "IN_REVIEW",
                "retrieved_at": document.get(
                    "retrieved_at",
                    "2026-07-25T14:36:15Z",
                ),
                "content_hash": f"sha256:{document['sha256']}",
                "object_path": f"raw/policies/{document['filename']}",
                "media_type": document["media_type"],
                "amendment_source_ids": amendment_ids,
                "supersedes_version_id": None,
                "review": {
                    "status": "UNREVIEWED",
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "notes": "Automatically extracted; legal/content review pending.",
                },
            }
        ],
    }


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "section"


def _chunk_record(
    candidate: ChunkCandidate,
    *,
    document: dict[str, Any],
    version_id: str,
    chunk_index: int,
) -> dict[str, Any]:
    source_id = document["document_id"]
    article = (
        f"Điều {candidate.article_number}"
        if candidate.article_number is not None
        else None
    )
    heading_path = [
        value
        for value in (
            candidate.chapter,
            candidate.section,
            article,
            candidate.article_title,
        )
        if value
    ]
    section_bits = [
        source_id,
        candidate.chapter or candidate.section or "preamble",
        article or "page",
        candidate.clause or "all",
        str(candidate.page_start),
    ]
    chunk_id = _slug("-".join(section_bits)) + f"-{chunk_index:04d}"
    content_hash = hashlib.sha256(candidate.content.encode("utf-8")).hexdigest()
    return {
        "chunk_id": chunk_id[:128],
        "source_id": source_id,
        "version_id": version_id,
        "namespace": "REGULATION",
        "chunk_index": chunk_index,
        "parent_chunk_id": None,
        "heading_path": heading_path or ["PreambleOrBackMatter"],
        "locator": {
            "chapter": candidate.chapter,
            "article": article,
            "clause": candidate.clause,
            "point": candidate.point,
            "section_id": _slug("-".join(section_bits))[:200],
            "page_start": candidate.page_start,
            "page_end": candidate.page_end,
        },
        "content": candidate.content[:12000],
        "content_hash": f"sha256:{content_hash}",
        "effective_from": EFFECTIVE_FROM[source_id],
        "effective_to": None,
        "allowed_product_codes": [PRODUCT_CODE],
        "allowed_agent_scopes": AGENT_SCOPES[_bundle_for(source_id)],
        "token_count": len(re.findall(r"\S+", candidate.content)),
        "parser_version": PARSER_VERSION,
        "chunker_version": CHUNKER_VERSION,
    }


def _assert_basic_contract(source: dict[str, Any], chunk: dict[str, Any]) -> None:
    identifier_pattern = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
    for key in ("source_id", "version_id", "chunk_id"):
        value = source.get(key) if key == "source_id" else chunk[key]
        if not identifier_pattern.fullmatch(value):
            raise ValueError(f"Invalid identifier for {key}: {value}")
    if not chunk["content"].strip() or len(chunk["content"]) < 20:
        raise ValueError(f"Chunk content too short: {chunk['chunk_id']}")
    if len(chunk["content"]) > 12000:
        raise ValueError(f"Chunk content too long: {chunk['chunk_id']}")


def normalize() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = [_source_record(document) for document in manifest["documents"]]
    source_by_id = {source["source_id"]: source for source in sources}
    chunks: list[dict[str, Any]] = []
    report_documents: list[dict[str, Any]] = []

    for document in manifest["documents"]:
        pdf_path = RAW_DIR / document["filename"]
        lines = _extract_lines(pdf_path)
        articles, orphan_lines = _normalize_articles(lines)
        candidates: list[ChunkCandidate] = []
        for article in articles:
            candidates.extend(_article_chunks(article))
        candidates.extend(_orphan_chunks(orphan_lines))

        version_id = f"{document['document_id']}-v1"
        document_chunks = [
            _chunk_record(
                candidate,
                document=document,
                version_id=version_id,
                chunk_index=index,
            )
            for index, candidate in enumerate(candidates)
        ]
        for chunk in document_chunks:
            _assert_basic_contract(source_by_id[document["document_id"]], chunk)
        chunks.extend(document_chunks)
        report_documents.append(
            {
                "document_id": document["document_id"],
                "filename": document["filename"],
                "pages": document["pages"],
                "extracted_lines": len(lines),
                "articles": len(articles),
                "chunks": len(document_chunks),
                "unstructured_lines": len(orphan_lines),
            }
        )

    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    (NORMALIZED_DIR / "policy-sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (NORMALIZED_DIR / "policy-sources.jsonl").write_text(
        "\n".join(json.dumps(source, ensure_ascii=False) for source in sources) + "\n",
        encoding="utf-8",
    )
    (NORMALIZED_DIR / "policy-chunks.jsonl").write_text(
        "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks) + "\n",
        encoding="utf-8",
    )

    report = {
        "report_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parser_version": PARSER_VERSION,
        "chunker_version": CHUNKER_VERSION,
        "source_status": "IN_REVIEW",
        "documents": report_documents,
        "totals": {
            "documents": len(sources),
            "pages": sum(item["pages"] for item in report_documents),
            "articles": sum(item["articles"] for item in report_documents),
            "chunks": len(chunks),
            "unstructured_lines": sum(
                item["unstructured_lines"] for item in report_documents
            ),
        },
        "warnings": [
            "Chunks are extraction candidates and require content/legal review.",
            "Page locators are physical PDF page numbers, not gazette page numbers.",
            "No automatic OCR was applied; image-only pages would be reported as empty.",
            "pypdf may preserve embedded-font spacing artifacts in Vietnamese words; review extracted text before embedding.",
        ],
    }
    (NORMALIZED_DIR / "normalization-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    if args.repo_root.resolve() != REPO_ROOT.resolve():
        raise SystemExit("This script currently supports the checked-out repository root only.")
    report = normalize()
    print(json.dumps(report["totals"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
