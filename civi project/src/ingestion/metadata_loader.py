import os
import json
import csv
from src.config import Config

class MetadataLoader:
    def __init__(self):
        self.data_dir = Config.DATA_DIR
        self.procedures = []
        self.forms = []
        self.phan_loai = []
        
        self.load_all()

    def load_all(self):
        # 1. Load procedures.json
        proc_path = os.path.join(self.data_dir, "procedures.json")
        if os.path.exists(proc_path):
            with open(proc_path, 'r', encoding='utf-8-sig') as f:
                self.procedures = json.load(f)
                
        # 2. Load forms.csv
        forms_path = os.path.join(self.data_dir, "forms.csv")
        if os.path.exists(forms_path):
            with open(forms_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                self.forms = list(reader)

        # 3. Load phan_loai_tthc.json
        pl_path = "src/data/phan_loai_tthc.json"
        if os.path.exists(pl_path):
            with open(pl_path, 'r', encoding='utf-8') as f:
                self.phan_loai = json.load(f)

    def get_procedure_by_code(self, code):
        """Find procedure details by code (e.g. 1.013225)"""
        # Find in procedures.json
        proc = next((p for p in self.procedures if p.get("Code") == code), None)
        # Find in phan_loai
        pl = next((p for p in self.phan_loai if p.get("Mã số") == code), {})
        
        if not proc and not pl:
            return None
            
        result = {}
        if proc:
            result.update({
                "id": proc.get("Id"),
                "code": proc.get("Code"),
                "name": proc.get("Name"),
                "pdf_file": proc.get("PdfFile")
            })
        if pl:
            result.update({
                "name": result.get("name") or pl.get("Tên"),
                "code": result.get("code") or pl.get("Mã số"),
                "nhom_de_muc": pl.get("Nhóm đề mục"),
                "linh_vuc": pl.get("Lĩnh vực chuẩn hóa"),
                "loai_yeu_cau": pl.get("Loại yêu cầu"),
                "tinh_huong": pl.get("Tình huống/đối tượng hồ sơ"),
                "dia_phuong": pl.get("Địa phương"),
                "co_quan_thuc_hien": pl.get("Cơ quan thực hiện"),
                "cap_thuc_hien": pl.get("Cấp thực hiện")
            })
        return result

    def get_forms_for_procedure(self, proc_id_or_code):
        """
        Find related DOCX/DOC files for a procedure.
        It searches forms.csv using SourceProcedureId.
        It also handles standard fallbacks:
        - If code is 1.013225, search forms that are building permits.
        """
        # First try to find by ID
        proc = next((p for p in self.procedures if p.get("Code") == proc_id_or_code or p.get("Id") == proc_id_or_code), None)
        
        related = []
        if proc:
            proc_id = proc.get("Id")
            related = [f for f in self.forms if f.get("SourceProcedureId") == proc_id]
            
        # Fallbacks for Case 1 (GPXD nhà ở riêng lẻ)
        # In Kich ban 1, the GPXD uses 'Don2.docx' which represents the building permit form
        if proc_id_or_code in ["1.013225", "1.009122"] or (proc and "cấp giấy phép xây dựng" in proc.get("Name", "").lower()):
            # Check if Don2.docx or DDNCapGPXD.docx is present local and add it
            local_files = os.listdir(os.path.join(self.data_dir, "mau_don_to_khai"))
            for f in local_files:
                if f.lower() in ["don2.docx", "ddncapgpxd.docx", "ddncapgpxd (1).docx"]:
                    # Create a mock form mapping
                    related.append({
                        "FileName": f,
                        "ComponentName": "Đơn đề nghị cấp giấy phép xây dựng theo mẫu hiện hành",
                        "Downloaded": "True",
                        "LocalFile": f
                    })
        
        # Fallbacks for Case 2 (Đăng ký biến động đất đai)
        if proc_id_or_code in ["1.115729", "1.115722", "1.115719"] or (proc and "đăng ký biến động" in proc.get("Name", "").lower()):
            local_files = os.listdir(os.path.join(self.data_dir, "mau_don_to_khai"))
            for f in local_files:
                if "18_73_2026" in f.lower() or "đơn biến động đất đai" in f.lower():
                    related.append({
                        "FileName": f,
                        "ComponentName": "Đơn đăng ký biến động đất đai, tài sản gắn liền với đất",
                        "Downloaded": "True",
                        "LocalFile": f
                    })
                    
        # Remove duplicates
        seen = set()
        unique_related = []
        for r in related:
            fn = r.get("FileName")
            if fn not in seen:
                seen.add(fn)
                unique_related.append(r)
                
        return unique_related
