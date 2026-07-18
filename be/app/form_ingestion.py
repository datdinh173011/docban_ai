"""Trusted local PDF form inventory and structural extraction for V1."""

import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings

TRUST_TIER = "operator_verified_primary"


@dataclass(frozen=True)
class FormSourceSpec:
    filename: str
    source_key: str
    form_code: str | None
    form_role: str
    asset_kind: str
    title_vi: str
    parser_profile: str
    expected_pages: int
    expected_markers: tuple[str, ...]
    field_codes: tuple[str, ...] = ()
    detached_house_only: bool = False


@dataclass(frozen=True)
class FormInspection:
    source_key: str
    filename: str
    sha256: str
    page_count: int
    extracted_characters: int
    rendered_page_count: int
    missing_markers: tuple[str, ...]
    errors: tuple[str, ...]
    source_trust_tier: str = TRUST_TIER

    @property
    def valid(self) -> bool:
        return not self.errors and not self.missing_markers

    def registry_payload(self) -> dict:
        payload = asdict(self)
        payload["status"] = "in_review" if self.valid else "draft"
        return payload


FORM_SOURCES: tuple[FormSourceSpec, ...] = (
    FormSourceSpec("01_to_khai_dang_ky_khai_sinh.pdf", "BIRTH_REGISTRATION_FORM_2026", "BIRTH_REGISTRATION_FORM", "primary_form", "form_pdf", "Tờ khai đăng ký khai sinh", "birth_registration", 2, ("TỜ KHAI ĐĂNG KÝ KHAI SINH", "Họ, chữ đệm, tên người yêu cầu", "Họ, chữ đệm, tên người mẹ"), ("applicant_full_name", "child_full_name", "child_birth_date", "mother_full_name", "father_full_name")),
    FormSourceSpec("02_mau_CT01_TT116_2026.pdf", "PERMANENT_RESIDENCE_CT01_2026", "PERMANENT_RESIDENCE_CT01_FORM", "primary_form", "form_pdf", "Mẫu CT01 - Tờ khai thay đổi thông tin cư trú", "permanent_residence_ct01", 2, ("TỜ KHAI THAY ĐỔI THÔNG TIN CƯ TRÚ", "Số định danh cá nhân", "Những thành viên trong hộ gia đình"), ("applicant_full_name", "citizen_id", "household_head_name", "residence_request", "household_members")),
    FormSourceSpec("03_don_de_nghi_cap_gpxd_nha_o_rieng_le.pdf", "CONSTRUCTION_PERMIT_REQUEST_2026", "CONSTRUCTION_PERMIT_REQUEST_FORM", "primary_form", "form_pdf", "Đơn đề nghị cấp giấy phép xây dựng", "construction_detached_house", 4, ("ĐƠN ĐỀ NGHỊ CẤP GIẤY PHÉP XÂY DỰNG", "4.4. Đối với công trình nhà ở riêng lẻ", "NGƯỜI LÀM ĐƠN"), ("owner_name", "owner_citizen_id", "construction_address", "first_floor_area", "total_floor_area", "building_height", "floor_count"), True),
)

FIELD_LABELS = {
    "applicant_full_name": "Họ, chữ đệm, tên người yêu cầu",
    "child_full_name": "Họ, chữ đệm, tên người được đăng ký khai sinh",
    "child_birth_date": "Ngày, tháng, năm sinh",
    "mother_full_name": "Họ, chữ đệm, tên người mẹ",
    "father_full_name": "Họ, chữ đệm, tên người cha",
    "citizen_id": "Số định danh cá nhân",
    "household_head_name": "Họ, chữ đệm, tên chủ hộ",
    "residence_request": "Nội dung đề nghị thay đổi thông tin cư trú",
    "household_members": "Những thành viên trong hộ gia đình",
    "owner_name": "Tên chủ đầu tư",
    "owner_citizen_id": "Số định danh cá nhân của chủ đầu tư",
    "construction_address": "Địa điểm xây dựng",
    "first_floor_area": "Diện tích xây dựng tầng 1",
    "total_floor_area": "Tổng diện tích sàn",
    "building_height": "Chiều cao công trình",
    "floor_count": "Số tầng",
}


