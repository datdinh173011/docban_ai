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
    "prompts/form_filling.txt",
    "procedure_selection.json",
    "form_guidance.json",
)


@dataclass(frozen=True)
class SelectionFilter:
    attribute: str
    label: str
    question: str


_DATA_TYPES = {"string", "date", "enum", "number", "table"}
_SEVERITIES = {"blocking_error", "warning", "suggestion", "unable_to_verify"}
_ALIGNS = {"left", "right", "center"}


@dataclass(frozen=True)
class FormFieldValidation:
    regex: str | None
    enum_values: tuple[str, ...] | None
    max_length: int | None
    not_future_date: bool
    rule_code: str
    severity: str
    message_vi: str
    suggestion_vi: str | None


@dataclass(frozen=True)
class FormFieldExport:
    page: int
    x: float
    y: float
    width: float
    height: float
    font_family: str
    font_size: float
    align: str
    format: str
    overflow_policy: str


@dataclass(frozen=True)
class FormField:
    field_code: str
    label_vi: str
    group_code: str
    data_type: str
    required: bool
    do_not_infer: bool
    validation: FormFieldValidation
    export: FormFieldExport | None


@dataclass(frozen=True)
class FormGroup:
    group_code: str
    label_vi: str
    display_order: int


@dataclass(frozen=True)
class FormCandidate:
    form_code: str
    title_vi: str
    source_pdf: str
    scenario_excerpt: str
    groups: tuple[FormGroup, ...]
    fields: tuple[FormField, ...]

    def field_by_code(self, field_code: str) -> FormField | None:
        return next((field for field in self.fields if field.field_code == field_code), None)


@dataclass(frozen=True)
class FormMapping:
    form_code: str
    match_procedure_codes: tuple[str, ...]
    match_keywords: tuple[str, ...]


@dataclass(frozen=True)
class ProcedureSettings:
    directory: Path
    grounded_response_prompt: str
    procedure_conversation_prompt: str
    form_filling_prompt: str
    selection_filters: tuple[SelectionFilter, ...]
    locality_question: str
    max_quick_replies: int
    form_guidance: dict[str, Any]
    form_candidates: dict[str, FormCandidate]
    form_mappings: tuple[FormMapping, ...]


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


def _form_field_validation(payload: dict[str, Any], field_code: str) -> FormFieldValidation:
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        raise ValueError(f"form_field_validation_missing:{field_code}")
    severity = validation.get("severity")
    rule_code, message_vi = validation.get("rule_code"), validation.get("message_vi")
    if severity not in _SEVERITIES or not isinstance(rule_code, str) or not rule_code.strip() or not isinstance(message_vi, str) or not message_vi.strip():
        raise ValueError(f"form_field_validation_invalid:{field_code}")
    enum_values = validation.get("enum_values")
    if enum_values is not None and (not isinstance(enum_values, list) or not all(isinstance(value, str) for value in enum_values)):
        raise ValueError(f"form_field_validation_enum_invalid:{field_code}")
    return FormFieldValidation(
        regex=validation.get("regex"),
        enum_values=tuple(enum_values) if enum_values else None,
        max_length=validation.get("max_length"),
        not_future_date=bool(validation.get("not_future_date", False)),
        rule_code=rule_code.strip(),
        severity=severity,
        message_vi=message_vi.strip(),
        suggestion_vi=validation.get("suggestion_vi"),
    )


def _form_field_export(payload: dict[str, Any], field_code: str) -> FormFieldExport | None:
    export = payload.get("export")
    if export is None:
        return None
    if not isinstance(export, dict):
        raise ValueError(f"form_field_export_invalid:{field_code}")
    try:
        align, overflow_policy = export["align"], export["overflow_policy"]
        if align not in _ALIGNS or overflow_policy != "reject":
            raise ValueError(f"form_field_export_invalid:{field_code}")
        return FormFieldExport(
            page=int(export["page"]), x=float(export["x"]), y=float(export["y"]),
            width=float(export["width"]), height=float(export["height"]),
            font_family=str(export["font_family"]), font_size=float(export["font_size"]),
            align=align, format=str(export["format"]), overflow_policy=overflow_policy,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"form_field_export_invalid:{field_code}") from exc


def _form_field(payload: dict[str, Any], group_codes: set[str]) -> FormField:
    field_code, label_vi, group_code, data_type = (
        payload.get("field_code"), payload.get("label_vi"), payload.get("group_code"), payload.get("data_type"),
    )
    if not isinstance(field_code, str) or not field_code.strip():
        raise ValueError("form_field_code_invalid")
    if not isinstance(label_vi, str) or not label_vi.strip():
        raise ValueError(f"form_field_label_invalid:{field_code}")
    if group_code not in group_codes:
        raise ValueError(f"form_field_group_invalid:{field_code}")
    if data_type not in _DATA_TYPES:
        raise ValueError(f"form_field_data_type_invalid:{field_code}")
    return FormField(
        field_code=field_code,
        label_vi=label_vi.strip(),
        group_code=group_code,
        data_type=data_type,
        required=bool(payload.get("required", False)),
        do_not_infer=bool(payload.get("do_not_infer", True)),
        validation=_form_field_validation(payload, field_code),
        export=_form_field_export(payload, field_code),
    )


