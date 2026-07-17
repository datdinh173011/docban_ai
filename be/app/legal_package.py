"""Approved-source ingestion for immutable legal knowledge packages."""

import hashlib
import json
import mimetypes
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.embeddings import EmbeddingClient
from app.knowledge_ingestion import ALLOWED_FACT_TYPES, ChunkDraft, chunk_text, normalize_bytes, relative_storage_path


class PackageError(ValueError):
    pass


REQUIRED_REGISTRY_FIELDS = {
    "source_code", "issuing_authority_vi",
    "title_vi", "source_type", "procedure_code", "owner",
    "check_cadence_days", "parser_profile", "approval_status", "legal_status",
}

APPROVED_REGISTRY_FIELDS = {
    "canonical_url", "fetch_url", "allowed_canonical_hostname",
    "allowed_fetch_hostname", "official_verified_at", "reviewer_id",
}

SUPPORTED_PROCEDURES = {
    "BIRTH_REGISTRATION": "Đăng ký khai sinh",
    "PERMANENT_RESIDENCE": "Đăng ký thường trú",
    "CONSTRUCTION_PERMIT_DETACHED_HOUSE": "Cấp giấy phép xây dựng mới cho nhà ở riêng lẻ",
}


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError("invalid_json") from exc


def parse_review_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_registry_document(document: dict) -> list[str]:
    sources = document.get("sources")
    if not isinstance(sources, list) or not sources:
        return ["registry_sources_missing"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"registry_source_invalid:{index}")
            continue
        missing = REQUIRED_REGISTRY_FIELDS - source.keys()
        if missing:
            errors.append(f"registry_source_missing:{index}:{','.join(sorted(missing))}")
            continue
        if source["approval_status"] not in {"draft", "approved", "retired"}:
            errors.append(f"registry_approval_invalid:{source['source_code']}")
        if source["procedure_code"] not in SUPPORTED_PROCEDURES:
            errors.append(f"registry_procedure_not_supported:{source['source_code']}")
        if source["legal_status"] not in {"draft", "active", "amended", "superseded", "repealed", "discovery"}:
            errors.append(f"registry_legal_status_invalid:{source['source_code']}")
        if source["approval_status"] == "approved":
            approved_missing = APPROVED_REGISTRY_FIELDS - source.keys()
            if approved_missing or source["legal_status"] not in {"active", "amended"}:
                errors.append(f"registry_approval_metadata_missing:{source['source_code']}")
            for url_key, host_key in (("canonical_url", "allowed_canonical_hostname"), ("fetch_url", "allowed_fetch_hostname")):
                parsed = urlparse(source.get(url_key, ""))
                if parsed.scheme != "https" or parsed.hostname != source.get(host_key) or parsed.hostname == "thuvienphapluat.vn":
                    errors.append(f"registry_url_not_exactly_allowed:{source['source_code']}")
        if source["source_code"] in seen:
            errors.append(f"registry_source_duplicate:{source['source_code']}")
        seen.add(source["source_code"])
    return errors


def validate_package_manifest(manifest: dict) -> list[str]:
    required = {"package_code", "version_no", "procedure_code", "documents", "procedure_facts"}
    missing = required - manifest.keys()
    if missing:
        return [f"package_missing:{','.join(sorted(missing))}"]
    if manifest["procedure_code"] not in SUPPORTED_PROCEDURES:
        return ["package_procedure_not_supported"]
    if not isinstance(manifest["version_no"], int) or manifest["version_no"] < 1:
        return ["package_version_invalid"]
    errors: list[str] = []
    document_codes: set[str] = set()
    source_codes: set[str] = set()
    for index, document in enumerate(manifest["documents"]):
        if not isinstance(document, dict) or not {"document_code", "source_code"} <= document.keys():
            errors.append(f"package_document_invalid:{index}")
            continue
        if document["document_code"] in document_codes or document["source_code"] in source_codes:
            errors.append(f"package_document_duplicate:{index}")
        document_codes.add(document["document_code"])
        source_codes.add(document["source_code"])
    for index, fact in enumerate(manifest["procedure_facts"]):
        if not isinstance(fact, dict) or fact.get("fact_type") not in ALLOWED_FACT_TYPES:
            errors.append(f"package_fact_invalid:{index}")
            continue
        if fact.get("source_code") not in source_codes or not fact.get("section_reference"):
            errors.append(f"package_fact_provenance_invalid:{index}")
        if not isinstance(fact.get("value"), dict) or not fact["value"].get("text"):
            errors.append(f"package_fact_value_missing:{index}")
    return errors


