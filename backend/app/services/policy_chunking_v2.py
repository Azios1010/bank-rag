import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Dict, List


CHUNKER_VERSION = "bank-rag-v2-chunker-2.0.0"
TARGET_SIZE = 2400
HARD_LIMIT = 4800


class PolicyChunkerV2:
    """Deterministic, lossless legal-text chunker.

    Hierarchy is supplied as metadata instead of repeating article/clause text
    in every child chunk. This prevents a large parent provision from turning
    every child fragment into an oversized copy.
    """

    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.anomalies: List[Dict[str, Any]] = []
        self._identity_by_ordinal: Dict[int, str] = {}
        self._classification_by_ordinal: Dict[int, str] = {}

    def get_deterministic_id(self, chunk_data: dict) -> str:
        hash_dict = {
            "chunker_version": CHUNKER_VERSION,
            "source_id": chunk_data.get("source_id"),
            "version_id": chunk_data.get("version_id"),
            "chapter": chunk_data.get("chapter"),
            "section": chunk_data.get("section"),
            "article": chunk_data.get("article"),
            "clause": chunk_data.get("clause"),
            "point": chunk_data.get("point"),
            "hierarchy_instance": chunk_data.get("hierarchy_instance"),
            "hierarchy_classification": chunk_data.get("hierarchy_classification"),
            "context_mode": chunk_data.get("context_mode"),
            "content": chunk_data.get("content"),
            "provenance": chunk_data.get("provenance"),
            "is_fragment": chunk_data.get("is_fragment"),
            "fragment_index": chunk_data.get("fragment_index"),
        }
        return hashlib.sha256(json.dumps(hash_dict, sort_keys=True).encode("utf-8")).hexdigest()

    @staticmethod
    def _hierarchy_key(record: Dict[str, Any]):
        return tuple(record.get(name) for name in (
            "source_id", "version_id", "chapter", "section", "article", "clause", "point"
        ))

    def _classify_hierarchy(self, provisions: List[Dict[str, Any]]) -> None:
        grouped: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
        for record in provisions:
            grouped[self._hierarchy_key(record)].append(record)

        for key, records in grouped.items():
            repeated = len(records) > 1
            for occurrence, record in enumerate(records, start=1):
                ordinal = record["_input_ordinal"]
                self._identity_by_ordinal[ordinal] = (
                    f"article={record.get('article') or '-'}|"
                    f"clause={record.get('clause') or '-'}|"
                    f"point={record.get('point') or '-'}|occurrence={occurrence}"
                )
                if record.get("point") is not None and record.get("clause") is None:
                    self._classification_by_ordinal[ordinal] = "DIRECT_ARTICLE_POINT"
                elif repeated:
                    self._classification_by_ordinal[ordinal] = "REPEATED_LABEL_GENUINE"
                else:
                    self._classification_by_ordinal[ordinal] = "NORMAL"

            if repeated:
                ordinals = [record["_input_ordinal"] for record in records]
                self.anomalies.append({
                    "anomaly_id": f"repeated_label_{key[0]}_{ordinals[0]}",
                    "anomaly_type": "REPEATED_HIERARCHY_LABEL",
                    "severity": "WARNING",
                    "source_id": key[0],
                    "input_ordinals": ordinals,
                    "details": (
                        "Repeated hierarchy label retained as distinct consolidated, amendment, "
                        "or annex material; occurrence identity is deterministic."
                    ),
                })

        for record in provisions:
            if record.get("point") is not None and record.get("clause") is None:
                ordinal = record["_input_ordinal"]
                self.anomalies.append({
                    "anomaly_id": f"direct_article_point_{record['source_id']}_{ordinal}",
                    "anomaly_type": "DIRECT_ARTICLE_POINT",
                    "severity": "WARNING",
                    "source_id": record.get("source_id"),
                    "input_ordinals": [ordinal],
                    "details": (
                        "Point is retained as a direct child of its article; no clause was "
                        "present in normalized parser evidence."
                    ),
                })

    def process_dataset(self, provisions: List[Dict[str, Any]]):
        self.chunks = []
        self.anomalies = []
        self._identity_by_ordinal = {}
        self._classification_by_ordinal = {}
        for idx, provision in enumerate(provisions, start=1):
            provision["_input_ordinal"] = idx

        self._classify_hierarchy(provisions)
        for article_records in self._article_instances(provisions):
            self._process_article_instance(article_records)
        self._detect_legal_duplicates()

    @staticmethod
    def _article_instances(provisions: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split an article whenever its own heading reappears in source order."""
        instances: List[List[Dict[str, Any]]] = []
        current: List[Dict[str, Any]] = []
        current_key = None
        for record in provisions:
            key = tuple(record.get(name) for name in ("source_id", "version_id", "chapter", "section", "article"))
            is_article_heading = record.get("clause") is None and record.get("point") is None
            if current and (key != current_key or is_article_heading):
                instances.append(current)
                current = []
            current.append(record)
            current_key = key
        if current:
            instances.append(current)
        return instances

    def _process_article_instance(self, records: List[Dict[str, Any]]) -> None:
        full_content = "\n".join(record.get("content", "") for record in records)
        # Keep small articles as a single retrieval unit. Larger articles are
        # emitted at normalized-provision level, with metadata-only context.
        if len(full_content) <= TARGET_SIZE:
            lead = records[0]
            self._create_chunk(
                full_content,
                records,
                {
                    "clause": None,
                    "point": None,
                    "hierarchy_instance": (
                        f"article={lead.get('article') or '-'}|article-instance="
                        f"{lead['_input_ordinal']}"
                    ),
                    "hierarchy_classification": "NORMAL",
                },
            )
            return
        for record in records:
            level_info = {
                "clause": record.get("clause"),
                "point": record.get("point"),
                "hierarchy_instance": self._identity_by_ordinal[record["_input_ordinal"]],
                "hierarchy_classification": self._classification_by_ordinal[record["_input_ordinal"]],
            }
            content = record.get("content", "")
            if len(content) <= TARGET_SIZE:
                self._create_chunk(content, [record], level_info)
            else:
                self._split_and_emit(content, [record], level_info)

    def _create_chunk(self, content: str, records: List[Dict[str, Any]], level_info: dict,
                      is_fragment: bool = False, fragment_index: int = 0):
        if not records:
            return
        if len(content) > HARD_LIMIT:
            raise ValueError(f"Chunk construction exceeded hard limit {HARD_LIMIT}: {len(content)}")
        base = records[0]
        pages = [value for record in records for value in (record.get("page_start"), record.get("page_end")) if value is not None]
        chunk = {
            "chunker_version": CHUNKER_VERSION,
            "source_id": base.get("source_id"),
            "version_id": base.get("version_id"),
            "chapter": base.get("chapter"),
            "section": base.get("section"),
            "article": base.get("article"),
            "clause": level_info.get("clause"),
            "point": level_info.get("point"),
            "hierarchy_instance": level_info["hierarchy_instance"],
            "hierarchy_classification": level_info["hierarchy_classification"],
            "context_mode": "metadata_only",
            "heading_path": base.get("heading_path", []),
            "content": content,
            "page_start": min(pages) if pages else 0,
            "page_end": max(pages) if pages else 0,
            "provenance": [
                {"input_ordinal": record["_input_ordinal"], "content_hash": record["content_hash"]}
                for record in records
            ],
            "is_long_unsplittable": False,
            "is_fragment": is_fragment,
            "fragment_index": fragment_index,
        }
        chunk["canonical_chunk_id"] = self.get_deterministic_id(chunk)
        self.chunks.append(chunk)

    @staticmethod
    def _split_text(text: str, max_size: int) -> List[str]:
        """Losslessly split paragraph -> Vietnamese sentence -> whitespace -> hard boundary."""
        if len(text) <= max_size:
            return [text]
        result: List[str] = []
        remaining = text
        paragraph_boundary = re.compile(r"\n\s*\n")
        # Vietnamese legal prose commonly uses all of these punctuation marks.
        sentence_boundary = re.compile(r"(?<=[.!?;:…])\s+")
        whitespace_boundary = re.compile(r"\s+")
        while len(remaining) > max_size:
            prefix = remaining[:max_size]
            boundary = 0
            for pattern in (paragraph_boundary, sentence_boundary, whitespace_boundary):
                matches = list(pattern.finditer(prefix))
                if matches:
                    boundary = matches[-1].end()
                    break
            if boundary == 0:
                boundary = max_size
            result.append(remaining[:boundary])
            remaining = remaining[boundary:]
        result.append(remaining)
        return result

    def _split_and_emit(self, text: str, records: List[Dict[str, Any]], level_info: dict) -> None:
        for index, fragment in enumerate(self._split_text(text, TARGET_SIZE), start=1):
            self._create_chunk(fragment, records, level_info, is_fragment=True, fragment_index=index)

    def _detect_legal_duplicates(self) -> None:
        groups: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
        for chunk in self.chunks:
            groups[(chunk["source_id"], chunk["version_id"], chunk["content"])].append(chunk)
        for (source_id, _version_id, _content), chunks in groups.items():
            if len(chunks) > 1:
                ids = [chunk["canonical_chunk_id"] for chunk in chunks]
                ordinals = sorted({item["input_ordinal"] for chunk in chunks for item in chunk["provenance"]})
                self.anomalies.append({
                    "anomaly_id": f"duplicate_legal_text_{ids[0][:8]}",
                    "anomaly_type": "EXACT_DUPLICATE_LEGAL_TEXT",
                    "severity": "WARNING",
                    "source_id": source_id,
                    "input_ordinals": ordinals,
                    "details": (
                        "Exact text is retained from distinct normalized provisions; it is legal-text "
                        "duplication, not chunk-context replication."
                    ),
                    "canonical_chunk_ids": ids,
                })
