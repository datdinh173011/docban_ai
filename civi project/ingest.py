import os
import json
import time
from src.config import Config
from src.ingestion.pdf_processor import PDFProcessor
from src.ingestion.vectorstore import VectorStoreManager

def main():
    import sys
    import io
    if sys.platform.startswith("win"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
    # Open local ingest.log file for real-time progress monitoring
    log_file = open("ingest.log", "w", encoding="utf-8")
    
    def log_print(msg):
        print(msg)
        log_file.write(str(msg) + "\n")
        log_file.flush()
        
    log_print("==========================================================")
    log_print("Ingestion Pipeline: Indexing PDFs to ChromaDB")
    log_print("==========================================================")
    
    # 1. Initialize services
    processor = PDFProcessor()
    vectorstore = VectorStoreManager()
    
    # 2. Load procedures list
    procedures_path = os.path.join(Config.DATA_DIR, "procedures.json")
    if not os.path.exists(procedures_path):
        log_print(f"Error: {procedures_path} not found.")
        return
        
    with open(procedures_path, 'r', encoding='utf-8-sig') as f:
        procedures = json.load(f)
        
    log_print(f"Loaded {len(procedures)} procedures from procedures.json")
    
    # 2.5 Load phan_loai_tthc.json for rich metadata mapping
    phan_loai_path = "src/data/phan_loai_tthc.json"
    phan_loai_map = {}
    if os.path.exists(phan_loai_path):
        with open(phan_loai_path, 'r', encoding='utf-8') as f:
            pl_list = json.load(f)
            for item in pl_list:
                code_key = item.get("Mã số")
                if code_key:
                    phan_loai_map[code_key] = item
        log_print(f"Loaded {len(phan_loai_map)} enrichment mappings from phan_loai_tthc.json")
    else:
        log_print("[Warning] phan_loai_tthc.json not found. Chunks will only have basic metadata.")

    # We will process each PDF
    start_time = time.time()
    indexed_count = 0
    
    # To keep the demo fast, let's prioritize indexing the key GPXD procedures first, 
    # but we will loop through all of them.
    # Key GPXD codes:
    key_codes = ['1.013225', '1.013229', '1.013226', '1.013227', '1.013228', '1.009122']
    
    # Sort procedures so key ones are indexed first
    procedures.sort(key=lambda p: 0 if p.get("Code") in key_codes else 1)
    
    for idx, proc in enumerate(procedures, 1):
        code = proc.get("Code")
        name = proc.get("Name")
        pdf_rel_path = proc.get("PdfFile")
        
        pdf_path = os.path.join(Config.DATA_DIR, pdf_rel_path)
        if not os.path.exists(pdf_path):
            log_print(f"[{idx}/{len(procedures)}] File not found: {pdf_path}. Skipping.")
            continue
            
        log_print(f"[{idx}/{len(procedures)}] Processing {code}: {name[:60]}...")
        
        # Prepare rich metadata from Excel data sheet mapping
        enrich_meta = phan_loai_map.get(code, {})
        base_metadata = {
            "code": code,
            "title": name,
            "nhom_de_muc": enrich_meta.get("Nhóm đề mục", ""),
            "linh_vuc": enrich_meta.get("Lĩnh vực chuẩn hóa", ""),
            "loai_yeu_cau": enrich_meta.get("Loại yêu cầu", ""),
            "tinh_huong": enrich_meta.get("Tình huống/đối tượng hồ sơ", ""),
            "dia_phuong": enrich_meta.get("Địa phương", ""),
            "doi_tuong_nguoidung": enrich_meta.get("Đối tượng người dùng", ""),
            "co_quan_thuc_hien": enrich_meta.get("Cơ quan thực hiện", ""),
            "cap_thuc_hien": enrich_meta.get("Cấp thực hiện", "")
        }
        
        try:
            # 1. Extract content from PDF (Docling markdown with tables)
            content = processor.extract_text_and_tables(pdf_path)
            
            # 2. Segment text into sections
            sections = processor.extract_sections(content)
            
            # 3. Create document chunks
            chunks = []
            for sec_name, sec_text in sections.items():
                if not sec_text:
                    continue
                # Split large sections into smaller chunks if necessary (e.g. max 1500 chars)
                max_chunk_len = 1500
                sec_chunks = [sec_text[i:i+max_chunk_len] for i in range(0, len(sec_text), max_chunk_len)]
                
                for c_idx, text_chunk in enumerate(sec_chunks):
                    # Clone metadata and add section name
                    chunk_meta = base_metadata.copy()
                    chunk_meta["section"] = sec_name
                    
                    chunks.append({
                        "id": f"{code}_{sec_name}_{c_idx}",
                        "text": text_chunk,
                        "metadata": chunk_meta
                    })
            
            # 4. Save chunks to ChromaDB vector store
            if chunks:
                vectorstore.add_documents(chunks)
                indexed_count += 1
                
        except Exception as e:
            log_print(f"Error processing {code}: {e}")
            
        # Fast exit for indexing only the top 15 procedures during quick setup, 
        # but allow user to run fully.
        # For full run: we keep indexing.
        # To make it responsive, let's limit it to 20 procedures for the first quick test run
        # if the user runs it in a fast mode. But let's index all by default.
        
    log_print("==========================================================")
    log_print(f"Ingestion complete. Indexed {indexed_count} procedures.")
    log_print(f"Total time elapsed: {time.time() - start_time:.2f} seconds")
    log_print("==========================================================")
    log_file.close()

if __name__ == "__main__":
    main()
