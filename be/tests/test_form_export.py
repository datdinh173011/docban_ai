from pathlib import Path

import pytest
from pypdf import PdfReader

from app import form_export
from app.procedure_settings import load_procedure_settings

SETTINGS = load_procedure_settings()
BIRTH_FORM = SETTINGS.form_candidates["BIRTH_REGISTRATION_FORM"]

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