def _form_candidate(payload: dict[str, Any]) -> FormCandidate:
    form_code, title_vi, source_pdf, scenario_excerpt = (
        payload.get("form_code"), payload.get("title_vi"), payload.get("source_pdf"), payload.get("scenario_excerpt"),
    )
    if not isinstance(form_code, str) or not form_code.strip():
        raise ValueError("form_candidate_code_invalid")
    if not isinstance(title_vi, str) or not title_vi.strip() or not isinstance(source_pdf, str) or not source_pdf.strip():
        raise ValueError(f"form_candidate_metadata_invalid:{form_code}")
    if not isinstance(scenario_excerpt, str) or not scenario_excerpt.strip():
        raise ValueError(f"form_candidate_scenario_excerpt_invalid:{form_code}")
    raw_groups = payload.get("groups")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError(f"form_candidate_groups_required:{form_code}")
    groups: list[FormGroup] = []
    seen_groups: set[str] = set()
    for entry in raw_groups:
        group_code, label_vi, display_order = entry.get("group_code"), entry.get("label_vi"), entry.get("display_order")
        if not isinstance(group_code, str) or group_code in seen_groups or not isinstance(label_vi, str) or not label_vi.strip() or not isinstance(display_order, int):
            raise ValueError(f"form_candidate_group_invalid:{form_code}")
        seen_groups.add(group_code)
        groups.append(FormGroup(group_code, label_vi.strip(), display_order))
    raw_fields = payload.get("fields")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise ValueError(f"form_candidate_fields_required:{form_code}")
    fields: list[FormField] = []
    seen_fields: set[str] = set()
    for entry in raw_fields:
        field = _form_field(entry, seen_groups)
        if field.field_code in seen_fields:
            raise ValueError(f"form_candidate_field_duplicate:{form_code}:{field.field_code}")
        seen_fields.add(field.field_code)
        fields.append(field)
    return FormCandidate(
        form_code=form_code,
        title_vi=title_vi.strip(),
        source_pdf=source_pdf.strip(),
        scenario_excerpt=scenario_excerpt.strip(),
        groups=tuple(groups),
        fields=tuple(fields),
    )


def _form_candidates(payload: dict[str, Any]) -> tuple[dict[str, FormCandidate], tuple[FormMapping, ...]]:
    if payload.get("version") != 1:
        raise ValueError("form_guidance_version_unsupported")
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("form_guidance_candidates_required")
    candidates: dict[str, FormCandidate] = {}
    for entry in raw_candidates:
        if not isinstance(entry, dict):
            raise ValueError("form_guidance_candidate_invalid")
        candidate = _form_candidate(entry)
        if candidate.form_code in candidates:
            raise ValueError(f"form_guidance_candidate_duplicate:{candidate.form_code}")
        candidates[candidate.form_code] = candidate
    raw_mappings = payload.get("mappings")
    if not isinstance(raw_mappings, list):
        raise ValueError("form_guidance_mappings_required")
    mappings: list[FormMapping] = []
    for entry in raw_mappings:
        if not isinstance(entry, dict):
            raise ValueError("form_guidance_mapping_invalid")
        form_code = entry.get("form_code")
        if form_code not in candidates:
            raise ValueError(f"form_guidance_mapping_unknown_form_code:{form_code}")
        procedure_codes, keywords = entry.get("match_procedure_codes", []), entry.get("match_keywords", [])
        if not isinstance(procedure_codes, list) or not isinstance(keywords, list):
            raise ValueError(f"form_guidance_mapping_matchers_invalid:{form_code}")
        mappings.append(FormMapping(form_code, tuple(procedure_codes), tuple(keywords)))
    return candidates, tuple(mappings)


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
    form_candidates, form_mappings = _form_candidates(form_guidance)
    digest = hashlib.sha256("".join(_read_text(directory, path) for path in _REQUIRED_FILES).encode()).hexdigest()[:12]
    logger.info("procedure_settings_loaded directory=%s checksum=%s", directory, digest)
    return ProcedureSettings(
        directory=directory,
        grounded_response_prompt=_read_text(directory, "prompts/grounded_response.txt"),
        procedure_conversation_prompt=_read_text(directory, "prompts/procedure_conversation.txt"),
        form_filling_prompt=_read_text(directory, "prompts/form_filling.txt"),
        selection_filters=filters,
        locality_question=locality["question"].strip(),
        max_quick_replies=selection["max_quick_replies"],
        form_guidance=form_guidance,
        form_candidates=form_candidates,
        form_mappings=form_mappings,
    )


@lru_cache
def get_procedure_settings() -> ProcedureSettings:
    """Cache one immutable bundle for the lifetime of a backend process."""
    return load_procedure_settings()
