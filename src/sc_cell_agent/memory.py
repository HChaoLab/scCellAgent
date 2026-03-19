from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AnalysisState:
    dataset_summary: dict[str, Any] = field(default_factory=dict)
    background_summary: dict[str, Any] = field(default_factory=dict)
    completed_steps: list[str] = field(default_factory=list)
    technical_findings: list[str] = field(default_factory=list)
    biological_findings: list[str] = field(default_factory=list)
    generated_files: dict[str, str] = field(default_factory=dict)
    available_tools: dict[str, list[str]] = field(default_factory=dict)
    key_metrics: dict[str, Any] = field(default_factory=dict)
    hypothesis_history: list[dict[str, Any]] = field(default_factory=list)


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AnalysisState:
        if not self.path.exists():
            return AnalysisState()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return AnalysisState(**data)

    def save(self, state: AnalysisState) -> None:
        self.path.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append_step(self, state: AnalysisState, step: str) -> None:
        if step not in state.completed_steps:
            state.completed_steps.append(step)
        self.save(state)
