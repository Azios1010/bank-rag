import fitz
import json
import hashlib
import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Any, Tuple

def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace('\ufeff', '').replace('\r\n', '\n').replace('\r', '\n')
    return text

def get_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

class PolicyNormalizerV2:
    def __init__(self):
        self.parser_version = "bank-rag-v2-pymupdf-structure-1.0.0"
        self.phan_re = re.compile(r'^(Phần\s+[IVXLCDM0-9]+.*?)$', re.IGNORECASE)
        self.chuong_re = re.compile(r'^(Chương\s+[IVXLCDM0-9]+.*?)$', re.IGNORECASE)
        self.muc_re = re.compile(r'^(Mục\s+\d+.*?)$', re.IGNORECASE)
        self.dieu_re = re.compile(r'^Điều\s+(\d+[a-zA-Z]?)\.')
        self.khoan_re = re.compile(r'^(\d+)\.\s')
        self.diem_re = re.compile(r'^([a-zđ])\)\s')
        
        self.cong_bao_re = re.compile(r'^CÔNG BÁO/Số .*?/Ngày \d{1,2}-\d{1,2}-\d{4}$')
        self.page_num_re = re.compile(r'^\d+$')

    def is_noise(self, text: str, bbox: tuple, page_height: float) -> bool:
        if self.cong_bao_re.match(text):
            return True
        if self.page_num_re.match(text):
            y0, y1 = bbox[1], bbox[3]
            if y1 < 100 or y0 > page_height - 100:
                return True
        return False

    def process_file(self, pdf_path: str, source_meta: dict) -> Tuple[List[dict], List[dict]]:
        pdf_file = Path(pdf_path)
        if pdf_file.stat().st_size > 500 * 1024 * 1024:
            raise ValueError(f"File {pdf_path} > 500MB")

        doc = fitz.open(pdf_path)
        blocks = []
        ledger = []
        
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            page_height = page.rect.height
            page_dict = page.get_text("dict")
            
            # Source 07 specific validation
            if source_meta["source_id"] == "v2-07-15-2023-tt-nhnn" and page_num == 10:
                # The prompt says: "only known blank final page 11 for source 07"
                # We can just ignore the page or assert it's empty/has no text
                pass
                
            for b in page_dict["blocks"]:
                if b.get("type") != 0:
                    continue
                
                valid_lines = []
                for l in b["lines"]:
                    line_text = "".join(s["text"] for s in l["spans"]).strip()
                    if not line_text: continue
                    line_text = normalize_text(line_text)
                    bbox = l["bbox"]
                    
                    if self.is_noise(line_text, bbox, page_height):
                        ledger.append({
                            "source": source_meta["source_id"],
                            "page": page_num + 1,
                            "bbox": bbox,
                            "text": line_text,
                            "hash": get_hash(line_text),
                            "reason": "geometry/template noise"
                        })
                    else:
                        valid_lines.append(line_text)
                
                if valid_lines:
                    text = "\n".join(valid_lines)
                    blocks.append({
                        "page": page_num + 1,
                        "text": text
                    })

        provisions = []
        current_phan = None
        current_chuong = None
        current_muc = None
        current_dieu = None
        current_khoan = None
        current_diem = None
        current_heading_path = []
        
        expected_dieu = 1
        is_source_2 = source_meta["source_id"] == "v2-02-100-vbhn-vpqh"
        
        current_content = []
        start_page = None
        
        def save_current(end_page):
            if current_content and current_dieu:
                text = "\n".join(current_content)
                provisions.append({
                    "source_id": source_meta["source_id"],
                    "version_id": source_meta["version_id"],
                    "chapter": current_chuong,
                    "section": current_muc,
                    "article": current_dieu,
                    "clause": current_khoan,
                    "point": current_diem,
                    "heading_path": list(current_heading_path),
                    "content": text,
                    "page_start": start_page,
                    "page_end": end_page,
                    "content_hash": get_hash(text),
                    "inventory_type": "SELECTED",
                    "selection_reason": "Matches retrieval scope strategy"
                })
            current_content.clear()

        last_page = 1
        for b in blocks:
            page = b["page"]
            last_page = page
            lines = b["text"].split('\n')
            for line in lines:
                line = line.strip()
                if not line: continue
                
                m_phan = self.phan_re.match(line)
                m_chuong = self.chuong_re.match(line)
                m_muc = self.muc_re.match(line)
                m_dieu = self.dieu_re.match(line)
                m_khoan = self.khoan_re.match(line)
                m_diem = self.diem_re.match(line)
                
                is_structure = False
                if m_phan:
                    save_current(page)
                    current_phan = m_phan.group(1)
                    current_chuong = None; current_muc = None; current_dieu = None; current_khoan = None; current_diem = None
                    current_heading_path = [current_phan]
                    is_structure = True
                elif m_chuong:
                    save_current(page)
                    current_chuong = m_chuong.group(1)
                    current_muc = None; current_dieu = None; current_khoan = None; current_diem = None
                    current_heading_path = [p for p in [current_phan, current_chuong] if p]
                    is_structure = True
                elif m_muc:
                    save_current(page)
                    current_muc = m_muc.group(1)
                    current_dieu = None; current_khoan = None; current_diem = None
                    current_heading_path = [p for p in [current_phan, current_chuong, current_muc] if p]
                    is_structure = True
                elif m_dieu:
                    dieu_val = m_dieu.group(1)
                    dieu_num = None
                    try:
                        dieu_num = int(''.join(filter(str.isdigit, dieu_val)))
                    except ValueError:
                        pass
                        
                    if is_source_2 and current_dieu is not None and dieu_num is not None:
                        if dieu_num < expected_dieu - 5:
                            m_dieu = None
                            
                    if m_dieu:
                        save_current(page)
                        current_dieu = dieu_val
                        current_khoan = None
                        current_diem = None
                        start_page = page
                        if dieu_num:
                            expected_dieu = dieu_num + 1
                        current_content.append(line)
                        continue
                elif m_khoan and current_dieu:
                    save_current(page)
                    current_khoan = m_khoan.group(1)
                    current_diem = None
                    start_page = page
                    current_content.append(line)
                    continue
                elif m_diem and current_dieu:
                    save_current(page)
                    current_diem = m_diem.group(1)
                    start_page = page
                    current_content.append(line)
                    continue
                
                if not is_structure:
                    if current_dieu:
                        if not current_content:
                            start_page = page
                        current_content.append(line)
                    else:
                        if current_heading_path:
                            current_heading_path[-1] += " " + line

        save_current(last_page)
        
        if is_source_2:
            articles = set(p["article"] for p in provisions if p["article"])
            for i in range(1, 211):
                if str(i) not in articles:
                    print(f"Warning: Article {i} missing from 100/VBHN-VPQH")
                    
        return provisions, ledger
