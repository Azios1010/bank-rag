import json
from collections.abc import Iterator
from pathlib import Path

from app.db.models import PolicyDocument, PolicyEmbedding
from sqlalchemy import select
from sqlalchemy.orm import Session


class GoldDatasetError(Exception):
    pass


class GoldParser:
    def __init__(self, db: Session):
        self._db = db

    def parse_file(self, filepath: Path) -> Iterator[dict]:
        if not filepath.exists():
            raise GoldDatasetError(f"Gold retrieval dataset is missing:\n{filepath}")
            
        seen_eval_ids = set()
        
        with open(filepath, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    raise GoldDatasetError(f"Invalid JSON at line {line_no}: {e}")
                
                self._validate_record(record, seen_eval_ids, line_no)
                self._resolve_evidence(record, line_no)
                
                yield record

    def _validate_record(self, record: dict, seen: set, line_no: int):
        required_fields = [
            "evaluation_id", "query", "query_type", "agent_scope", "assessment_date", 
            "filters", "gold_evidence", "forbidden_version_ids", 
            "expected_coverage", "tags"
        ]
        for field in required_fields:
            if field not in record:
                raise GoldDatasetError(f"Line {line_no}: Missing required field '{field}'")
                
        allowed_query_types = {
            "POLICY_LOOKUP", "ELIGIBILITY_SUPPORT", "CALCULATION_GUIDANCE",
            "MULTI_SOURCE", "NEGATIVE_NO_EVIDENCE"
        }
        if record["query_type"] not in allowed_query_types:
            raise GoldDatasetError(f"Line {line_no}: Invalid query_type '{record['query_type']}'")
                
        eval_id = record["evaluation_id"]
        if eval_id in seen:
            raise GoldDatasetError(f"Line {line_no}: Duplicate evaluation_id '{eval_id}'")
        seen.add(eval_id)
        
        gold_sources = set()
        for ev in record.get("gold_evidence", []):
            if not isinstance(ev, dict):
                raise GoldDatasetError(f"Line {line_no}: gold_evidence must be objects")
            if "source_id" not in ev or "version_id" not in ev or "section_id" not in ev:
                raise GoldDatasetError(f"Line {line_no}: gold_evidence missing required fields")
            gold_sources.add(ev["version_id"])
            
        forbidden = set(record.get("forbidden_version_ids", []))
        overlap = gold_sources.intersection(forbidden)
        if overlap:
            raise GoldDatasetError(f"Line {line_no}: Contradictory gold/forbidden version selectors for {overlap}")
            
    def _resolve_evidence(self, record: dict, line_no: int):
        resolved_ids = []
        for ev in record.get("gold_evidence", []):
            if ev.get("chunk_id"):
                # Exact chunk id provided
                chunk_id = ev["chunk_id"]
                # Validate it exists
                stmt = select(PolicyEmbedding.canonical_chunk_id).where(
                    PolicyEmbedding.canonical_chunk_id == chunk_id
                ).limit(1)
                if not self._db.execute(stmt).scalar():
                    raise GoldDatasetError(f"Line {line_no}: Invalid reference, chunk_id '{chunk_id}' not found")
                resolved_ids.append(chunk_id)
            else:
                # Resolve by source/version/section
                source_id = ev["source_id"]
                version_id = ev["version_id"]
                section_id = ev["section_id"]
                
                stmt = (
                    select(PolicyEmbedding.canonical_chunk_id)
                    .join(PolicyDocument, PolicyEmbedding.policy_document_id == PolicyDocument.id)
                    .where(
                        PolicyDocument.canonical_source_id == source_id,
                        PolicyDocument.canonical_version_id == version_id,
                        PolicyEmbedding.metadata_["section_id"].astext == section_id,
                        PolicyEmbedding.canonical_chunk_id.is_not(None)
                    )
                )
                rows = self._db.execute(stmt).scalars().all()
                if not rows:
                    raise GoldDatasetError(f"Line {line_no}: No canonical chunk matches {source_id}/{version_id}/{section_id}")
                
                # If there are multiple unique canonical chunks for a section, we have to resolve all of them safely
                # Wait, "resolution would be unsafe/ambiguous according to the dataset contract"
                # A section might have multiple chunks, which is valid and expected. We include all of them.
                resolved_ids.extend(list(set(rows)))
                
        record["resolved_canonical_chunk_ids"] = list(set(resolved_ids))