def source_specs() -> dict[str, FormSourceSpec]:
    return {spec.filename: spec for spec in FORM_SOURCES}


def extract_pdf_text(path: Path) -> tuple[int, str]:
    reader = PdfReader(path)
    return len(reader.pages), "\n".join(page.extract_text() or "" for page in reader.pages)


def render_pdf_pages(path: Path) -> int:
    """Render every page so a technically broken but text-readable PDF cannot publish."""
    renderer = shutil.which("pdftoppm")
    if renderer is None:
        raise ValueError("page_renderer_unavailable")
    with tempfile.TemporaryDirectory(prefix="icivi-form-render-") as temporary_directory:
        output_prefix = Path(temporary_directory) / "page"
        result = subprocess.run(
            [renderer, "-png", str(path), str(output_prefix)],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise ValueError("page_render_failed")
        return len(list(Path(temporary_directory).glob("page-*.png")))


def ocr_pdf_text(path: Path) -> str:
    """Use OCR only after native extraction fails or produces unusable text."""
    renderer = shutil.which("pdftoppm")
    ocr = shutil.which("tesseract")
    if renderer is None or ocr is None:
        raise ValueError("ocr_fallback_unavailable")
    with tempfile.TemporaryDirectory(prefix="icivi-form-ocr-") as temporary_directory:
        output_prefix = Path(temporary_directory) / "page"
        render = subprocess.run(
            [renderer, "-r", "200", "-png", str(path), str(output_prefix)],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if render.returncode != 0:
            raise ValueError("ocr_render_failed")
        text_parts: list[str] = []
        for image_path in sorted(Path(temporary_directory).glob("page-*.png")):
            result = subprocess.run(
                [ocr, str(image_path), "stdout", "-l", "vie+eng"],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                raise ValueError("ocr_failed")
            text_parts.append(result.stdout)
        return "\n".join(text_parts)


def detached_house_text(text: str) -> str:
    start = text.find("4.4. Đối với công trình nhà ở riêng lẻ")
    end = text.find("4.5. Đối với trường hợp cải tạo", start)
    return text[start:end if end != -1 else None]


def inspect_form_pdf(path: Path, spec: FormSourceSpec) -> FormInspection:
    contents = path.read_bytes()
    errors: list[str] = []
    try:
        page_count, text = extract_pdf_text(path)
    except Exception:
        page_count, text = 0, ""
        errors.append("native_extraction_failed")
    try:
        rendered_page_count = render_pdf_pages(path)
    except ValueError as exc:
        rendered_page_count = 0
        errors.append(str(exc))
    if rendered_page_count != page_count:
        errors.append("page_render_count_mismatch")
    if page_count == 0:
        page_count = rendered_page_count
        errors = [error for error in errors if error != "page_render_count_mismatch"]
    if page_count != spec.expected_pages:
        errors.append("page_count_mismatch")
    if not text.strip() or len(text.strip()) < 200:
        try:
            text = ocr_pdf_text(path)
            errors = [error for error in errors if error != "native_extraction_failed"]
        except ValueError as exc:
            errors.append(str(exc))
    relevant_text = detached_house_text(text) if spec.detached_house_only else text
    if len(text.strip()) < 200:
        errors.append("extraction_quality_insufficient_needs_ocr")
    if spec.detached_house_only and not relevant_text.strip():
        errors.append("detached_house_section_missing")
    missing_markers = tuple(marker for marker in spec.expected_markers if marker not in text)
    return FormInspection(
        source_key=spec.source_key,
        filename=path.name,
        sha256=hashlib.sha256(contents).hexdigest(),
        page_count=page_count,
        extracted_characters=len(text.strip()),
        rendered_page_count=rendered_page_count,
        missing_markers=missing_markers,
        errors=tuple(errors),
    )


def inspect_form_corpus(directory: Path) -> list[FormInspection]:
    specs = source_specs()
    unexpected = sorted(path.name for path in directory.glob("*.pdf") if path.name not in specs)
    if unexpected:
        raise ValueError(f"unexpected_form_sources:{','.join(unexpected)}")
    missing = sorted(filename for filename in specs if not (directory / filename).is_file())
    if missing:
        raise ValueError(f"form_sources_missing:{','.join(missing)}")
    return [inspect_form_pdf(directory / spec.filename, spec) for spec in FORM_SOURCES]


def build_form_draft(spec: FormSourceSpec, inspection: FormInspection) -> dict:
    if not inspection.valid:
        raise ValueError("form_requires_technical_review")
    if spec.form_role != "primary_form":
        raise ValueError("noncanonical_form_source_cannot_be_published_as_form")
    return {
        "form_code": spec.form_code,
        "form_role": spec.form_role,
        "source_key": spec.source_key,
        "source_trust_tier": TRUST_TIER,
        "fields": [{"field_code": field_code, "provenance": {"source_key": spec.source_key}} for field_code in spec.field_codes],
        "export_enabled": False,
    }


def _storage_path(data_dir: Path, path: Path) -> str:
    return path.relative_to(data_dir).as_posix()


async def import_form_corpus(
    engine: AsyncEngine, settings: Settings, source_dir: Path
) -> list[dict[str, str | int]]:
    """Create immutable draft snapshots and form-schema records for inspected PDFs."""
    inspections = inspect_form_corpus(source_dir)
    inspection_by_key = {inspection.source_key: inspection for inspection in inspections}
    data_dir = settings.knowledge_data_dir.resolve()
    raw_dir = data_dir / "documents" / "forms" / "raw"
    normalized_dir = data_dir / "documents" / "forms" / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, str | int]] = []

    async with engine.begin() as connection:
        for spec in FORM_SOURCES:
            inspection = inspection_by_key[spec.source_key]
            if not inspection.valid:
                raise ValueError(f"form_technical_review_failed:{spec.source_key}")
            contents = (source_dir / spec.filename).read_bytes()
            _, normalized_text = extract_pdf_text(source_dir / spec.filename)
            raw_path = raw_dir / f"{inspection.sha256}-{spec.filename}"
            normalized_path = normalized_dir / f"{inspection.sha256}.txt"
            if not raw_path.exists():
                raw_path.write_bytes(contents)
            if not normalized_path.exists():
                normalized_path.write_text(normalized_text, encoding="utf-8")
            latest = (await connection.execute(text("""
                SELECT id, version_no, sha256, status FROM source_registry
                WHERE source_key = :source_key ORDER BY version_no DESC LIMIT 1
            """), {"source_key": spec.source_key})).mappings().one_or_none()
            if latest and latest["sha256"] == inspection.sha256:
                results.append({"source_key": spec.source_key, "version_no": latest["version_no"], "status": latest["status"]})
                continue
            version_no = (latest["version_no"] + 1) if latest else 1
            registry_id = await connection.scalar(text("""
                INSERT INTO source_registry (
                    source_key, version_no, canonical_path, snapshot_path, normalized_text_path,
                    source_trust_tier, asset_kind, form_code, form_role, jurisdiction_scope,
                    parser_profile, expected_field_groups, sha256, page_count, effective_from,
                    metadata, status
                ) VALUES (
                    :source_key, :version_no, :canonical_path, :snapshot_path, :normalized_text_path,
                    :trust, :asset_kind, :form_code, :form_role, 'national', :parser_profile,
                    CAST(:field_groups AS jsonb), :sha256, :page_count, :effective_from,
                    CAST(:metadata AS jsonb), 'in_review'
                ) RETURNING id
            """), {
                "source_key": spec.source_key,
                "version_no": version_no,
                "canonical_path": spec.filename,
                "snapshot_path": _storage_path(data_dir, raw_path),
                "normalized_text_path": _storage_path(data_dir, normalized_path),
                "trust": TRUST_TIER,
                "asset_kind": spec.asset_kind,
                "form_code": spec.form_code,
                "form_role": spec.form_role,
                "parser_profile": spec.parser_profile,
                "field_groups": json.dumps(["main"] if spec.field_codes else []),
                "sha256": inspection.sha256,
                "page_count": inspection.page_count,
                "effective_from": date.today(),
                "metadata": json.dumps({"inspection": inspection.registry_payload(), "imported_at": datetime.now().astimezone().isoformat()}),
            })
            if spec.form_code:
                template_id = await connection.scalar(text("""
                    INSERT INTO form_template (form_code, title_vi, status)
                    VALUES (:form_code, :title_vi, 'in_review')
                    ON CONFLICT (form_code) DO UPDATE SET updated_at = now()
                    RETURNING id
                """), {"form_code": spec.form_code, "title_vi": spec.title_vi})
                form_version_id = await connection.scalar(text("""
                    INSERT INTO form_version (form_template_id, source_registry_id, version_no, form_role, effective_from, status, metadata)
                    VALUES (:template_id, :registry_id, :version_no, :form_role, :effective_from, 'in_review', CAST(:metadata AS jsonb))
                    RETURNING id
                """), {
                    "template_id": template_id,
                    "registry_id": registry_id,
                    "version_no": version_no,
                    "form_role": spec.form_role,
                    "effective_from": date.today(),
                    "metadata": json.dumps({"detached_house_only": spec.detached_house_only, "export_enabled": False}),
                })
                section_id = await connection.scalar(text("""
                    INSERT INTO form_section (form_version_id, section_code, title_vi, page_start, page_end, display_order)
                    VALUES (:form_version_id, 'main', :title_vi, 1, :page_count, 1)
                    RETURNING id
                """), {"form_version_id": form_version_id, "title_vi": spec.title_vi, "page_count": inspection.page_count})
                for field_code in spec.field_codes:
                    await connection.execute(text("""
                        INSERT INTO form_field (form_version_id, section_id, field_code, label_vi, data_type, page_no, provenance)
                        VALUES (:form_version_id, :section_id, :field_code, :label_vi, 'text', 1, CAST(:provenance AS jsonb))
                    """), {"form_version_id": form_version_id, "section_id": section_id, "field_code": field_code, "label_vi": FIELD_LABELS[field_code], "provenance": json.dumps({"source_key": spec.source_key, "page_no": 1})})
            results.append({"source_key": spec.source_key, "version_no": version_no, "status": "in_review"})
    return results


async def publish_form(engine: AsyncEngine, settings: Settings, form_code: str) -> None:
    """Publish only a technically valid, trusted draft and never mutate a published version."""
    data_dir = settings.knowledge_data_dir.resolve()
    async with engine.begin() as connection:
        form = (await connection.execute(text("""
            SELECT fv.id AS form_version_id, fv.form_role, fv.status AS form_status,
                ft.id AS template_id, sr.id AS registry_id, sr.status AS source_status,
                sr.source_trust_tier, sr.snapshot_path, sr.normalized_text_path, sr.sha256,
                sr.form_role AS source_role
            FROM form_version fv
            JOIN form_template ft ON ft.id = fv.form_template_id
            JOIN source_registry sr ON sr.id = fv.source_registry_id
            WHERE ft.form_code = :form_code AND fv.status = 'in_review'
            ORDER BY fv.version_no DESC LIMIT 1 FOR UPDATE
        """), {"form_code": form_code})).mappings().one_or_none()
        if form is None:
            raise ValueError("form_draft_not_found")
        if form["source_trust_tier"] != TRUST_TIER or form["source_status"] != "in_review":
            raise ValueError("form_source_not_trusted_or_reviewed")
        raw_path = data_dir / form["snapshot_path"]
        normalized_path = data_dir / form["normalized_text_path"]
        if not raw_path.is_file() or not normalized_path.is_file() or hashlib.sha256(raw_path.read_bytes()).hexdigest() != form["sha256"]:
            raise ValueError("form_snapshot_checksum_invalid")
        field_count = await connection.scalar(text("SELECT count(*) FROM form_field WHERE form_version_id = :id"), {"id": form["form_version_id"]})
        if form["form_role"] == "primary_form" and not field_count:
            raise ValueError("primary_form_requires_fields")
        await connection.execute(text("UPDATE source_registry SET status = 'published', updated_at = now() WHERE id = :id"), {"id": form["registry_id"]})
        await connection.execute(text("UPDATE form_version SET status = 'published', updated_at = now() WHERE id = :id"), {"id": form["form_version_id"]})
        await connection.execute(text("UPDATE form_template SET status = 'published', updated_at = now() WHERE id = :id"), {"id": form["template_id"]})
