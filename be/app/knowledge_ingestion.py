import hashlib
import json
import mimetypes
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.embeddings import EmbeddingClient


class ManifestError(ValueError):
    pass


ALLOWED_FACT_TYPES = {
    "audience",
    "receiving_authority",
    "process",
    "required_document",
    "processing_time",
    "fee",
    "legal_basis",
}


@dataclass(frozen=True)
class ChunkDraft:
    chunk_no: int
    chunk_type: str
    hierarchy_path: list[dict[str, str]]
    title: str
    content: str

    @property
    def token_count(self) -> int:
        return len(re.findall(r"\S+", self.content))


def read_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    required = {"document_code", "procedure_code", "source", "source_file"}
    missing = required - manifest.keys()
    if missing:
        raise ManifestError(f"manifest_missing:{','.join(sorted(missing))}")
    source = manifest["source"]
    for key in ("source_code", "source_type", "title_vi", "source_url", "effective_from"):
        if not source.get(key):
            raise ManifestError(f"source_missing:{key}")
    return manifest


def validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    try:
        read_manifest_values(manifest)
    except ManifestError as exc:
        errors.append(str(exc))
    source = manifest.get("source", {})
    if source.get("effective_to") and source.get("effective_from") and source["effective_to"] < source["effective_from"]:
        errors.append("effective_date_range_invalid")
    if manifest.get("jurisdiction_scope", "national") != "national":
        errors.append("pilot_accepts_national_scope_only")
    for index, fact in enumerate(manifest.get("procedure_facts", [])):
        if not isinstance(fact, dict) or fact.get("fact_type") not in ALLOWED_FACT_TYPES:
            errors.append(f"procedure_fact_invalid:{index}")
        elif not isinstance(fact.get("value"), dict) or not fact["value"].get("text"):
            errors.append(f"procedure_fact_value_missing:{index}")
    return errors


def read_manifest_values(manifest: dict) -> None:
    required = {"document_code", "procedure_code", "source", "source_file"}
    missing = required - manifest.keys()
    if missing:
        raise ManifestError(f"manifest_missing:{','.join(sorted(missing))}")
    source = manifest["source"]
    for key in ("source_code", "source_type", "title_vi", "source_url", "effective_from"):
        if not source.get(key):
            raise ManifestError(f"source_missing:{key}")


async def source_bytes(manifest: dict, manifest_path: Path) -> tuple[bytes, str]:
    local_path = manifest.get("source_file")
    if local_path:
        resolved = (manifest_path.parent / local_path).resolve()
        if resolved.is_file():
            return resolved.read_bytes(), resolved.name
    source_url = manifest["source"]["source_url"]
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(source_url)
        response.raise_for_status()
    name = Path(urlparse(source_url).path).name or "official-source"
    return response.content, name


def normalize_bytes(contents: bytes, filename: str, content_type: str | None = None) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".html", ".htm"} or (content_type and "html" in content_type):
        soup = BeautifulSoup(contents, "html.parser")
        for node in soup(["script", "style", "nav", "footer"]):
            node.decompose()
        return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    if suffix == ".pdf" or (content_type and "pdf" in content_type):
        from io import BytesIO

        reader = PdfReader(BytesIO(contents))
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        return extracted or ocr_pdf_bytes(contents)
    return contents.decode("utf-8")


