"""Render a filled form draft as a PDF overlay on the original source template.

No LLM, no database. Everything happens in memory (`io.BytesIO`) — nothing is
written to disk. `overflow_policy` is always "reject" (see `docs/02-schema.md`
§7.3): if a value does not fit its mapped box, this module raises `ExportError`
rather than silently truncating or shrinking the font.
"""

import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.procedure_settings import FormCandidate, FormField

TEMPLATES_DIR = Path(__file__).resolve().with_name("assets") / "form_templates"

# Search order: a repo-bundled font (developer-provided) first, then the path the
# Debian `fonts-noto-core` package installs to (see be/Dockerfile), which is what
# the deployed container actually uses. ReportLab's own bundled fonts (Vera/Helvetica)
# lack Vietnamese diacritic glyphs and must never be used for this renderer.
_FONT_NAME = "NotoSans"
_FONT_CANDIDATES = (
    Path(__file__).resolve().with_name("assets") / "fonts" / "NotoSans-Regular.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
)
_registered = False


class ExportError(ValueError):
    def __init__(self, field_code: str | None, reason: str) -> None:
        self.field_code = field_code
        self.reason = reason
        super().__init__(f"{reason}:{field_code}")


def _ensure_font_registered() -> None:
    global _registered
    if _registered:
        return
    font_path = next((path for path in _FONT_CANDIDATES if path.is_file()), None)
    if font_path is None:
        raise ExportError(None, "vietnamese_font_missing")
    pdfmetrics.registerFont(TTFont(_FONT_NAME, str(font_path)))
    _registered = True


def _format_value(value: object, field: FormField) -> str:
    if field.data_type == "table":
        if isinstance(value, list):
            return "; ".join(", ".join(f"{k}: {v}" for k, v in row.items()) if isinstance(row, dict) else str(row) for row in value)
        return str(value) if value else ""
    return "" if value is None else str(value)


def _group_fields_by_page(candidate: FormCandidate, values: dict) -> dict[int, list[FormField]]:
    by_page: dict[int, list[FormField]] = {}
    for field in candidate.fields:
        if field.export is None:
            continue
        text_value = _format_value(values.get(field.field_code), field)
        if not text_value:
            continue
        by_page.setdefault(field.export.page, []).append(field)
    return by_page


def render_export(candidate: FormCandidate, values: dict) -> bytes:
    _ensure_font_registered()
    base_path = TEMPLATES_DIR / candidate.source_pdf
    base_reader = PdfReader(base_path)
    writer = PdfWriter()
    by_page = _group_fields_by_page(candidate, values)

    for page_index, page in enumerate(base_reader.pages, start=1):
        overlay_fields = by_page.get(page_index, [])
        if overlay_fields:
            buffer = io.BytesIO()
            page_width, page_height = float(page.mediabox.width), float(page.mediabox.height)
            canvas_obj = canvas.Canvas(buffer, pagesize=(page_width, page_height))
            for field in overlay_fields:
                export = field.export
                text_value = _format_value(values.get(field.field_code), field)
                canvas_obj.setFont(_FONT_NAME, export.font_size)
                if pdfmetrics.stringWidth(text_value, _FONT_NAME, export.font_size) > export.width:
                    raise ExportError(field.field_code, "text_exceeds_field_width")
                if export.align == "right":
                    canvas_obj.drawRightString(export.x + export.width, export.y, text_value)
                elif export.align == "center":
                    canvas_obj.drawCentredString(export.x + export.width / 2, export.y, text_value)
                else:
                    canvas_obj.drawString(export.x, export.y, text_value)
            canvas_obj.save()
            buffer.seek(0)
            page.merge_page(PdfReader(buffer).pages[0])
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
