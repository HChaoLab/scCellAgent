from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AgentConfig:
    project_root: Path
    max_technical_retries: int = 3
    max_hypothesis_retries: int = 2
    enable_visual_review: bool = True

    @property
    def output_dir(self) -> Path:
        return self.project_root / "output"

    @property
    def code_dir(self) -> Path:
        return self.output_dir / "code"

    @property
    def data_dir(self) -> Path:
        return self.output_dir / "data"

    @property
    def plot_dir(self) -> Path:
        return self.output_dir / "plots"

    @property
    def technical_report_dir(self) -> Path:
        return self.output_dir / "technical_report"

    @property
    def analysis_report_dir(self) -> Path:
        return self.output_dir / "analysis_report"

    @property
    def manuscript_path(self) -> Path:
        return self.output_dir / "manuscript.md"

    @property
    def state_path(self) -> Path:
        return self.output_dir / "state.json"

    def ensure_directories(self) -> None:
        for path in [
            self.output_dir,
            self.code_dir,
            self.data_dir,
            self.plot_dir,
            self.technical_report_dir,
            self.analysis_report_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)
