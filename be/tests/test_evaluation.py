import json

import pytest

from app.evaluation.contracts import EvaluationCase, EvaluationObservation
from app.evaluation.metrics import brier_score, expected_calibration_error
from app.evaluation.run import load_records, render_markdown
from app.evaluation.runner import evaluate


def case(case_id: str = "BIRTH-EVAL-001", **overrides) -> EvaluationCase:
    values = {
        "case_id": case_id,
        "question": "Căn cứ nào?",
        "procedure_code": "BIRTH_REGISTRATION",
        "expected_paths": ["hybrid_rag"],
        "expected_band": "high",
        "required_evidence_ids": ["chunk-1"],
        "required_citation_ids": ["CIT-1"],
        "required_fact_ids": ["legal_basis"],
        "expected_correct": True,
        "reviewed": True,
    }
    values.update(overrides)
    return EvaluationCase.model_validate(values)


def observation(case_id: str = "BIRTH-EVAL-001", **overrides) -> EvaluationObservation:
    values = {
        "case_id": case_id,
        "retrieved_evidence_ids": ["chunk-1"],
        "citation_ids": ["CIT-1"],
        "answer_fact_ids": ["legal_basis"],
        "answer_text": "Có căn cứ.",
        "answer_strategy": "high",
        "confidence_score": 0.99,
    }
    values.update(overrides)
    return EvaluationObservation.model_validate(values)


def test_metric_formulas_are_deterministic() -> None:
    assert brier_score([1.0, 0.0], [True, False]) == 0.0
    assert expected_calibration_error([1.0, 0.0], [True, False]) == 0.0
    with pytest.raises(ValueError):
        brier_score([0.5], [True, False])


def test_evaluation_reports_missing_critical_citation() -> None:
    report = evaluate("BIRTH_REGISTRATION", [case()], [observation(citation_ids=[])])
    assert report.passed is False
    assert any(failure.category == "citation" for failure in report.failures)


def test_strict_gate_requires_reviewed_seventy_case_distribution() -> None:
    report = evaluate("BIRTH_REGISTRATION", [case()], [observation()], strict=True)
    assert report.passed is False
    assert any(failure.detail == "production_dataset_distribution_invalid" for failure in report.failures)


def test_demo_gate_requires_two_reviewed_birth_cases() -> None:
    report = evaluate("BIRTH_REGISTRATION", [case()], [observation()], profile="demo")

    assert report.passed is False
    assert any(failure.detail == "demo_dataset_requires_two_reviewed_birth_cases" for failure in report.failures)


def test_demo_gate_rejects_external_legal_authority() -> None:
    second_case = case("BIRTH-EVAL-002")
    second_observation = observation("BIRTH-EVAL-002", external_citation_ids=["EXT-1"])

    report = evaluate("BIRTH_REGISTRATION", [case(), second_case], [observation(), second_observation], profile="demo")

    assert report.passed is False
    assert any(failure.category == "external_authority" for failure in report.failures)


def test_fixture_dataset_loads_and_renders_report() -> None:
    from pathlib import Path

    path = Path(__file__).parents[1] / "evaluation" / "datasets" / "birth_registration.fixture.jsonl"
    cases, observations = load_records(path)
    report = evaluate("BIRTH_REGISTRATION", cases, observations, profile="demo")
    rendered = render_markdown(report.model_dump())
    assert report.passed is True
    assert report.profile == "demo"
    assert "Evaluation Report" in rendered


def test_invalid_dataset_record_is_rejected(tmp_path) -> None:
    path = tmp_path / "invalid.jsonl"
    path.write_text(json.dumps({"case": {}}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dataset_record_invalid:1"):
        load_records(path)
