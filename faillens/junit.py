from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import RunMetadata, TestResult


SUPPORTED_ARTIFACTS = {".png", ".jpg", ".jpeg", ".webp", ".html", ".log", ".txt", ".json"}
TEXT_ARTIFACTS = {".html", ".log", ".txt", ".json"}


def discover_junit_files(inputs: list[str]) -> list[Path]:
    files: set[Path] = set()
    for raw in inputs:
        path = Path(raw).expanduser().resolve()
        if path.is_file() and path.suffix.lower() == ".xml":
            files.add(path)
        elif path.is_dir():
            files.update(p for p in path.rglob("*.xml") if p.is_file())
        else:
            raise FileNotFoundError(f"输入不存在或不是 XML/目录：{raw}")
    return sorted(files)


def _metadata_for(xml_path: Path) -> RunMetadata:
    metadata_path = xml_path.with_name("run.json")
    payload: dict[str, object] = {}
    if metadata_path.exists():
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"无法读取运行元数据 {metadata_path}: {exc}") from exc
    return RunMetadata(
        run_id=str(payload.get("run_id") or xml_path.parent.name or xml_path.stem),
        source=str(xml_path),
        timestamp=_optional_str(payload.get("timestamp")),
        commit=_optional_str(payload.get("commit")),
        branch=_optional_str(payload.get("branch")),
        environment=_optional_str(payload.get("environment")),
    )


def _optional_str(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_")


def _find_artifacts(xml_path: Path, classname: str, name: str) -> list[Path]:
    root = xml_path.parent / "artifacts"
    if not root.is_dir():
        return []
    candidates = {
        _safe_name(name).lower(),
        _safe_name(f"{classname}.{name}").lower(),
        _safe_name(f"{classname}::{name}").lower(),
    }
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_ARTIFACTS:
            continue
        parent_key = _safe_name(path.parent.name).lower()
        stem_key = _safe_name(path.stem).lower()
        if path.parent == root or parent_key in candidates or any(key in stem_key for key in candidates):
            found.append(path)
    return sorted(found)


def _read_artifact_text(paths: list[Path], limit: int = 40_000) -> str:
    chunks: list[str] = []
    remaining = limit
    for path in paths:
        if path.suffix.lower() not in TEXT_ARTIFACTS or remaining <= 0:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")[:remaining]
        except OSError:
            continue
        chunks.append(f"[附件 {path.name}]\n{content}")
        remaining -= len(content)
    return "\n".join(chunks)


def parse_junit(xml_path: Path) -> list[TestResult]:
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        raise ValueError(f"JUnit XML 格式错误 {xml_path}: {exc}") from exc

    run = _metadata_for(xml_path)
    results: list[TestResult] = []
    for case in tree.getroot().iter("testcase"):
        name = case.attrib.get("name", "unnamed")
        classname = case.attrib.get("classname", "")
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        problem = failure if failure is not None else error
        if problem is not None:
            status = "failed" if failure is not None else "error"
        elif skipped is not None:
            status = "skipped"
        else:
            status = "passed"
        try:
            duration = float(case.attrib.get("time", "0") or 0)
        except ValueError:
            duration = 0.0
        message = problem.attrib.get("message", "") if problem is not None else ""
        stacktrace = (problem.text or "").strip() if problem is not None else ""
        stdout = (case.findtext("system-out") or "").strip()
        stderr = (case.findtext("system-err") or "").strip()
        test_id = f"{classname}::{name}" if classname else name
        artifact_paths = _find_artifacts(xml_path, classname, name)
        results.append(
            TestResult(
                test_id=test_id,
                name=name,
                classname=classname,
                status=status,
                duration=duration,
                run=run,
                message=message,
                stacktrace=stacktrace,
                stdout=stdout,
                stderr=stderr,
                artifact_paths=artifact_paths,
                artifact_text=_read_artifact_text(artifact_paths),
            )
        )
    return results


def load_results(inputs: list[str]) -> tuple[list[TestResult], list[RunMetadata]]:
    xml_files = discover_junit_files(inputs)
    if not xml_files:
        raise ValueError("没有找到 JUnit XML 文件")
    results: list[TestResult] = []
    runs: list[RunMetadata] = []
    for xml_file in xml_files:
        parsed = parse_junit(xml_file)
        if not parsed:
            continue
        results.extend(parsed)
        runs.append(parsed[0].run)
    if not results:
        raise ValueError("JUnit XML 中没有 testcase")
    return results, runs

