import sys
import io
import os
from src.ingestion.pdf_processor import PDFProcessor

# Set UTF-8 output on Windows
if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure scratch directory exists
os.makedirs("scratch", exist_ok=True)

print("Starting test PDF conversion...")
processor = PDFProcessor()

pdf_path = "dichvucong_xay_dung_crawled_2026-07-17/pdf_thu_tuc/144_1.013227.pdf" # Gia han GPXD
if not os.path.exists(pdf_path):
    # Try another one
    pdf_path = "dichvucong_xay_dung_crawled_2026-07-17/pdf_thu_tuc/088_1.009122.pdf"

print(f"Reading: {pdf_path}")
try:
    content = processor.extract_text_and_tables(pdf_path)
    
    # Save the output to scratch/extracted_test.md
    with open("scratch/extracted_test.md", "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Extraction successful! Saved to scratch/extracted_test.md")
    print("\n--- FIRST 1000 CHARACTERS ---")
    print(content[:1000])
    print("-----------------------------")
    
    # Look for table markers like '|'
    if "|" in content:
        print("🎉 Success! Found markdown table markers ('|') in the extracted text.")
    else:
        print("⚠️ Warning: No markdown table markers ('|') found. Check the output file to verify.")
        
except Exception as e:
    print(f"Error: {e}")