async def register_sources(engine: AsyncEngine, registry_document: dict) -> int:
    errors = validate_registry_document(registry_document)
    if errors:
        raise PackageError(";".join(errors))
    async with engine.begin() as connection:
        for source in registry_document["sources"]:
            await connection.execute(text("""
                INSERT INTO official_source_registry (
                    source_code, canonical_url, fetch_url, allowed_canonical_hostname,
                    allowed_fetch_hostname, allowed_redirect_hostnames, issuing_authority_vi,
                    document_number, title_vi, source_type, procedure_code, scenario_code,
                    effective_from, effective_to, owner, check_cadence_days, parser_profile,
                    approval_status, legal_status, amends_source_codes, supersedes_source_codes,
                    official_verified_at, reviewer_id, discovery_urls, metadata
                ) VALUES (
                    :source_code, :canonical_url, :fetch_url, :allowed_canonical_hostname,
                    :allowed_fetch_hostname, CAST(:allowed_redirect_hostnames AS text[]), :issuing_authority_vi,
                    :document_number, :title_vi, :source_type, :procedure_code, :scenario_code,
                    :effective_from, :effective_to, :owner, :check_cadence_days, :parser_profile,
                    :approval_status, :legal_status, CAST(:amends_source_codes AS text[]), CAST(:supersedes_source_codes AS text[]),
                    :official_verified_at, :reviewer_id, CAST(:discovery_urls AS jsonb), CAST(:metadata AS jsonb)
                ) ON CONFLICT (source_code) DO UPDATE SET
                    canonical_url = EXCLUDED.canonical_url,
                    fetch_url = EXCLUDED.fetch_url,
                    allowed_canonical_hostname = EXCLUDED.allowed_canonical_hostname,
                    allowed_fetch_hostname = EXCLUDED.allowed_fetch_hostname,
                    allowed_redirect_hostnames = EXCLUDED.allowed_redirect_hostnames,
                    issuing_authority_vi = EXCLUDED.issuing_authority_vi,
                    document_number = EXCLUDED.document_number,
                    title_vi = EXCLUDED.title_vi,
                    source_type = EXCLUDED.source_type,
                    procedure_code = EXCLUDED.procedure_code,
                    scenario_code = EXCLUDED.scenario_code,
                    effective_from = EXCLUDED.effective_from,
                    effective_to = EXCLUDED.effective_to,
                    owner = EXCLUDED.owner,
                    check_cadence_days = EXCLUDED.check_cadence_days,
                    parser_profile = EXCLUDED.parser_profile,
                    approval_status = EXCLUDED.approval_status,
                    legal_status = EXCLUDED.legal_status,
                    amends_source_codes = EXCLUDED.amends_source_codes,
                    supersedes_source_codes = EXCLUDED.supersedes_source_codes,
                    official_verified_at = EXCLUDED.official_verified_at,
                    reviewer_id = EXCLUDED.reviewer_id,
                    discovery_urls = EXCLUDED.discovery_urls,
                    metadata = EXCLUDED.metadata,
                    updated_at = now()
            """), {
                **source,
                "scenario_code": source.get("scenario_code", "STANDARD"),
                "canonical_url": source.get("canonical_url"),
                "fetch_url": source.get("fetch_url"),
                "allowed_canonical_hostname": source.get("allowed_canonical_hostname"),
                "allowed_fetch_hostname": source.get("allowed_fetch_hostname"),
                "allowed_redirect_hostnames": source.get("allowed_redirect_hostnames", []),
                "amends_source_codes": source.get("amends_source_codes", []),
                "supersedes_source_codes": source.get("supersedes_source_codes", []),
                "official_verified_at": parse_review_timestamp(source.get("official_verified_at")),
                "reviewer_id": source.get("reviewer_id"),
                "discovery_urls": json.dumps(source.get("discovery_urls", [])),
                "effective_from": date.fromisoformat(source["effective_from"]) if source.get("effective_from") else None,
                "effective_to": date.fromisoformat(source["effective_to"]) if source.get("effective_to") else None,
                "metadata": json.dumps(source.get("metadata", {})),
            })
    return len(registry_document["sources"])


