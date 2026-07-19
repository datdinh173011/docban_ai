import io
from pathlib import Path

import pdfplumber
import pytest
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics

from app import form_export
from app.procedure_settings import load_procedure_settings

SETTINGS = load_procedure_settings()
BIRTH_FORM = SETTINGS.form_candidates["BIRTH_REGISTRATION_FORM"]
CONSTRUCTION_FORM = SETTINGS.form_candidates["CONSTRUCTION_PERMIT_REQUEST_FORM"]
WRAP_CASES = (
    ("BIRTH_REGISTRATION_FORM", "child_full_name", "Nguyễn Thị Minh Anh Phương Mai An Nhiên Hoàng Bảo Ngọc Khánh Linh"),
    ("PERMANENT_RESIDENCE_CT01_FORM", "residence_request", "Đăng ký thường trú tại căn hộ số 1208, tòa nhà A, phường Minh Khai, quận Bắc Từ Liêm, thành phố Hà Nội"),
)

# A Vietnamese-diacritic-capable TTF is not vendored in the repo (licensing) — the
# deployed container gets one via `fonts-noto-core` (see Dockerfile). For portable
# local test runs, fall back to whatever Unicode-complete font the dev machine or CI
# image happens to provide, skipping the render tests entirely if none is found.
_DEV_FALLBACK_FONTS = (
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
)


def _available_font() -> Path | None:
    return next((path for path in _DEV_FALLBACK_FONTS if path.is_file()), None)


@pytest.fixture(autouse=True)
def reset_font_registration(monkeypatch):
    monkeypatch.setattr(form_export, "_registered", False)
    yield
    form_export._registered = False


def test_missing_font_raises_export_error(monkeypatch) -> None:
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", ())
    monkeypatch.setattr(form_export, "_fontconfig_match", lambda: None)
    with pytest.raises(form_export.ExportError) as exc_info:
        form_export.render_export(BIRTH_FORM, {"child_full_name": "Nguyễn Văn A"})
    assert exc_info.value.reason == "vietnamese_font_missing"


def test_render_export_produces_valid_pdf_with_vietnamese_text(monkeypatch) -> None:
    font_path = _available_font()
    if font_path is None:
        pytest.skip("no Unicode-complete TTF available on this machine to exercise the real render path")
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", (font_path,))
    values = {
        "child_full_name": "Nguyễn Thị Hồng Ánh",
        "child_gender": "Nữ",
        "mother_full_name": "Trần Thị Bích",
    }
    pdf_bytes = form_export.render_export(BIRTH_FORM, values)
    reader = PdfReader(__import__("io").BytesIO(pdf_bytes))
    assert len(reader.pages) == 2


def test_overflowing_value_raises_export_error_not_corrupted_pdf(monkeypatch) -> None:
    font_path = _available_font()
    if font_path is None:
        pytest.skip("no Unicode-complete TTF available on this machine to exercise the real render path")
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", (font_path,))
    too_long = "Nguyễn " * 200
    with pytest.raises(form_export.ExportError) as exc_info:
        form_export.render_export(BIRTH_FORM, {"child_full_name": too_long})
    assert exc_info.value.reason == "text_exceeds_field_width"


@pytest.mark.parametrize(("form_code", "field_code", "value"), WRAP_CASES)
def test_long_text_wraps_within_the_configured_pdf_region(monkeypatch, form_code: str, field_code: str, value: str) -> None:
    font_path = _available_font()
    if font_path is None:
        pytest.skip("no Unicode-complete TTF available on this machine to exercise the real render path")
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", (font_path,))
    candidate = SETTINGS.form_candidates[form_code]
    field = candidate.field_by_code(field_code)
    assert field and field.export and field.export.overflow_policy == "wrap"

    form_export._ensure_font_registered()
    lines, font_size = form_export._fit_lines(value, field)
    assert 1 < len(lines) <= field.export.max_lines
    assert field.export.min_font_size <= font_size <= field.export.font_size

    pdf_bytes = form_export.render_export(candidate, {field_code: value})
    assert len(PdfReader(__import__("io").BytesIO(pdf_bytes)).pages) > 0


