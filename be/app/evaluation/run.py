import argparse
import json
from pathlib import Path

from rich.console import Console

from app.evaluation.contracts import EvaluationCase, EvaluationObservation
from app.evaluation.runner import evaluate

console = Console()


def load_records(path: Path) -> tuple[list[EvaluationCase], list[EvaluationObservation]]:
    cases: list[EvaluationCase] = []
    observations: list[EvaluationObservation] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            cases.append(EvaluationCase.model_validate(record["case"]))
            observations.append(EvaluationObservation.model_validate(record["observation"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"dataset_record_invalid:{line_no}") from exc
    if not cases:
        raise ValueError("dataset_empty")
    return cases, observations


def render_markdown(report: dict) -> str:
    lines = [
        f"# Evaluation Report - {report['package_code']}",
        "",
        f"Status: {'PASS' if report['passed'] else 'FAIL'}",
        "",
        "## Metrics",
        "",
    ]
    lines.extend(f"- `{name}`: {value:.4f}" for name, value in report["metrics"].items())
    lines.extend(["", "## Failures", ""])
    if report["failures"]:
        lines.extend(f"- `{failure['case_id']}` `{failure['category']}`: {failure['detail']}" for failure in report["failures"])
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="ICIVI deterministic RAG quality gate")
    parser.add_argument("--package", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, default=Path("evaluation/reports"))
    parser.add_argument("--strict", action="store_true")
    arguments = parser.parse_args()

    try:
        cases, observations = load_records(arguments.dataset)
        report = evaluate(arguments.package, cases, observations, strict=arguments.strict)
    except ValueError as exc:
        console.print(f"[red]Evaluation dataset invalid:[/red] {exc}")
        raise SystemExit(2) from exc

    arguments.report_dir.mkdir(parents=True, exist_ok=True)
    serialized = report.model_dump()
    (arguments.report_dir / f"{arguments.package.lower()}.json").write_text(json.dumps(serialized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (arguments.report_dir / f"{arguments.package.lower()}.md").write_text(render_markdown(serialized), encoding="utf-8")
    console.print(f"[{'green' if report.passed else 'red'}]{'PASS' if report.passed else 'FAIL'}[/] {arguments.package}: {report.case_count} cases")
    if not report.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