async def _approved_sources(connection, source_codes: set[str]) -> dict[str, dict]:
    rows = (await connection.execute(text("""
        SELECT * FROM official_source_registry
        WHERE source_code = ANY(CAST(:source_codes AS text[]))
          AND approval_status = 'approved'
          AND legal_status IN ('active', 'amended')
          AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
    """), {"source_codes": list(source_codes)})).mappings().all()
    sources = {row["source_code"]: dict(row) for row in rows}
    if set(sources) != source_codes:
        raise PackageError("package_contains_unapproved_source")
    superseded = {
        source_code
        for source in sources.values()
        for source_code in source["supersedes_source_codes"]
    }
    if source_codes & superseded:
        raise PackageError("package_contains_superseded_source")
    return sources


async def _fetch_approved_source(source: dict) -> tuple[bytes, str, str | None]:
    parsed = urlparse(source["fetch_url"])
    if parsed.scheme != "https" or parsed.hostname != source["allowed_fetch_hostname"]:
        raise PackageError("source_url_not_authorized")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(source["fetch_url"])
        response.raise_for_status()
    final_host = urlparse(str(response.url)).hostname
    allowed_hosts = {source["allowed_fetch_hostname"], *source["allowed_redirect_hostnames"]}
    if final_host not in allowed_hosts:
        raise PackageError("source_redirect_not_authorized")
    content_type = response.headers.get("content-type")
    filename = Path(urlparse(str(response.url)).path).name or f"{source['source_code']}.html"
    return response.content, filename, content_type


def verify_source_content(source: dict, normalized_text: str) -> None:
    """Reject snapshots that do not identify the approved legal document."""
    expected_markers = source["metadata"].get("expected_text_markers", [])
    markers = [source["document_number"], *(expected_markers or [source["title_vi"]])]
    normalized = " ".join(normalized_text.casefold().split())
    if any(marker and " ".join(marker.casefold().split()) not in normalized for marker in markers):
        raise PackageError("source_document_metadata_mismatch")


