import json
import hashlib
import re
from typing import List, Dict, Any, Optional

CHUNKER_VERSION = "bank-rag-v2-chunker-1.0.0"
TARGET_SIZE = 2400
HARD_LIMIT = 4800

class PolicyChunkerV2:
    def __init__(self):
        self.chunks = []
        self.anomalies = []

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
            "content": chunk_data.get("content"),
            "provenance": chunk_data.get("provenance"),
            "is_fragment": chunk_data.get("is_fragment"),
            "fragment_index": chunk_data.get("fragment_index")
        }
        return hashlib.sha256(json.dumps(hash_dict, sort_keys=True).encode("utf-8")).hexdigest()

    def process_dataset(self, provisions: List[Dict[str, Any]]):
        # 1. Group by Article
        article_groups = {}
        for idx, p in enumerate(provisions):
            p["_input_ordinal"] = idx + 1
            key = (p.get("source_id"), p.get("version_id"), p.get("chapter"), p.get("section"), p.get("article"))
            if key not in article_groups:
                article_groups[key] = []
            article_groups[key].append(p)
            
            # Check for orphan points
            if p.get("point") is not None and p.get("clause") is None:
                self.anomalies.append({
                    "anomaly_id": f"orphan_{p['source_id']}_{idx+1}",
                    "anomaly_type": "ORPHAN_POINT_WITHOUT_CLAUSE",
                    "severity": "WARNING",
                    "source_id": p.get("source_id"),
                    "input_ordinals": [p["_input_ordinal"]],
                    "details": f"Point {p.get('point')} found without a clause in article {p.get('article')}"
                })

        # 2. Check for duplicate hierarchy keys
        hierarchy_keys = {}
        for p in provisions:
            hk = (p.get("source_id"), p.get("version_id"), p.get("chapter"), p.get("section"), p.get("article"), p.get("clause"), p.get("point"))
            if hk not in hierarchy_keys:
                hierarchy_keys[hk] = []
            hierarchy_keys[hk].append(p)
            
        for hk, recs in hierarchy_keys.items():
            if len(recs) > 1:
                self.anomalies.append({
                    "anomaly_id": f"dup_{hk[0]}_{recs[0]['_input_ordinal']}",
                    "anomaly_type": "DUPLICATE_HIERARCHY_KEY",
                    "severity": "WARNING",
                    "source_id": hk[0],
                    "input_ordinals": [r["_input_ordinal"] for r in recs],
                    "details": f"Duplicate hierarchy key: {hk}"
                })

        # 3. Process each Article Group
        for ag_key, recs in article_groups.items():
            self._process_article_group(ag_key, recs)

        # 4. Check for EXACT_DUPLICATE_CONTENT
        content_groups = {}
        for c in self.chunks:
            content = c["content"]
            key = (c.get("source_id"), c.get("version_id"), content)
            if key not in content_groups:
                content_groups[key] = []
            content_groups[key].append(c)

        for (src, ver, content), recs in content_groups.items():
            if len(recs) > 1:
                ids = [r["canonical_chunk_id"] for r in recs]
                input_ords = set()
                for r in recs:
                    for prov in r["provenance"]:
                        input_ords.add(prov["input_ordinal"])
                
                self.anomalies.append({
                    "anomaly_id": f"exact_dup_content_{ids[0][:8]}",
                    "anomaly_type": "EXACT_DUPLICATE_CONTENT",
                    "severity": "WARNING",
                    "source_id": src,
                    "input_ordinals": sorted(list(input_ords)),
                    "details": f"Exact duplicate content found across {len(recs)} chunks",
                    "canonical_chunk_ids": ids
                })

    def _create_chunk(self, content: str, records: List[Dict], level_info: dict, is_long: bool = False):
        if not records:
            return
        base = records[0]
        # Get page range
        pages = [r.get("page_start") for r in records if r.get("page_start") is not None] + \
                [r.get("page_end") for r in records if r.get("page_end") is not None]
        page_start = min(pages) if pages else 0
        page_end = max(pages) if pages else 0

        chunk = {
            "chunker_version": CHUNKER_VERSION,
            "source_id": base.get("source_id"),
            "version_id": base.get("version_id"),
            "chapter": base.get("chapter"),
            "section": base.get("section"),
            "article": base.get("article"),
            "clause": level_info.get("clause"),
            "point": level_info.get("point"),
            "heading_path": base.get("heading_path", []),
            "content": content,
            "page_start": page_start,
            "page_end": page_end,
            "provenance": [{"input_ordinal": r["_input_ordinal"], "content_hash": r["content_hash"]} for r in records],
            "is_long_unsplittable": is_long,
            "is_fragment": level_info.get("is_fragment", False),
            "fragment_index": level_info.get("fragment_index", 0)
        }
        chunk["canonical_chunk_id"] = self.get_deterministic_id(chunk)
        self.chunks.append(chunk)
        
        if is_long:
            self.anomalies.append({
                "anomaly_id": f"long_{chunk['canonical_chunk_id']}",
                "anomaly_type": "LONG_UNSPLITTABLE",
                "severity": "WARNING",
                "source_id": chunk["source_id"],
                "input_ordinals": [r["input_ordinal"] for r in chunk["provenance"]],
                "details": f"Chunk length {len(content)} exceeds hard limit {HARD_LIMIT}"
            })

    def _split_text(self, context: str, piece: str, max_size: int) -> List[str]:
        # Split by paragraph
        paragraphs = piece.split("\n")
        chunks = []
        current_chunk = ""
        for p in paragraphs:
            if not p.strip(): continue
            # Try to add paragraph
            if len(context) + len(current_chunk) + len(p) + 1 <= max_size:
                current_chunk += (p + "\n")
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                if len(context) + len(p) > max_size:
                    # Split by sentence
                    sentences = re.split(r"(?<=\.)\s+", p)
                    for s in sentences:
                        if not s.strip(): continue
                        if len(context) + len(current_chunk) + len(s) + 1 <= max_size:
                            current_chunk += (s + " ")
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = s + " "
                else:
                    current_chunk = p + "\n"
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    def _process_article_group(self, ag_key, recs):
        full_content = "\n".join([r.get("content", "") for r in recs])
        
        if len(full_content) <= TARGET_SIZE:
            # Whole article fits!
            self._create_chunk(full_content, recs, {"clause": None, "point": None})
            return

        # Too big, split by Clause
        # First, gather Article context (clause is None and point is None)
        article_context_recs = [r for r in recs if r.get("clause") is None and r.get("point") is None]
        article_context_text = "\n".join([r.get("content", "") for r in article_context_recs])
        if article_context_text:
            article_context_text += "\n"

        # Gather Clause groups
        clause_groups = {}
        for r in recs:
            if r.get("clause") is not None or r.get("point") is not None:
                ckey = r.get("clause")
                if ckey not in clause_groups:
                    clause_groups[ckey] = []
                clause_groups[ckey].append(r)
        
        # If no clause groups, we just have to split the article context itself
        if not clause_groups:
            self._split_and_emit(article_context_text, article_context_text, article_context_recs, {"clause": None, "point": None})
            return

        for ckey, crecs in clause_groups.items():
            clause_content = "\n".join([r.get("content", "") for r in crecs])
            combined = (article_context_text + clause_content).strip()
            
            if len(combined) <= TARGET_SIZE:
                self._create_chunk(combined, article_context_recs + crecs, {"clause": ckey, "point": None})
            else:
                # Split by point
                clause_context_recs = [r for r in crecs if r.get("point") is None]
                clause_context_text = "\n".join([r.get("content", "") for r in clause_context_recs])
                
                full_context_text = article_context_text
                if clause_context_text:
                    full_context_text += clause_context_text + "\n"
                
                point_recs = [r for r in crecs if r.get("point") is not None]
                if not point_recs:
                    # Clause has no points, split clause text
                    self._split_and_emit(full_context_text, clause_content, article_context_recs + crecs, {"clause": ckey, "point": None})
                    continue
                
                for p_rec in point_recs:
                    pkey = p_rec.get("point")
                    pcontent = p_rec.get("content", "")
                    pcombined = (full_context_text + pcontent).strip()
                    
                    if len(pcombined) <= TARGET_SIZE:
                        self._create_chunk(pcombined, article_context_recs + clause_context_recs + [p_rec], {"clause": ckey, "point": pkey})
                    else:
                        self._split_and_emit(full_context_text, pcontent, article_context_recs + clause_context_recs + [p_rec], {"clause": ckey, "point": pkey})

    def _split_and_emit(self, context: str, text: str, records: List[Dict], level_info: dict):
        splits = self._split_text(context, text, TARGET_SIZE)
        for i, s in enumerate(splits):
            combined = (context + s).strip()
            is_long = len(combined) > HARD_LIMIT
            
            new_level_info = dict(level_info)
            new_level_info["is_fragment"] = True
            new_level_info["fragment_index"] = i + 1
            
            self._create_chunk(combined, records, new_level_info, is_long)
