import sys
import io
import json
import fitz
import os
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r'dichvucong_xay_dung_crawled_2026-07-17/procedures.json', 'r', encoding='utf-8-sig') as f:
    procedures = json.load(f)

# Focus on key GPXD procedures + extract exact form references
key_codes = ['1.013225', '1.013229', '1.013226', '1.013227', '1.013228',
             '1.013236', '1.013238', '1.013231', '1.013233', '1.013235',
             '1.009122', '1.013316', '1.013315']

all_form_refs = {}

for p in procedures:
    if p['Code'] not in key_codes:
        continue
    
    pdf_path = os.path.join('dichvucong_xay_dung_crawled_2026-07-17', p['PdfFile'])
    if not os.path.exists(pdf_path):
        continue
    
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()
    
    # Extract form references with patterns
    patterns = [
        r'[Mm]ẫu\s+(?:số\s+)?[\d]+[a-zA-Z]?\s*(?:Phụ\s+lục|PL)',
        r'[Mm]ẫu\s+(?:số\s+)?[\d]+\s*(?:ban\s+hành|Nghị\s+định)',
        r'Đơn\s+đề\s+nghị.*?(?:theo|Mẫu).*?(?:Nghị\s+định|NĐ|Phụ\s+lục)',
        r'(?:Mẫu|mẫu)\s+(?:số\s+)?(?:0[1-9]|[1-9]\d?)\b',
    ]
    
    form_refs = set()
    for pattern in patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        for m in matches:
            form_refs.add(m.strip()[:100])
    
    all_form_refs[p['Code']] = {
        'name': p['Name'][:150],
        'forms': list(form_refs)
    }

# Print results
print("="*120)
print("TỔNG HỢP MẪU ĐƠN YÊU CẦU TRONG CÁC THỦ TỤC GPXD")
print("="*120)

unique_forms = set()
for code, info in all_form_refs.items():
    print(f"\n[{code}] {info['name'][:120]}")
    if info['forms']:
        for f in sorted(info['forms']):
            print(f"  📋 {f}")
            unique_forms.add(f)
    else:
        print(f"  (không tìm thấy reference mẫu đơn cụ thể)")

print(f"\n\n{'='*120}")
print(f"DANH SÁCH MẪU ĐƠN DUY NHẤT ({len(unique_forms)} mẫu):")
print(f"{'='*120}")
for f in sorted(unique_forms):
    print(f"  📋 {f}")

# Also check what we have in mau_don_to_khai
print(f"\n\n{'='*120}")
print("FILE HIỆN CÓ TRONG mau_don_to_khai/:")
print(f"{'='*120}")
mau_dir = r'dichvucong_xay_dung_crawled_2026-07-17/mau_don_to_khai'
for f in sorted(os.listdir(mau_dir)):
    print(f"  ✅ {f}")