async def import_package(engine: AsyncEngine, settings: Settings, manifest: dict) -> dict[str, int | str]:
    errors = validate_package_manifest(manifest)
    if errors:
        raise PackageError(";".join(errors))
    data_dir = settings.knowledge_data_dir.resolve()
    raw_dir = data_dir / "documents" / "legal" / "raw"
    normalized_dir = data_dir / "documents" / "legal" / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as connection:
        existing = await connection.scalar(text("""
            SELECT 1 FROM knowledge_package WHERE package_code = :code AND version_no = :version
        """), {"code": manifest["package_code"], "version": manifest["version_no"]})
        if existing:
            raise PackageError("package_version_already_exists")
        source_codes = {document["source_code"] for document in manifest["documents"]}
        registry_sources = await _approved_sources(connection, source_codes)
        embedder = EmbeddingClient(settings)
        if not embedder.configured:
            raise PackageError("embedding_provider_not_configured")
        package_id = await connection.scalar(text("""
            INSERT INTO knowledge_package (package_code, version_no, procedure_code, scenario_code, status, metadata)
            VALUES (:code, :version, :procedure_code, :scenario_code, 'in_review', CAST(:metadata AS jsonb))
            RETURNING id
        """), {
            "code": manifest["package_code"], "version": manifest["version_no"],
            "procedure_code": manifest["procedure_code"], "scenario_code": manifest.get("scenario_code", "STANDARD"),
            "metadata": json.dumps({"expected_scenarios": manifest.get("expected_scenarios", [])}),
        })
        procedure_id = await connection.scalar(text("""
            INSERT INTO administrative_procedure (procedure_code) VALUES (:code)
            ON CONFLICT (procedure_code) DO UPDATE SET updated_at = now() RETURNING id
        """), {"code": manifest["procedure_code"]})
        procedure_version_id = await connection.scalar(text("""
            INSERT INTO procedure_version (procedure_id, version_no, title_vi, effective_from, status, metadata, knowledge_package_id)
            VALUES (:procedure_id, :version, :title, :effective_from, 'in_review', CAST(:metadata AS jsonb), :package_id)
            ON CONFLICT (procedure_id, version_no) DO UPDATE SET knowledge_package_id = EXCLUDED.knowledge_package_id
            RETURNING id
        """), {
            "procedure_id": procedure_id, "version": manifest["version_no"], "title": SUPPORTED_PROCEDURES[manifest["procedure_code"]],
            "effective_from": min(source["effective_from"] for source in registry_sources.values()),
            "metadata": json.dumps({"scenario_code": manifest.get("scenario_code", "STANDARD")}), "package_id": package_id,
        })
        source_versions: dict[str, str] = {}
        document_count = 0
        chunk_count = 0
        for document in manifest["documents"]:
            source = registry_sources[document["source_code"]]
            contents, filename, content_type = await _fetch_approved_source(source)
            digest = hashlib.sha256(contents).hexdigest()
            raw_path = raw_dir / f"{digest[:16]}-{filename}"
            normalized_path = normalized_dir / f"{digest}.txt"
            raw_path.write_bytes(contents)
            normalized = normalize_bytes(contents, filename, content_type)
            verify_source_content(source, normalized)
            normalized_path.write_text(normalized, encoding="utf-8")
            chunks = chunk_text(normalized)
            vectors = [await embedder.embed(chunk.content) for chunk in chunks]
            source_file_id = await connection.scalar(text("""
                INSERT INTO source_file (file_code, original_name, storage_path, mime_type, size_bytes, sha256, source_url, source_name, downloaded_at)
                VALUES (:file_code, :original_name, :storage_path, :mime_type, :size_bytes, :sha256, :source_url, :source_name, :downloaded_at)
                ON CONFLICT (file_code) DO UPDATE SET storage_path = EXCLUDED.storage_path, sha256 = EXCLUDED.sha256
                RETURNING id
            """), {"file_code": f"FILE_{digest[:16].upper()}", "original_name": filename, "storage_path": relative_storage_path(data_dir, raw_path), "mime_type": mimetypes.guess_type(filename)[0] or "application/octet-stream", "size_bytes": len(contents), "sha256": digest, "source_url": source["canonical_url"], "source_name": source["issuing_authority_vi"], "downloaded_at": datetime.now().astimezone()})
            legal_source_id = await connection.scalar(text("""
                INSERT INTO legal_source (source_code, source_type, issuing_authority_vi, document_number, title_vi)
                VALUES (:source_code, :source_type, :authority, :document_number, :title)
                ON CONFLICT (source_code) DO UPDATE SET title_vi = EXCLUDED.title_vi RETURNING id
            """), {"source_code": source["source_code"], "source_type": source["source_type"], "authority": source["issuing_authority_vi"], "document_number": source["document_number"], "title": source["title_vi"]})
            source_version_id = await connection.scalar(text("""
                INSERT INTO legal_source_version (legal_source_id, version_no, source_file_id, effective_from, effective_to, source_url, extracted_text_path, status)
                VALUES (:legal_source_id, :version, :source_file_id, :effective_from, :effective_to, :source_url, :extracted_text_path, 'in_review')
                RETURNING id
            """), {"legal_source_id": legal_source_id, "version": manifest["version_no"], "source_file_id": source_file_id, "effective_from": source["effective_from"], "effective_to": source["effective_to"], "source_url": source["canonical_url"], "extracted_text_path": relative_storage_path(data_dir, normalized_path)})
            source_versions[source["source_code"]] = str(source_version_id)
            document_id = await connection.scalar(text("""
                INSERT INTO knowledge_document (document_code, legal_source_version_id, procedure_version_id, document_type, language_code, title, normalized_text_path, status)
                VALUES (:code, :source_version_id, :procedure_version_id, 'legal', 'vi', :title, :path, 'in_review')
                RETURNING id
            """), {"code": document["document_code"], "source_version_id": source_version_id, "procedure_version_id": procedure_version_id, "title": source["title_vi"], "path": relative_storage_path(data_dir, normalized_path)})
            for chunk, vector in zip(chunks, vectors, strict=True):
                await connection.execute(text("""
                    INSERT INTO knowledge_chunk (knowledge_document_id, chunk_no, chunk_type, hierarchy_path, title, content, token_count, embedding)
                    VALUES (:document_id, :chunk_no, :chunk_type, CAST(:hierarchy_path AS jsonb), :title, :content, :token_count, CAST(:embedding AS vector))
                """), {"document_id": document_id, "chunk_no": chunk.chunk_no, "chunk_type": chunk.chunk_type, "hierarchy_path": json.dumps(chunk.hierarchy_path), "title": chunk.title, "content": chunk.content, "token_count": chunk.token_count, "embedding": "[" + ",".join(str(value) for value in vector) + "]"})
            document_count += 1
            chunk_count += len(chunks)
        for fact in manifest["procedure_facts"]:
            await connection.execute(text("""
                INSERT INTO procedure_fact (procedure_version_id, fact_type, value, effective_from, legal_source_version_id, status, metadata)
                VALUES (:procedure_version_id, :fact_type, CAST(:value AS jsonb), :effective_from, :source_version_id, 'in_review', CAST(:metadata AS jsonb))
            """), {"procedure_version_id": procedure_version_id, "fact_type": fact["fact_type"], "value": json.dumps(fact["value"]), "effective_from": min(source["effective_from"] for source in registry_sources.values()), "source_version_id": source_versions[fact["source_code"]], "metadata": json.dumps({"section_reference": fact["section_reference"], "claim_id": fact.get("claim_id", fact["fact_type"])})})
    return {"package_code": manifest["package_code"], "documents": document_count, "chunks": chunk_count}


