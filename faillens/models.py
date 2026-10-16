from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RunMetadata:
    run_id: str
    source: str
    timestamp: str | None = None
    commit: str | None = None
    branch: str | None = None
    environment: str | None = None


@dataclass(slots=True)
class TestResult:
    test_id: str
    name: str
    classname: str
    status: str
    duration: float
    run: RunMetadata
    message: str = ""
    stacktrace: str = ""
    stdout: str = ""
    stderr: str = ""
    artifact_paths: list[Path] = field(default_factory=list)
    artifact_text: str = ""

    @property
    def diagnostic_text(self) -> str:
        return "\n".join(
            part
            for part in (self.message, self.stacktrace, self.stdout, self.stderr, self.artifact_text)
            if part
        )


@dataclass(slots=True)
class Diagnosis:
    category: str
    label: str
    confidence: float
    summary: str
    evidence: list[str]
    suggestions: list[str]


@dataclass(slots=True)
class TestAnalysis:
    result: TestResult
    diagnosis: Diagnosis | None = None
    artifact_links: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TestHistory:
    test_id: str
    name: str
    classname: str
    runs: int
    passed: int
    failed: int
    skipped: int
    failure_rate: float
    flaky_score: float
    is_flaky: bool
    latest_status: str


@dataclass(slots=True)
class AnalysisReport:
    project: str
    generated_at: str
    inputs: list[str]
    runs: list[RunMetadata]
    results: list[TestAnalysis]
    histories: list[TestHistory]
    min_confidence: float = 0.45

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for item in data["results"]:
            item["result"].pop("artifact_paths", None)
            item["result"].pop("artifact_text", None)
        return data

