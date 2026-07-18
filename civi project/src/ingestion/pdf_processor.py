import os
import re

# We will try to import docling. If not available, we fall back to a simple PyMuPDF/fitz processor.
# This ensures that the code runs even if there is a library installation issue in the user environment.
try:
    from docling.document_converter import DocumentConverter
    HAS_DOCLING = True
except ImportError:
    HAS_DOCLING = False
    import fitz  # PyMuPDF fallback

class PDFProcessor:
    def __init__(self):
        if HAS_DOCLING:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
            
            # Disable OCR for native PDFs to dramatically speed up ingestion
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = False
            
            self.converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        else:
            self.converter = None
            print("[Warning] Docling is not installed. Falling back to PyMuPDF (fitz) for PDF extraction.")

    def extract_text_and_tables(self, pdf_path):
        """
        Extract content from PDF. If Docling is installed, it extracts in Markdown format
        which preserves tables. If not, it uses PyMuPDF as fallback.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        if HAS_DOCLING:
            try:
                # Convert using Docling to preserve table formats
                result = self.converter.convert(pdf_path)
                # Export to markdown
                markdown_content = result.document.export_to_markdown()
                return markdown_content
            except Exception as e:
                print(f"[Error] Docling failed to process {pdf_path}: {e}. Falling back to PyMuPDF.")
                # Fall through to fitz
        
        # PyMuPDF Fallback
        text_content = []
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text_content.append(page.get_text())
        doc.close()
        return "\n\n".join(text_content)

    def extract_sections(self, content):
        """
        Split the extracted document content into logical sections for granular RAG retrieval.
        Specifically, we look for key administrative sections:
        - Trình tự thực hiện (Execution sequence)
        - Cách thức thực hiện (Execution method)
        - Thành phần hồ sơ (Required documents)
        - Lệ phí/Thời hạn (Fees / Processing time)
        """
        sections = {
            "trinh_tu": "",
            "cach_thuc": "",
            "ho_so": "",
            "le_phi_thoi_han": "",
            "general": ""
        }
        
        # Simple regex splitting to locate headings
        # Since Docling output is Markdown, headings will start with #, ## or ###.
        # Standard PDF might just have text.
        lines = content.split('\n')
        current_section = "general"
        section_lines = {k: [] for k in sections.keys()}
        
        for line in lines:
            line_lower = line.lower().strip()
            # Detect section switches
            if "trình tự" in line_lower and ("thực hiện" in line_lower or "bước" in line_lower):
                current_section = "trinh_tu"
            elif "cách thức" in line_lower and "thực hiện" in line_lower:
                current_section = "cach_thuc"
            elif "thành phần" in line_lower and ("hồ sơ" in line_lower or "giấy tờ" in line_lower):
                current_section = "ho_so"
            elif "thời hạn" in line_lower or "lệ phí" in line_lower or "phí" in line_lower:
                if current_section in ["ho_so", "general", "trinh_tu"]:
                    current_section = "le_phi_thoi_han"
            
            section_lines[current_section].append(line)
            
        for k in sections.keys():
            sections[k] = "\n".join(section_lines[k]).strip()
            
        return sections