async def publish_package(engine: AsyncEngine, package_code: str, version_no: int) -> None:
    async with engine.begin() as connection:
        package = (await connection.execute(text("""
            SELECT id, metadata FROM knowledge_package
            WHERE package_code = :code AND version_no = :version AND status = 'in_review' FOR UPDATE
        """), {"code": package_code, "version": version_no})).mappings().one_or_none()
        if package is None:
            raise PackageError("package_not_in_review")
        if not package["metadata"].get("evaluation_passed", False):
            raise PackageError("package_evaluation_required")
        document_count = await connection.scalar(text("""
            SELECT count(*) FROM knowledge_document kd JOIN procedure_version pv ON pv.id = kd.procedure_version_id
            WHERE pv.knowledge_package_id = :package_id AND kd.status = 'in_review'
        """), {"package_id": package["id"]})
        chunk_count = await connection.scalar(text("""
            SELECT count(*) FROM knowledge_chunk kc JOIN knowledge_document kd ON kd.id = kc.knowledge_document_id
            JOIN procedure_version pv ON pv.id = kd.procedure_version_id WHERE pv.knowledge_package_id = :package_id AND kc.embedding IS NOT NULL
        """), {"package_id": package["id"]})
        if not document_count or not chunk_count:
            raise PackageError("package_requires_documents_and_embeddings")
        fact_count = await connection.scalar(text("""
            SELECT count(*) FROM procedure_fact WHERE procedure_version_id IN
                (SELECT id FROM procedure_version WHERE knowledge_package_id = :package_id)
        """), {"package_id": package["id"]})
        if not fact_count:
            raise PackageError("package_requires_reviewed_procedure_facts")
        await connection.execute(text("UPDATE knowledge_package SET status = 'published', published_at = now() WHERE id = :id"), {"id": package["id"]})
        await connection.execute(text("UPDATE procedure_version SET status = 'published' WHERE knowledge_package_id = :id"), {"id": package["id"]})
        await connection.execute(text("UPDATE procedure_fact SET status = 'published' WHERE procedure_version_id IN (SELECT id FROM procedure_version WHERE knowledge_package_id = :id)"), {"id": package["id"]})
        await connection.execute(text("UPDATE knowledge_document SET status = 'published' WHERE procedure_version_id IN (SELECT id FROM procedure_version WHERE knowledge_package_id = :id)"), {"id": package["id"]})
        await connection.execute(text("UPDATE legal_source_version SET status = 'published' WHERE id IN (SELECT legal_source_version_id FROM knowledge_document WHERE procedure_version_id IN (SELECT id FROM procedure_version WHERE knowledge_package_id = :id))"), {"id": package["id"]})


async def record_package_evaluation(engine: AsyncEngine, package_code: str, version_no: int, report: dict) -> None:
    profile = report.get("profile")
    if report.get("package_code") != package_code or report.get("passed") is not True or profile not in {"demo", "standard"}:
        raise PackageError("evaluation_report_not_passing")
    async with engine.begin() as connection:
        result = await connection.execute(text("""
            UPDATE knowledge_package
            SET metadata = metadata || CAST(:metadata AS jsonb)
            WHERE package_code = :code AND version_no = :version AND status = 'in_review'
        """), {
            "code": package_code,
            "version": version_no,
            "metadata": json.dumps({
                "evaluation_passed": True,
                "evaluation_case_count": report.get("case_count", 0),
                "release_profile": profile,
            }),
        })
        if not result.rowcount:
            raise PackageError("package_not_in_review")
