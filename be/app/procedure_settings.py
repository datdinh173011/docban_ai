"""Validated prompt and taxonomy assets for the procedure RAG runtime."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_RECORD_ATTRIBUTES = {"group", "field", "request_type", "scenario", "audience"}
_REQUIRED_FILES = (
    "prompts/grounded_response.txt",
    "prompts/procedure_conversation.txt",
    "procedure_selection.json",
    "form_guidance.json",
)


@dataclass(frozen=True)
class SelectionFilter:
    attribute: str
    label: str
    question: str


@dataclass(frozen=True)
class ProcedureSettings:
    directory: Path
    grounded_response_prompt: str
    procedure_conversation_prompt: str
    selection_filters: tuple[SelectionFilter, ...]
    locality_question: str
    max_quick_replies: int
    form_guidance: dict[str, Any]


def _default_directory() -> Path:
    return Path(__file__).resolve().with_name("settings")


def _settings_directory() -> Path:
    configured = os.getenv("PROCEDURE_SETTINGS_DIR")
    return Path(configured).resolve() if configured else _default_directory()


def _read_text(directory: Path, relative_path: str) -> str:
    path = directory / relative_path
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise ValueError(f"procedure_settings_file_missing:{relative_path}") from exc
    if not value:
        raise ValueError(f"procedure_settings_file_empty:{relative_path}")
    return value


def _read_json(directory: Path, relative_path: str) -> dict[str, Any]:
    try:
        payload = json.loads(_read_text(directory, relative_path))
    except json.JSONDecodeError as exc:
        raise ValueError(f"procedure_settings_json_invalid:{relative_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"procedure_settings_json_object_required:{relative_path}")
    return payload


def _selection_filters(payload: dict[str, Any]) -> tuple[SelectionFilter, ...]:
    if payload.get("version") != 1:
        raise ValueError("procedure_selection_version_unsupported")
    maximum = payload.get("max_quick_replies")
    if not isinstance(maximum, int) or not 1 <= maximum <= 7:
        raise ValueError("procedure_selection_max_quick_replies_invalid")
    entries = payload.get("filters")
    if not isinstance(entries, list) or not entries:
        raise ValueError("procedure_selection_filters_required")
    filters: list[SelectionFilter] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("procedure_selection_filter_invalid")
        attribute, label, question = entry.get("attribute"), entry.get("label"), entry.get("question")
        if attribute not in _RECORD_ATTRIBUTES or attribute in seen:
            raise ValueError("procedure_selection_filter_attribute_invalid")
        if not isinstance(label, str) or not label.strip() or not isinstance(question, str) or not question.strip():
            raise ValueError("procedure_selection_filter_text_invalid")
        seen.add(attribute)
        filters.append(SelectionFilter(attribute, label.strip(), question.strip()))
    return tuple(filters)


def load_procedure_settings(directory: Path | None = None) -> ProcedureSettings:
    directory = (directory or _settings_directory()).resolve()
    if not directory.is_dir():
        raise ValueError(f"procedure_settings_directory_missing:{directory}")
    missing = [relative_path for relative_path in _REQUIRED_FILES if not (directory / relative_path).is_file()]
    if missing:
        raise ValueError(f"procedure_settings_bundle_incomplete:{','.join(missing)}")
    selection = _read_json(directory, "procedure_selection.json")
    filters = _selection_filters(selection)
    locality = selection.get("locality")
    if not isinstance(locality, dict) or not isinstance(locality.get("question"), str) or not locality["question"].strip():
        raise ValueError("procedure_selection_locality_invalid")
    form_guidance = _read_json(directory, "form_guidance.json")
    if form_guidance.get("version") != 1 or not isinstance(form_guidance.get("candidates"), list) or not isinstance(form_guidance.get("mappings"), list):
        raise ValueError("form_guidance_schema_invalid")
    digest = hashlib.sha256("".join(_read_text(directory, path) for path in _REQUIRED_FILES).encode()).hexdigest()[:12]
    logger.info("procedure_settings_loaded directory=%s checksum=%s", directory, digest)
    return ProcedureSettings(
        directory=directory,
        grounded_response_prompt=_read_text(directory, "prompts/grounded_response.txt"),
        procedure_conversation_prompt=_read_text(directory, "prompts/procedure_conversation.txt"),
        selection_filters=filters,
        locality_question=locality["question"].strip(),
        max_quick_replies=selection["max_quick_replies"],
        form_guidance=form_guidance,
    )


@lru_cache
def get_procedure_settings() -> ProcedureSettings:
    """Cache one immutable bundle for the lifetime of a backend process."""
    return load_procedure_settings()
