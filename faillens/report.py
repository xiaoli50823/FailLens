from __future__ import annotations

import json
import shutil
from collections import Counter
from importlib.resources import files
from pathlib import Path
from typing import Any

from .models import AnalysisReport


def _copy_artifacts(report: AnalysisReport, output_dir: Path) -> None:
    artifact_root = output_dir / "artifacts"
    for index, analysis in enumerate(report.results):
        analysis.artifact_links.clear()
        for artifact_index, source in enumerate(analysis.result.artifact_paths, start=1):
            target_dir = artifact_root / f"case-{index + 1}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{artifact_index}-{source.name}"
            shutil.copy2(source, target)
            analysis.artifact_links.append(target.relative_to(output_dir).as_posix())


def _dashboard_payload(report: AnalysisReport) -> dict[str, Any]:
    payload = report.to_dict()
    results = report.results
    failed = [item for item in results if item.result.status in {"failed", "error"}]
    executed = sum(item.result.status != "skipped" for item in results)
    passed = sum(item.result.status == "passed" for item in results)
    flaky = sum(item.is_flaky for item in report.histories)
    pass_rate = passed / executed if executed else 0.0
    health_score = max(0, round((pass_rate * 100) - (flaky / max(1, len(report.histories)) * 15)))
    categories = Counter(item.diagnosis.category if item.diagnosis else "unknown" for item in failed)
    category_labels = {
        item.diagnosis.category: item.diagnosis.label for item in failed if item.diagnosis
    }

    run_trend: list[dict[str, Any]] = []
    for run in report.runs:
        run_results = [item.result for item in results if item.result.run.source == run.source]
        run_total = len(run_results)
        run_passed = sum(item.status == "passed" for item in run_results)
        run_trend.append(
            {
                "run_id": run.run_id,
                "timestamp": run.timestamp,
                "passed": run_passed,
                "failed": sum(item.status in {"failed", "error"} for item in run_results),
                "skipped": sum(item.status == "skipped" for item in run_results),
                "pass_rate": round(run_passed / run_total * 100, 1) if run_total else 0,
            }
        )

    payload["dashboard"] = {
        "health_score": health_score,
        "pass_rate": round(pass_rate * 100, 1),
        "total": len(results),
        "passed": passed,
        "failed": len(failed),
        "skipped": sum(item.result.status == "skipped" for item in results),
        "flaky": flaky,
        "unique_tests": len(report.histories),
        "total_duration": round(sum(item.result.duration for item in results), 3),
        "categories": [
            {"key": key, "label": category_labels.get(key, "暂未识别"), "count": count}
            for key, count in categories.most_common()
        ],
        "run_trend": run_trend,
    }
    return payload


def _render_html(report: AnalysisReport) -> str:
    template = files("faillens").joinpath("templates/report.html").read_text(encoding="utf-8")
    payload = json.dumps(_dashboard_payload(report), ensure_ascii=False).replace("</", "<\\/")
    title = str(report.project).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return template.replace("__REPORT_TITLE__", title).replace("__REPORT_DATA__", payload)


def write_reports(
    report: AnalysisReport, output_dir: Path, copy_artifacts: bool = True
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if copy_artifacts:
        _copy_artifacts(report, output_dir)
    else:
        for analysis in report.results:
            analysis.artifact_links.clear()
    json_path = output_dir / "report.json"
    html_path = output_dir / "report.html"
    json_path.write_text(
        json.dumps(_dashboard_payload(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    html_path.write_text(_render_html(report), encoding="utf-8")
    return html_path, json_path