def test_single_line_field_truncates_overflow_for_print_layout(monkeypatch) -> None:
    font_path = _available_font()
    if font_path is None:
        pytest.skip("no Unicode-complete TTF available on this machine to exercise the real render path")
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", (font_path,))
    field = BIRTH_FORM.field_by_code("applicant_id_document")
    assert field and field.export and field.export.overflow_policy == "reject"
    form_export._ensure_font_registered()
    lines, font_size = form_export._fit_lines("1" * 80, field)
    assert lines[0].endswith("…")
    assert len(lines[0]) < 80
    assert pdfmetrics.stringWidth(lines[0], form_export._FONT_BOLD_NAME, font_size) <= field.export.width


def test_construction_address_prefers_truncation_over_wrapping(monkeypatch) -> None:
    font_path = _available_font()
    if font_path is None:
        pytest.skip("no Unicode-complete TTF available on this machine to exercise the real render path")
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", (font_path,))
    field = CONSTRUCTION_FORM.field_by_code("construction_address")
    assert field and field.export and field.export.truncate_overflow

    form_export._ensure_font_registered()
    value = "Thửa đất số 123, tờ bản đồ số 45, đường Nguyễn Văn Linh, phường Tân Phong, quận 7, Thành phố Hồ Chí Minh"
    lines, font_size = form_export._fit_lines(value, field)
    assert len(lines) == 1
    assert lines[0].endswith("…")
    assert pdfmetrics.stringWidth(lines[0], form_export._FONT_BOLD_NAME, font_size) <= field.export.width


def test_machine_filled_text_uses_bold_font(monkeypatch) -> None:
    font_path = _available_font()
    if font_path is None:
        pytest.skip("no Unicode-complete TTF available on this machine to exercise the real render path")
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", (font_path,))

    with pdfplumber.open(io.BytesIO(form_export.render_export(CONSTRUCTION_FORM, {"phone_number": "0912345678"}))) as pdf:
        rendered_digits = [
            char for char in pdf.pages[0].chars
            if char["text"].isdigit() and 155 <= char["x0"] <= 462 and 285 <= char["top"] <= 303
        ]
        assert rendered_digits
        assert all("Bold" in char["fontname"] for char in rendered_digits)


def _assert_word_in_region(page, value: str, region: tuple[float, float, float, float]) -> None:
    matches = [word for word in page.extract_words() if word["text"] == value]
    assert len(matches) == 1, f"expected one {value!r}, got {matches}"
    word = matches[0]
    x0, x1, top, bottom = region
    assert x0 <= word["x0"] < word["x1"] <= x1
    assert top <= word["top"] < word["bottom"] <= bottom


def test_numeric_values_render_inside_official_form_blanks(monkeypatch) -> None:
    font_path = _available_font()
    if font_path is None:
        pytest.skip("no Unicode-complete TTF available on this machine to exercise the real render path")
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", (font_path,))
    values = {
        "land_area": 123.45,
        "first_floor_area": 98.76,
        "total_floor_area": 350.5,
        "floor_count": 12,
        "estimated_completion_months": 24,
    }

    with pdfplumber.open(io.BytesIO(form_export.render_export(CONSTRUCTION_FORM, values))) as pdf:
        _assert_word_in_region(pdf.pages[0], "123.45", (311.8, 358.0, 348.0, 365.0))
        _assert_word_in_region(pdf.pages[1], "98.76", (276.5, 316.0, 544.0, 561.0))
        _assert_word_in_region(pdf.pages[1], "350.5", (158.7, 225.1, 565.0, 582.0))
        _assert_word_in_region(pdf.pages[1], "12", (122.6, 145.0, 638.0, 654.0))
        _assert_word_in_region(pdf.pages[3], "24", (300.4, 436.9, 114.0, 131.0))


def test_birth_copy_count_renders_on_first_page(monkeypatch) -> None:
    font_path = _available_font()
    if font_path is None:
        pytest.skip("no Unicode-complete TTF available on this machine to exercise the real render path")
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", (font_path,))

    with pdfplumber.open(io.BytesIO(form_export.render_export(BIRTH_FORM, {"copy_count": 7}))) as pdf:
        matches = [
            char for char in pdf.pages[0].chars
            if char["text"] == "7" and 114.2 <= char["x0"] <= 139.0 and abs(char["size"] - 9) < 0.01
        ]
        assert len(matches) == 1
        char = matches[0]
        assert 114.2 <= char["x0"] < char["x1"] <= 139.0
        assert 805.0 <= char["top"] < char["bottom"] <= 821.0
        assert not any(word["text"] == "7" for word in pdf.pages[1].extract_words())
