from collections.abc import Sequence


def ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def brier_score(probabilities: Sequence[float], outcomes: Sequence[bool]) -> float:
    if len(probabilities) != len(outcomes):
        raise ValueError("brier_length_mismatch")
    return sum((probability - float(outcome)) ** 2 for probability, outcome in zip(probabilities, outcomes, strict=True)) / len(probabilities) if probabilities else 0.0


def expected_calibration_error(probabilities: Sequence[float], outcomes: Sequence[bool], bins: int = 10) -> float:
    if len(probabilities) != len(outcomes):
        raise ValueError("ece_length_mismatch")
    if bins < 1:
        raise ValueError("ece_bins_invalid")
    total = len(probabilities)
    if not total:
        return 0.0
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        values = [(score, outcome) for score, outcome in zip(probabilities, outcomes, strict=True) if lower <= score < upper or (index == bins - 1 and score == 1.0)]
        if values:
            confidence = sum(score for score, _ in values) / len(values)
            accuracy = sum(float(outcome) for _, outcome in values) / len(values)
            error += (len(values) / total) * abs(confidence - accuracy)
    return error
