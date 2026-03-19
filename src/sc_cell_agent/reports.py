from __future__ import annotations

from pathlib import Path

from .memory import AnalysisState


class ReportWriter:
    def write_technical_report(self, output_dir: Path, state: AnalysisState) -> Path:
        path = output_dir / "technical_summary.md"
        path.write_text(
            "\n".join(
                [
                    "# 技术报告",
                    "",
                    "## 质量指标",
                    *[f"- {k}: {v}" for k, v in state.key_metrics.items()],
                    "",
                    "## 技术发现",
                    *[f"- {item}" for item in state.technical_findings],
                    "",
                    "## 视觉发现",
                    *[f"- {item}" for item in state.visual_findings],
                ]
            ),
            encoding="utf-8",
        )
        return path

    def write_analysis_report(self, output_dir: Path, state: AnalysisState) -> Path:
        path = output_dir / "analysis_summary.md"
        path.write_text(
            "\n".join(
                [
                    "# 分析报告",
                    "",
                    "## 生物学发现",
                    *[f"- {item}" for item in state.biological_findings],
                    "",
                    "## 假设历史",
                    *[f"- {item}" for item in state.hypothesis_history],
                    "",
                    "## 已完成步骤",
                    *[f"- {step}" for step in state.completed_steps],
                ]
            ),
            encoding="utf-8",
        )
        return path

    def write_manuscript(self, path: Path, state: AnalysisState) -> Path:
        manuscript = "\n".join(
            [
                "# Title",
                "",
                "## Abstract",
                "待基于 state 自动填充。",
                "",
                "## Introduction",
                "待填充研究背景与前沿。",
                "",
                "## Results",
                *[f"- {item}" for item in state.biological_findings],
                "",
                "## Methods",
                *[f"- {step}" for step in state.completed_steps],
                "",
                "## Data Availability",
                "列出 output/data 中的数据文件。",
                *[f"- {key}: {value}" for key, value in state.generated_files.items()],
                "",
                "## Code Availability",
                "列出 output/code 中的脚本与环境说明。",
            ]
        )
        path.write_text(manuscript, encoding="utf-8")
        return path