def ocr_pdf_bytes(contents: bytes) -> str:
    """Extract scanned official PDFs without retaining temporary page images."""
    with tempfile.TemporaryDirectory(prefix="icivi-ocr-") as directory:
        root = Path(directory)
        pdf_path = root / "source.pdf"
        pdf_path.write_bytes(contents)
        prefix = root / "page"
        try:
            subprocess.run(
                ["pdftoppm", "-r", "200", "-png", str(pdf_path), str(prefix)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            pages = sorted(root.glob("page-*.png"))
            text = [
                subprocess.run(
                    ["tesseract", str(page), "stdout", "-l", "vie+eng"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).stdout
                for page in pages
            ]
        except (OSError, subprocess.CalledProcessError):
            return ""
    return "\n".join(text).strip()


def chunk_text(normalized_text: str, max_words: int = 420) -> list[ChunkDraft]:
    sections = re.split(r"(?=^\s*(?:Điều\s+\d+|Chương\s+[IVXLCDM]+|Khoản\s+\d+))", normalized_text, flags=re.IGNORECASE | re.MULTILINE)
    chunks: list[ChunkDraft] = []
    current_title = "Nội dung"
    for section in sections:
        section = section.strip()
        if not section:
            continue
        first_line, _, remainder = section.partition("\n")
        if re.match(r"^(Điều|Chương|Khoản)\s+", first_line, re.IGNORECASE):
            current_title = first_line.strip()
        words = section.split()
        for start in range(0, len(words), max_words):
            content = " ".join(words[start : start + max_words])
            chunks.append(
                ChunkDraft(
                    chunk_no=len(chunks) + 1,
                    chunk_type="article" if current_title.lower().startswith("điều") else "other",
                    hierarchy_path=[{"level": "section", "label": current_title}],
                    title=current_title,
                    content=content,
                )
            )
    if not chunks:
        raise ManifestError("source_has_no_extractable_text")
    return chunks


def relative_storage_path(data_dir: Path, target: Path) -> str:
    return target.relative_to(data_dir).as_posix()


async def import_manifest(engine: AsyncEngine, settings: Settings, manifest_path: Path) -> dict[str, int | str]:
    manifest = read_manifest(manifest_path)
    errors = validate_manifest(manifest)
    if errors:
        raise ManifestError(";".join(errors))
    contents, filename = await source_bytes(manifest, manifest_path)
    digest = hashlib.sha256(contents).hexdigest()
    data_dir = settings.knowledge_data_dir.resolve()
    raw_dir = data_dir / "documents" / "legal" / "raw"
    normalized_dir = data_dir / "documents" / "legal" / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{digest[:16]}-{filename}"
    raw_path.write_bytes(contents)
    normalized = normalize_bytes(contents, filename)
    normalized_path = normalized_dir / f"{digest}.txt"
    normalized_path.write_text(normalized, encoding="utf-8")
    chunks = chunk_text(normalized)
    embedder = EmbeddingClient(settings)
    vectors = [await embedder.embed(chunk.content) for chunk in chunks]
    source = manifest["source"]
    effective_from = date.fromisoformat(source["effective_from"])
    effective_to = date.fromisoformat(source["effective_to"]) if source.get("effective_to") else None
    file_code = manifest.get("file_code", f"FILE_{digest[:16].upper()}")
    async with engine.begin() as connection:
        published = await connection.scalar(text("SELECT 1 FROM knowledge_document WHERE document_code = :code AND status = 'published'"), {"code": manifest["document_code"]})
        if published:
            raise ManifestError("published_document_is_immutable")
        procedure_id = await connection.scalar(text("""
            INSERT INTO administrative_procedure (procedure_code) VALUES (:code)
            ON CONFLICT (procedure_code) DO UPDATE SET updated_at = now() RETURNING id
        """), {"code": manifest["procedure_code"]})
        procedure_version_id = await connection.scalar(text("""
            INSERT INTO procedure_version (procedure_id, version_no, title_vi, effective_from, status, metadata)
            VALUES (:procedure_id, 1, :title, :effective_from, 'draft', CAST(:metadata AS jsonb))
            ON CONFLICT (procedure_id, version_no) DO UPDATE SET
                title_vi = EXCLUDED.title_vi, metadata = EXCLUDED.metadata
            RETURNING id
        """), {
            "procedure_id": procedure_id,
            "title": manifest.get("procedure_title", "Đăng ký khai sinh"),
            "effective_from": effective_from,
            "metadata": json.dumps({"scenario_code": manifest.get("scenario_code", "STANDARD")}),
        })
        source_file_id = await connection.scalar(text("""
            INSERT INTO source_file (file_code, original_name, storage_path, mime_type, size_bytes, sha256, source_url, source_name, downloaded_at)
            VALUES (:file_code, :original_name, :storage_path, :mime_type, :size_bytes, :sha256, :source_url, :source_name, :downloaded_at)
            ON CONFLICT (file_code) DO UPDATE SET storage_path = EXCLUDED.storage_path, sha256 = EXCLUDED.sha256, size_bytes = EXCLUDED.size_bytes
            RETURNING id
        """), {"file_code": file_code, "original_name": filename, "storage_path": relative_storage_path(data_dir, raw_path), "mime_type": mimetypes.guess_type(filename)[0] or "application/octet-stream", "size_bytes": len(contents), "sha256": digest, "source_url": source["source_url"], "source_name": source.get("source_name", "Nguồn chính thức"), "downloaded_at": datetime.now().astimezone()})
        legal_source_id = await connection.scalar(text("""
            INSERT INTO legal_source (source_code, source_type, issuing_authority_vi, document_number, title_vi)
            VALUES (:source_code, :source_type, :authority, :document_number, :title)
            ON CONFLICT (source_code) DO UPDATE SET title_vi = EXCLUDED.title_vi, document_number = EXCLUDED.document_number RETURNING id
        """), {"source_code": source["source_code"], "source_type": source["source_type"], "authority": source.get("issuing_authority_vi"), "document_number": source.get("document_number"), "title": source["title_vi"]})
        legal_source_version_id = await connection.scalar(text("""
            INSERT INTO legal_source_version (legal_source_id, version_no, source_file_id, issued_date, effective_from, effective_to, source_url, extracted_text_path, status)
            VALUES (:legal_source_id, 1, :source_file_id, :issued_date, :effective_from, :effective_to, :source_url, :extracted_text_path, 'draft')
            ON CONFLICT (legal_source_id, version_no) DO UPDATE SET source_file_id = EXCLUDED.source_file_id, effective_from = EXCLUDED.effective_from, effective_to = EXCLUDED.effective_to, extracted_text_path = EXCLUDED.extracted_text_path
            RETURNING id
        """), {"legal_source_id": legal_source_id, "source_file_id": source_file_id, "issued_date": date.fromisoformat(source["issued_date"]) if source.get("issued_date") else None, "effective_from": effective_from, "effective_to": effective_to, "source_url": source["source_url"], "extracted_text_path": relative_storage_path(data_dir, normalized_path)})
        await connection.execute(text("DELETE FROM procedure_fact WHERE procedure_version_id = :id AND status = 'draft'"), {"id": procedure_version_id})
        for fact in manifest.get("procedure_facts", []):
            await connection.execute(text("""
                INSERT INTO procedure_fact (
                    procedure_version_id, fact_type, value, effective_from,
                    effective_to, legal_source_version_id, status, metadata
                ) VALUES (
                    :procedure_version_id, :fact_type, CAST(:value AS jsonb),
                    :effective_from, :effective_to, :legal_source_version_id,
                    'draft', CAST(:metadata AS jsonb)
                )
            """), {
                "procedure_version_id": procedure_version_id,
                "fact_type": fact["fact_type"],
                "value": json.dumps(fact["value"]),
                "effective_from": effective_from,
                "effective_to": effective_to,
                "legal_source_version_id": legal_source_version_id,
                "metadata": json.dumps({"scenario_code": manifest.get("scenario_code", "STANDARD"), "provenance": fact.get("provenance", {})}),
            })
        document_id = await connection.scalar(text("""
            INSERT INTO knowledge_document (document_code, legal_source_version_id, procedure_version_id, document_type, language_code, title, normalized_text_path, status)
            VALUES (:document_code, :legal_source_version_id, :procedure_version_id, :document_type, 'vi', :title, :normalized_text_path, 'draft')
            ON CONFLICT (document_code) DO UPDATE SET legal_source_version_id = EXCLUDED.legal_source_version_id, procedure_version_id = EXCLUDED.procedure_version_id, title = EXCLUDED.title, normalized_text_path = EXCLUDED.normalized_text_path, updated_at = now()
            RETURNING id
        """), {"document_code": manifest["document_code"], "legal_source_version_id": legal_source_version_id, "procedure_version_id": procedure_version_id, "document_type": manifest.get("document_type", "legal"), "title": source["title_vi"], "normalized_text_path": relative_storage_path(data_dir, normalized_path)})
        await connection.execute(text("DELETE FROM knowledge_chunk WHERE knowledge_document_id = :document_id"), {"document_id": document_id})
        for chunk, vector in zip(chunks, vectors, strict=True):
            await connection.execute(text("""
                INSERT INTO knowledge_chunk (knowledge_document_id, chunk_no, chunk_type, hierarchy_path, title, content, token_count, embedding)
                VALUES (:document_id, :chunk_no, :chunk_type, CAST(:hierarchy_path AS jsonb), :title, :content, :token_count, CAST(:embedding AS vector))
            """), {"document_id": document_id, "chunk_no": chunk.chunk_no, "chunk_type": chunk.chunk_type, "hierarchy_path": json.dumps(chunk.hierarchy_path), "title": chunk.title, "content": chunk.content, "token_count": chunk.token_count, "embedding": "[" + ",".join(str(value) for value in vector) + "]"})
    return {"document_code": manifest["document_code"], "chunks": len(chunks), "sha256": digest}


async def publish_document(engine: AsyncEngine, settings: Settings, document_code: str) -> None:
    data_dir = settings.knowledge_data_dir.resolve()
    async with engine.begin() as connection:
        document = (await connection.execute(text("""
            SELECT kd.id, kd.normalized_text_path, lsv.id AS legal_source_version_id, lsv.effective_from, lsv.effective_to, lsv.source_url,
                sf.storage_path, sf.sha256, pv.id AS procedure_version_id
            FROM knowledge_document kd JOIN legal_source_version lsv ON lsv.id = kd.legal_source_version_id
            JOIN source_file sf ON sf.id = lsv.source_file_id JOIN procedure_version pv ON pv.id = kd.procedure_version_id
            WHERE kd.document_code = :code FOR UPDATE
        """), {"code": document_code})).mappings().one_or_none()
        if document is None:
            raise ManifestError("document_not_found")
        if not document["source_url"] or not document["effective_from"]:
            raise ManifestError("citation_metadata_missing")
        if document["effective_to"] and document["effective_to"] < date.today():
            raise ManifestError("document_no_longer_effective")
        raw_path = data_dir / document["storage_path"]
        normalized_path = data_dir / document["normalized_text_path"]
        if not raw_path.is_file() or not normalized_path.is_file() or hashlib.sha256(raw_path.read_bytes()).hexdigest() != document["sha256"]:
            raise ManifestError("source_checksum_invalid")
        chunk_count = await connection.scalar(text("SELECT count(*) FROM knowledge_chunk WHERE knowledge_document_id = :id AND embedding IS NOT NULL"), {"id": document["id"]})
        if not chunk_count:
            raise ManifestError("published_document_requires_embeddings")
        await connection.execute(text("UPDATE knowledge_document SET status = 'published', updated_at = now() WHERE id = :id"), {"id": document["id"]})
        await connection.execute(text("UPDATE legal_source_version SET status = 'published' WHERE id = :id"), {"id": document["legal_source_version_id"]})
        await connection.execute(text("UPDATE procedure_version SET status = 'published', updated_at = now() WHERE id = :id"), {"id": document["procedure_version_id"]})
        await connection.execute(text("UPDATE procedure_fact SET status = 'published', updated_at = now() WHERE procedure_version_id = :id AND status = 'draft'"), {"id": document["procedure_version_id"]})
