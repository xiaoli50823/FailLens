from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from .diagnosis import diagnose
from .models import AnalysisReport, TestAnalysis, TestHistory, TestResult


def _history(results: list[TestResult]) -> list[TestHistory]:
    grouped: dict[str, list[TestResult]] = defaultdict(list)
    for result in results:
        grouped[result.test_id].append(result)

    histories: list[TestHistory] = []
    for test_id, items in grouped.items():
        passed = sum(item.status == "passed" for item in items)
        failed = sum(item.status in {"failed", "error"} for item in items)
        skipped = sum(item.status == "skipped" for item in items)
        executed = passed + failed
        failure_rate = failed / executed if executed else 0.0
        status_changes = sum(a.status != b.status for a, b in zip(items, items[1:]))
        change_factor = status_changes / max(1, len(items) - 1)
        flaky_score = 0.0
        is_flaky = passed > 0 and failed > 0
        if is_flaky:
            balance = 1.0 - abs(0.5 - failure_rate) * 2
            flaky_score = min(1.0, 0.65 * balance + 0.35 * change_factor)
        histories.append(
            TestHistory(
                test_id=test_id,
                name=items[-1].name,
                classname=items[-1].classname,
                runs=len(items),
                passed=passed,
                failed=failed,
                skipped=skipped,
                failure_rate=round(failure_rate, 3),
                flaky_score=round(flaky_score, 3),
                is_flaky=is_flaky,
                latest_status=items[-1].status,
            )
        )
    return sorted(histories, key=lambda h: (h.is_flaky, h.flaky_score, h.failed), reverse=True)


def analyze(
    results: list[TestResult],
    runs,
    inputs: list[str],
    project: str,
    min_confidence: float = 0.45,
) -> AnalysisReport:
    analyses = [TestAnalysis(result=result, diagnosis=diagnose(result)) for result in results]
    return AnalysisReport(
        project=project,
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        inputs=inputs,
        runs=runs,
        results=analyses,
        histories=_history(results),
        min_confidence=min_confidence,
    )

