"""Render a filled form draft as a PDF overlay on the original source template."""

import io
import subprocess
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
_FONT_BOLD_NAME = "NotoSans-Bold"
_FONT_CANDIDATES = (
    Path(__file__).resolve().with_name("assets") / "fonts" / "NotoSans-Regular.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
)
_FONT_BOLD_CANDIDATES = (
    Path(__file__).resolve().with_name("assets") / "fonts" / "NotoSans-Bold.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
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
    font_path = next((path for path in (*_FONT_CANDIDATES, _fontconfig_match()) if path and path.is_file()), None)
    if font_path is None:
        raise ExportError(None, "vietnamese_font_missing")
    pdfmetrics.registerFont(TTFont(_FONT_NAME, str(font_path)))
    bold_candidates = (*_FONT_BOLD_CANDIDATES, _fontconfig_match("Noto Sans:style=Bold"))
    bold_path = next((path for path in bold_candidates if path and path.is_file()), font_path)
    pdfmetrics.registerFont(TTFont(_FONT_BOLD_NAME, str(bold_path)))
    _registered = True


def ensure_vietnamese_font() -> None:
    """Fail deployment startup early when the PDF font is unavailable."""
    _ensure_font_registered()


def _fontconfig_match(pattern: str = "Noto Sans") -> Path | None:
    """Ask Fontconfig for Noto Sans when distributions use a non-Debian path."""
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{family}\n%{file}", pattern],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    family, _, value = result.stdout.strip().partition("\n")
    return Path(value) if family.startswith("Noto Sans") and value else None


def _format_value(value: object, field: FormField) -> str:
    if field.data_type == "table":
        if isinstance(value, list):
            return "; ".join(", ".join(f"{k}: {v}" for k, v in row.items()) if isinstance(row, dict) else str(row) for row in value)
        return str(value) if value else ""
    if value is None:
        return ""
    suffix = field.export.display_suffix if field.export else ""
    return f"{value}{suffix}"


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


def _wrap_text(text_value: str, width: float, font_size: float) -> list[str] | None:
    words = text_value.split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(candidate, _FONT_BOLD_NAME, font_size) <= width:
            current = candidate
            continue
        if not current or pdfmetrics.stringWidth(word, _FONT_BOLD_NAME, font_size) > width:
            return None
        lines.append(current)
        current = word
    lines.append(current)
    return lines


def _truncate_text(text_value: str, width: float, font_size: float) -> str:
    if pdfmetrics.stringWidth(text_value, _FONT_BOLD_NAME, font_size) <= width:
        return text_value
    ellipsis = "…"
    if pdfmetrics.stringWidth(ellipsis, _FONT_BOLD_NAME, font_size) > width:
        raise ExportError(None, "text_exceeds_field_width")
    low, high = 0, len(text_value)
    while low < high:
        middle = (low + high + 1) // 2
        candidate = f"{text_value[:middle].rstrip()}{ellipsis}"
        if pdfmetrics.stringWidth(candidate, _FONT_BOLD_NAME, font_size) <= width:
            low = middle
        else:
            high = middle - 1
    return f"{text_value[:low].rstrip()}{ellipsis}"


def _fit_lines(text_value: str, field: FormField) -> tuple[list[str], float]:
    export = field.export
    assert export is not None
    if export.truncate_overflow or export.overflow_policy == "reject":
        return [_truncate_text(text_value, export.width, export.font_size)], export.font_size

    font_size = export.font_size
    while font_size >= export.min_font_size:
        lines = _wrap_text(text_value, export.width, font_size)
        if lines is not None and len(lines) <= export.max_lines:
            return lines, font_size
        font_size -= 0.5
    raise ExportError(field.field_code, "text_exceeds_field_width")


def _draw_lines(canvas_obj: canvas.Canvas, field: FormField, lines: list[str], font_size: float) -> None:
    export = field.export
    assert export is not None
    if export.mask_width:
        rendered_width = max(pdfmetrics.stringWidth(line, _FONT_BOLD_NAME, font_size) for line in lines)
        mask_width = min(export.mask_width, rendered_width + 2)
        canvas_obj.setFillColorRGB(1, 1, 1)
        canvas_obj.rect(export.x, export.y - 2, mask_width, font_size + 4, fill=1, stroke=0)
        canvas_obj.setFillColorRGB(0, 0, 0)
    canvas_obj.setFont(_FONT_BOLD_NAME, font_size)
    for index, line in enumerate(lines):
        y = export.y - (index * export.line_height)
        if export.align == "right":
            canvas_obj.drawRightString(export.x + export.width, y, line)
        elif export.align == "center":
            canvas_obj.drawCentredString(export.x + export.width / 2, y, line)
        else:
            canvas_obj.drawString(export.x, y, line)


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
                lines, font_size = _fit_lines(text_value, field)
                _draw_lines(canvas_obj, field, lines, font_size)
            canvas_obj.save()
            buffer.seek(0)
            page.merge_page(PdfReader(buffer).pages[0])
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
