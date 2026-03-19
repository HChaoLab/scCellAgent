from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .documentation import ToolDocEntry


@dataclass(slots=True)
class ReviewDecision:
    status: str
    reason: str
    next_action: str


@dataclass(slots=True)
class ReviewBundle:
    technical_ok: bool
    biological_ok: bool
    visual_ok: bool
    summary: str


class ReviewEngine:
    def __init__(self, max_technical_retries: int, max_hypothesis_retries: int) -> None:
        self.max_technical_retries = max_technical_retries
        self.max_hypothesis_retries = max_hypothesis_retries

    def decide(
        self,
        technical_ok: bool,
        biological_ok: bool,
        technical_retry_count: int,
        hypothesis_retry_count: int,
        visual_ok: bool = True,
    ) -> ReviewDecision:
        if not technical_ok or not visual_ok:
            if technical_retry_count >= self.max_technical_retries:
                return ReviewDecision("stop", "技术或视觉迭代次数已达上限", "人工复核")
            return ReviewDecision("retry_technical", "技术结果或图形质量不合格", "修复代码并重跑")

        if not biological_ok:
            if hypothesis_retry_count >= self.max_hypothesis_retries:
                return ReviewDecision("stop", "假设迭代次数已达上限", "人工复核")
            return ReviewDecision("retry_hypothesis", "生物学解释不充分", "调整假设与分析重点")

        return ReviewDecision("accept", "技术、视觉和生物学评价均通过", "进入下一步")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDocEntry] = {}

    def register(self, package: str, symbols: list[str], description: str = "") -> None:
        self._tools[package] = ToolDocEntry(
            package=package,
            symbols=symbols,
            description=description or f"Registered tool package {package}.",
        )

    def as_prompt_text(self) -> str:
        lines: list[str] = []
        for package, entry in sorted(self._tools.items()):
            symbol_text = ", ".join(entry.symbols)
            lines.append(f"- {package}: {symbol_text} | {entry.description}")
        return "\n".join(lines)

    @property
    def allowed_imports(self) -> set[str]:
        return set(self._tools)

    def snapshot(self) -> dict[str, list[str]]:
        return {package: entry.symbols for package, entry in self._tools.items()}

    def doc_entries(self) -> list[ToolDocEntry]:
        return list(self._tools.values())


class MetadataInspector:
    @staticmethod
    def summarize(
        obs_columns: list[str],
        var_columns: list[str],
        uns_keys: list[str],
        n_obs: int | None = None,
        n_vars: int | None = None,
        sample_notes: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "obs_columns": obs_columns,
            "var_columns": var_columns,
            "uns_keys": uns_keys,
            "n_obs": n_obs,
            "n_vars": n_vars,
            "sample_notes": sample_notes or [],
        }
