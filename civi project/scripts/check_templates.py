import sys
import io
import json
import os
import csv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load procedures.json
with open('dichvucong_xay_dung_crawled_2026-07-17/procedures.json', 'r', encoding='utf-8-sig') as f:
    procs = json.load(f)

# Load forms.csv
with open('dichvucong_xay_dung_crawled_2026-07-17/forms.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    forms = list(reader)

local_files = os.listdir('dichvucong_xay_dung_crawled_2026-07-17/mau_don_to_khai')
local_files_lower = [fn.lower() for fn in local_files]

print('Checking key GPXD templates:')
gpxd_procs = ['1.013225', '1.013229', '1.013226', '1.013227', '1.013228', '1.009122']
for code in gpxd_procs:
    proc = next((p for p in procs if p['Code'] == code), None)
    if proc:
        print(f'\n  Code: {code} - {proc["Name"][:80]}...')
        proc_id = proc['Id']
        related_forms = [f for f in forms if f['SourceProcedureId'] == proc_id]
        print(f'  Related forms in forms.csv for this procedure:')
        for rf in related_forms:
            fn = rf['FileName']
            exists = fn.lower() in local_files_lower
            # Find the actual filename case-insensitive
            actual_fn = next((f for f in local_files if f.lower() == fn.lower()), None)
            print(f'    - {fn} (Exists local: {exists} as {actual_fn})')
