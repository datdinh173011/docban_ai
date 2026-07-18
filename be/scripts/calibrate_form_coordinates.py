"""Dev-only helper: locate label phrases in a source form PDF and emit a first-pass
export coordinate mapping (page/x/y) for each field, to be pasted into
`app/settings/form_guidance.json` and visually calibrated by hand.

This is NOT part of the runtime package (see be/app/form_export.py) and requires the
dev-only `pdfplumber` dependency. Usage:

    uv run python scripts/calibrate_form_coordinates.py birth_registration
    uv run python scripts/calibrate_form_coordinates.py ct01
    uv run python scripts/calibrate_form_coordinates.py construction_permit
"""

import json
import sys
from pathlib import Path

import pdfplumber

ASSETS_DIR = Path(__file__).resolve().parents[1] / "app" / "assets" / "form_templates"

# (field_code, page_no, label_phrase_to_search_for, value_placement, occurrence_index)
# value_placement: "after" places the value immediately to the right of the label on
# the same line; "below" places it on the next line at the label's left margin.
# occurrence_index: 0-based index into repeated identical labels on the same page
# (e.g. "Nơi cư trú:" appears once for the applicant, once for the mother, once for
# the father — index 0/1/2 respectively).
FIELD_LABELS: dict[str, list[tuple[str, int, str, str, int]]] = {
    "birth_registration": [
        ("applicant_full_name", 1, "Họ, chữ đệm, tên người yêu cầu:", "after", 0),
        ("applicant_birth_date", 1, "Ngày, tháng, năm sinh:", "after", 0),
        ("applicant_residence", 1, "Nơi cư trú:", "after", 0),
        ("applicant_id_document", 1, "Giấy tờ tùy thân:", "after", 0),
        ("relationship_to_child", 1, "Quan hệ với người được khai sinh:", "after", 0),
        ("child_full_name", 1, "Họ, chữ đệm, tên:", "after", 0),
        ("child_birth_date", 1, "Ngày, tháng, năm sinh:", "after", 1),
        ("child_gender", 1, "Giới tính:", "after", 0),
        ("child_ethnicity", 1, "Dân tộc:", "after", 0),
        ("child_nationality", 1, "Quốc tịch:", "after", 0),
        ("child_birth_place", 1, "Nơi sinh:", "after", 0),
        ("child_hometown", 1, "Quê quán:", "after", 0),
        ("mother_full_name", 1, "Họ, chữ đệm, tên người mẹ:", "after", 0),
        ("mother_birth_year", 1, "Năm sinh:", "after", 0),
        ("mother_ethnicity", 1, "Dân tộc:", "after", 1),
        ("mother_nationality", 1, "Quốc tịch:", "after", 1),
        ("mother_residence", 1, "Nơi cư trú:", "after", 1),
        ("mother_id_document", 1, "Giấy tờ tùy thân:", "after", 1),
        ("father_full_name", 1, "Họ, chữ đệm, tên người cha:", "after", 0),
        ("father_birth_year", 1, "Năm sinh:", "after", 1),
        ("father_ethnicity", 1, "Dân tộc:", "after", 2),
        ("father_nationality", 1, "Quốc tịch:", "after", 2),
        ("father_residence", 1, "Nơi cư trú:", "after", 2),
        ("father_id_document", 1, "Giấy tờ tùy thân:", "after", 2),
    ],
    "ct01": [
        ("recipient_authority", 1, "Kính gửi", "after", 0),
        ("applicant_full_name", 1, "Họ, chữ đệm và tên khai sinh:", "after", 0),
        ("applicant_birth_date", 1, "Ngày, tháng, năm sinh:", "after", 0),
        ("applicant_gender", 1, "Giới tính:", "after", 0),
        ("citizen_id", 1, "Số định danh cá nhân:", "after", 0),
        ("applicant_phone", 1, "Số điện thoại liên hệ:", "after", 0),
        ("applicant_email", 1, "Email:", "after", 0),
        ("household_head_name", 1, "Họ, chữ đệm và tên chủ hộ", "after", 0),
        ("relationship_to_household_head", 1, "Mối quan hệ với chủ hộ:", "after", 0),
        ("household_head_citizen_id", 1, "Số định danh cá nhân của chủ hộ:", "after", 0),
        ("residence_request", 1, "Nội dung đề nghị", "below", 0),
    ],
    "construction_permit": [
        ("recipient_authority", 1, "Kính gửi:", "after", 0),
        ("owner_name", 1, "Tên chủ đầu tư", "after", 0),
        ("owner_citizen_id", 1, "Số định danh cá nhân/Mã số doanh nghiệp:", "after", 0),
        ("representative_name", 1, "Người đại diện:", "after", 0),
        ("representative_title", 1, "Chức vụ:", "after", 0),
        ("representative_citizen_id", 1, "Số định danh cá nhân:", "after", 0),
        ("phone_number", 1, "Số điện thoại:", "after", 0),
        ("land_plot_number", 1, "Lô đất số:", "after", 0),
        ("land_area", 1, "Diện tích", "after", 0),
        ("design_org_name", 1, "Tên tổ chức/cá nhân:", "after", 0),
        ("design_org_license_number", 1, "Mã số chứng chỉ năng lực/hành nghề:", "after", 0),
        ("review_org_name", 1, "Tên tổ chức/cá nhân:", "after", 1),
        ("review_org_license_number", 1, "Mã số chứng chỉ năng lực/hành nghề:", "after", 1),
        # Page 2 repeats "Cấp công trình/Cốt xây dựng/..." once per building-type
        # subsection (4.2 theo tuyến, 4.3 tượng đài, 4.4 nhà ở riêng lẻ, 4.5 cải tạo);
        # occurrence index 2 selects the 4.4 "nhà ở riêng lẻ" subsection, which is the
        # only one this app scopes to (see plan: ignore 4.1/4.2/4.3/4.5-4.8).
        ("building_grade", 2, "Cấp công trình:", "after", 2),
        ("construction_elevation", 2, "Cốt xây dựng:", "after", 2),
        ("setback_distance", 2, "Khoảng lùi", "after", 1),
        ("first_floor_area", 2, "Diện tích xây dựng tầng 1", "after", 0),
        # Unlike the other page-2 subsection labels, "Tổng diện tích sàn:" (with the
        # colon immediately after) only matches the 4.4 occurrence — the 4.1 occurrence
        # is followed by "(đối với...)" instead of a colon, so occurrence 0 is correct here.
        ("total_floor_area", 2, "Tổng diện tích sàn:", "after", 0),
        ("building_height", 2, "Chiều cao công trình:", "after", 2),
        ("floor_count", 2, "Số tầng:", "after", 1),
        ("estimated_completion_months", 4, "Dự kiến thời gian hoàn thành công trình:", "after", 0),
    ],
}

