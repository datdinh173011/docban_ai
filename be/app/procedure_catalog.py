"""Read the versioned DVC snapshot into section-aware procedure records."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile

from pypdf import PdfReader


SECTION_HEADINGS = {
    "TRÌNH TỰ THỰC HIỆN": "process",
    "CÁCH THỨC THỰC HIỆN": "submission",
    "THÀNH PHẦN HỒ SƠ": "required_document",
    "THỜI HẠN GIẢI QUYẾT": "processing_time",
    "ĐỐI TƯỢNG THỰC HIỆN": "audience",
    "CƠ QUAN THỰC HIỆN": "receiving_authority",
    "CƠ QUAN CÓ THẨM QUYỀN": "receiving_authority",
    "KẾT QUẢ THỰC HIỆN": "result",
    "PHÍ, LỆ PHÍ": "fee",
    "CĂN CỨ PHÁP LÝ": "legal_basis",
    "YÊU CẦU, ĐIỀU KIỆN": "condition",
}
_XML_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def normalize_text(value: str) -> str:
    """Make Vietnamese matching accent-insensitive and deterministic."""
    decomposed = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def tokens(value: str) -> set[str]:
    return set(_TOKEN.findall(normalize_text(value)))


@dataclass(frozen=True)
class ProcedureSection:
    section_type: str
    title: str
    content: str
    chunk_no: int


@dataclass(frozen=True)
class ProcedureRecord:
    code: str
    name: str
    pdf_file: str
    attachment_count: int
    group: str
    field: str
    request_type: str
    audience: str
    scenario: str
    scope: str
    locality: str
    execution_level: str
    data_warning: str
    issuing_authority: str
    receiving_authority: str
    decision_number: str | None
    snapshot_sha256: str
    sections: tuple[ProcedureSection, ...]

    @property
    def is_local(self) -> bool:
        return self.scope == "Địa phương"


def _column(reference: str) -> str:
    return "".join(char for char in reference if char.isalpha())


def _read_workbook_rows(path: Path) -> list[dict[str, str]]:
    with ZipFile(path) as archive:
        shared = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(node.text or "" for node in item.iterfind(".//m:t", _XML_NS)) for item in shared.findall("m:si", _XML_NS)]
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    rows: list[dict[str, str]] = []
    for xml_row in sheet.findall(".//m:sheetData/m:row", _XML_NS):
        row: dict[str, str] = {}
        for cell in xml_row.findall("m:c", _XML_NS):
            value = cell.find("m:v", _XML_NS)
            raw = "" if value is None else value.text or ""
            if cell.attrib.get("t") == "s" and raw:
                raw = strings[int(raw)]
            row[_column(cell.attrib["r"])] = raw.strip()
        rows.append(row)
    if not rows:
        raise ValueError("taxonomy_workbook_is_empty")
    headers = rows[0]
    return [{headers.get(column, column): value for column, value in row.items()} for row in rows[1:]]


def _pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _compact(value: str) -> str:
    # PostgreSQL TEXT rejects NUL bytes emitted by some PDF extractors.
    value = value.replace("\x00", "")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", value)).strip()


def _extract_decision_number(text: str) -> str | None:
    match = re.search(r"Số quyết định\s+([^\n]+)", text, flags=re.IGNORECASE)
    return _compact(match.group(1)) if match else None


def split_sections(text: str) -> tuple[ProcedureSection, ...]:
    """Split PDF text at known DVC headings while retaining unknown preamble."""
    positions: list[tuple[int, str, str]] = []
    normalized = normalize_text(text).upper()
    for heading, section_type in SECTION_HEADINGS.items():
        match = re.search(re.escape(normalize_text(heading).upper()), normalized)
        if match:
            positions.append((match.start(), heading.title(), section_type))
    positions.sort()
    sections: list[ProcedureSection] = []
    if positions and positions[0][0] > 0:
        preamble = _compact(text[:positions[0][0]])
        if preamble:
            sections.append(ProcedureSection("overview", "Thông tin thủ tục", preamble, 0))
    chunk_offset = len(sections)
    for index, (start, title, section_type) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
        content = _compact(text[start:end])
        if content:
            sections.append(ProcedureSection(section_type, title, content, chunk_offset + index))
    if not sections:
        content = _compact(text)
        if content:
            sections.append(ProcedureSection("overview", "Thông tin thủ tục", content, 0))
    return tuple(sections)


def _record_from_rows(procedure: dict[str, Any], taxonomy: dict[str, str], snapshot_dir: Path) -> ProcedureRecord:
    pdf_path = snapshot_dir / procedure["PdfFile"]
    if not pdf_path.is_file():
        raise ValueError(f"procedure_pdf_missing:{procedure['Code']}")
    raw_pdf = pdf_path.read_bytes()
    text = _pdf_text(pdf_path)
    return ProcedureRecord(
        code=procedure["Code"],
        name=procedure["Name"],
        pdf_file=procedure["PdfFile"],
        attachment_count=int(procedure.get("AttachmentCount", 0)),
        group=taxonomy.get("Nhóm đề mục", "Chưa phân loại"),
        field=taxonomy.get("Lĩnh vực chuẩn hóa", "Chưa phân loại"),
        request_type=taxonomy.get("Loại yêu cầu", "Chưa phân loại"),
        audience=taxonomy.get("Đối tượng người dùng", "Cần hỏi thêm"),
        scenario=taxonomy.get("Tình huống/đối tượng hồ sơ", "Cần hỏi thêm"),
        scope=taxonomy.get("Phạm vi", "Địa phương"),
        locality=taxonomy.get("Địa phương", "Áp dụng tại địa phương (không nêu tỉnh)"),
        execution_level=taxonomy.get("Cấp thực hiện", "Chưa có dữ liệu rõ"),
        data_warning=taxonomy.get("Cảnh báo dữ liệu", "Không có cảnh báo tự động"),
        issuing_authority=taxonomy.get("Cơ quan ban hành", ""),
        receiving_authority=taxonomy.get("Cơ quan thực hiện", ""),
        decision_number=_extract_decision_number(text),
        snapshot_sha256=hashlib.sha256(raw_pdf).hexdigest(),
        sections=split_sections(text),
    )


class ProcedureCatalog:
    """Immutable local view of one crawled procedure snapshot."""

    def __init__(self, records: list[ProcedureRecord], crawled_at: str) -> None:
        if len({record.code for record in records}) != len(records):
            raise ValueError("procedure_codes_must_be_unique")
        self.records = records
        self.crawled_at = crawled_at
        self.by_code = {record.code: record for record in records}

    @classmethod
    def from_snapshot(cls, snapshot_dir: Path) -> "ProcedureCatalog":
        with (snapshot_dir / "procedures.json").open(encoding="utf-8-sig") as source:
            procedures = json.load(source)
        with (snapshot_dir / "summary.json").open(encoding="utf-8-sig") as source:
            summary = json.load(source)
        if summary.get("ProcedureCount") != len(procedures):
            raise ValueError("snapshot_procedure_count_mismatch")
        taxonomy_rows = _read_workbook_rows(snapshot_dir / "phan-loai-tthc-cho-ai-agent.xlsx")
        taxonomy_by_code = {row["Mã số"]: row for row in taxonomy_rows if row.get("Mã số")}
        if set(item["Code"] for item in procedures) != set(taxonomy_by_code):
            raise ValueError("snapshot_taxonomy_codes_mismatch")
        return cls([_record_from_rows(item, taxonomy_by_code[item["Code"]], snapshot_dir) for item in procedures], summary["CrawledAt"])

    def dump(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"crawled_at": self.crawled_at, "records": [asdict(record) for record in self.records]}
        output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ProcedureCatalog":
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = [
            ProcedureRecord(
                **{**record, "sections": tuple(ProcedureSection(**section) for section in record["sections"])}
            )
            for record in payload["records"]
        ]
        return cls(records, payload["crawled_at"])


@lru_cache
def load_catalog(snapshot_dir: str, catalog_path: str | None = None) -> ProcedureCatalog:
    """Reuse an immutable catalog across app lifespans in one worker process."""
    return ProcedureCatalog.load(Path(catalog_path)) if catalog_path else ProcedureCatalog.from_snapshot(Path(snapshot_dir))
