from app.evaluation.contracts import EvaluationCase, EvaluationFailure, EvaluationObservation, EvaluationProfile, EvaluationReport
from app.evaluation.metrics import brier_score, expected_calibration_error, ratio

PRODUCTION_THRESHOLDS = {
    "recall_at_5": 0.95,
    "groundedness": 0.95,
    "band_accuracy": 0.90,
    "brier_score_max": 0.10,
    "ece_max": 0.05,
}


def evaluate(
    package_code: str,
    cases: list[EvaluationCase],
    observations: list[EvaluationObservation],
    strict: bool = False,
    profile: EvaluationProfile = "standard",
) -> EvaluationReport:
    by_case = {observation.case_id: observation for observation in observations}
    failures: list[EvaluationFailure] = []
    recalled = grounded = band_matches = citation_hits = citation_required = 0
    probabilities: list[float] = []
    outcomes: list[bool] = []

    for case in cases:
        observation = by_case.get(case.case_id)
        if observation is None:
            failures.append(EvaluationFailure(case_id=case.case_id, category="data", detail="observation_missing"))
            continue
        required_evidence = set(case.required_evidence_ids)
        retrieved = set(observation.retrieved_evidence_ids[:5])
        if required_evidence.issubset(retrieved):
            recalled += 1
        else:
            failures.append(EvaluationFailure(case_id=case.case_id, category="retrieval", detail="required_evidence_missing"))

        required_citations = set(case.required_citation_ids)
        citations = set(observation.citation_ids)
        citation_hits += len(required_citations & citations)
        citation_required += len(required_citations)
        if case.critical and not required_citations.issubset(citations):
            failures.append(EvaluationFailure(case_id=case.case_id, category="citation", detail="critical_citation_missing"))
        if observation.external_citation_ids and case.critical and observation.answer_strategy in {"high", "medium"}:
            failures.append(EvaluationFailure(case_id=case.case_id, category="external_authority", detail="external_citation_in_legal_answer"))

        forbidden_present = any(claim.lower() in observation.answer_text.lower() for claim in case.forbidden_claims)
        facts_present = set(case.required_fact_ids).issubset(observation.answer_fact_ids)
        is_grounded = facts_present and not forbidden_present and (not case.critical or required_citations.issubset(citations))
        if is_grounded:
            grounded += 1
        else:
            failures.append(EvaluationFailure(case_id=case.case_id, category="groundedness", detail="required_fact_or_citation_missing"))

        if observation.answer_strategy == case.expected_band:
            band_matches += 1
        else:
            failures.append(EvaluationFailure(case_id=case.case_id, category="confidence", detail="confidence_band_mismatch"))
        if case.required_warning and observation.warning != case.required_warning:
            failures.append(EvaluationFailure(case_id=case.case_id, category="warning", detail="required_warning_missing"))
        probabilities.append(observation.confidence_score)
        outcomes.append(case.expected_correct)

    evaluated = len(cases)
    metrics = {
        "recall_at_5": ratio(recalled, evaluated),
        "citation_coverage": ratio(citation_hits, citation_required),
        "groundedness": ratio(grounded, evaluated),
        "band_accuracy": ratio(band_matches, evaluated),
        "brier_score": brier_score(probabilities, outcomes),
        "ece": expected_calibration_error(probabilities, outcomes),
    }
    if profile == "demo":
        reviewed_cases = sum(case.reviewed for case in cases)
        if package_code != "BIRTH_REGISTRATION" or len(cases) != 2 or reviewed_cases != 2:
            failures.append(EvaluationFailure(case_id="DATASET", category="data", detail="demo_dataset_requires_two_reviewed_birth_cases"))
        if metrics["citation_coverage"] < 1.0:
            failures.append(EvaluationFailure(case_id="GATE", category="citation", detail="citation_coverage_below_threshold"))
    elif strict:
        reviewed_cases = sum(case.reviewed for case in cases)
        high = sum(case.expected_band == "high" for case in cases)
        medium = sum(case.expected_band == "medium" for case in cases)
        low = sum(case.expected_band in {"low", "unable_to_verify"} for case in cases)
        if (len(cases), reviewed_cases, high, medium, low) != (70, 70, 35, 18, 17):
            failures.append(EvaluationFailure(case_id="DATASET", category="data", detail="production_dataset_distribution_invalid"))
        if metrics["recall_at_5"] < PRODUCTION_THRESHOLDS["recall_at_5"]:
            failures.append(EvaluationFailure(case_id="GATE", category="retrieval", detail="recall_at_5_below_threshold"))
        if metrics["citation_coverage"] < 1.0:
            failures.append(EvaluationFailure(case_id="GATE", category="citation", detail="citation_coverage_below_threshold"))
        if metrics["groundedness"] < PRODUCTION_THRESHOLDS["groundedness"]:
            failures.append(EvaluationFailure(case_id="GATE", category="groundedness", detail="groundedness_below_threshold"))
        if metrics["band_accuracy"] < PRODUCTION_THRESHOLDS["band_accuracy"]:
            failures.append(EvaluationFailure(case_id="GATE", category="confidence", detail="band_accuracy_below_threshold"))
        if metrics["brier_score"] > PRODUCTION_THRESHOLDS["brier_score_max"]:
            failures.append(EvaluationFailure(case_id="GATE", category="confidence", detail="brier_score_above_threshold"))
        if metrics["ece"] > PRODUCTION_THRESHOLDS["ece_max"]:
            failures.append(EvaluationFailure(case_id="GATE", category="confidence", detail="ece_above_threshold"))
    return EvaluationReport(package_code=package_code, profile=profile, case_count=evaluated, metrics=metrics, failures=failures, passed=not failures)