FORM_FILES = {
    "birth_registration": "01_to_khai_dang_ky_khai_sinh.pdf",
    "ct01": "02_mau_CT01_TT116_2026.pdf",
    "construction_permit": "03_don_de_nghi_cap_gpxd_nha_o_rieng_le.pdf",
}


def calibrate(form_key: str) -> list[dict]:
    pdf_path = ASSETS_DIR / FORM_FILES[form_key]
    results: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        for field_code, page_no, label, placement, occurrence in FIELD_LABELS[form_key]:
            page = pdf.pages[page_no - 1]
            matches = page.search(label)
            if len(matches) <= occurrence:
                results.append({"field_code": field_code, "page": page_no, "error": f"label_not_found:{label!r}[{occurrence}] (found {len(matches)})"})
                continue
            match = matches[occurrence]
            page_height = float(page.height)
            if placement == "after":
                x = round(match["x1"] + 4, 1)
                y = round(page_height - match["bottom"] + 2, 1)
                width = round(float(page.width) - 56 - x, 1)
            else:
                x = round(match["x0"], 1)
                y = round(page_height - match["bottom"] - 12, 1)
                width = round(float(page.width) - 56 - x, 1)
            results.append({
                "field_code": field_code,
                "page": page_no,
                "x": x,
                "y": y,
                "width": max(width, 60.0),
                "height": 14,
                "font_family": "NotoSans",
                "font_size": 10,
                "align": "left",
                "format": "text",
                "overflow_policy": "reject",
            })
    return results


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else None
    if key not in FIELD_LABELS:
        print(f"usage: calibrate_form_coordinates.py <{'|'.join(FIELD_LABELS)}>", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(calibrate(key), ensure_ascii=False, indent=2))
