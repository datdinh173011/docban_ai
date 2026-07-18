import json
from pathlib import Path

import pytest

from app.procedure_settings import load_procedure_settings


SETTINGS_DIR = Path(__file__).parents[1] / "app" / "settings"


def copy_bundle(destination: Path) -> None:
    for source in SETTINGS_DIR.rglob("*"):
        if source.is_file():
            target = destination / source.relative_to(SETTINGS_DIR)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())


def test_bundled_procedure_settings_are_valid() -> None:
    settings = load_procedure_settings(SETTINGS_DIR)

    assert settings.max_quick_replies == 7
    assert [item.attribute for item in settings.selection_filters] == [
        "group",
        "field",
        "request_type",
        "scenario",
        "audience",
    ]
    assert "EVIDENCE" in settings.grounded_response_prompt


def test_runtime_override_bundle_is_loaded_from_its_directory(tmp_path: Path) -> None:
    override = tmp_path / "runtime_settings"
    copy_bundle(override)
    selection_path = override / "procedure_selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["filters"][0]["question"] = "Câu hỏi override?"
    selection_path.write_text(json.dumps(selection, ensure_ascii=False), encoding="utf-8")

    settings = load_procedure_settings(override)

    assert settings.directory == override.resolve()
    assert settings.selection_filters[0].question == "Câu hỏi override?"


def test_invalid_selection_attribute_rejects_startup_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "settings"
    copy_bundle(bundle)
    selection_path = bundle / "procedure_selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["filters"][0]["attribute"] = "unknown"
    selection_path.write_text(json.dumps(selection, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="procedure_selection_filter_attribute_invalid"):
        load_procedure_settings(bundle)
