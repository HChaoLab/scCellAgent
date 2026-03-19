from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ReviewDecision:
    status: str
    reason: str
    next_action: str


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
    ) -> ReviewDecision:
        if not technical_ok:
            if technical_retry_count >= self.max_technical_retries:
                return ReviewDecision("stop", "技术迭代次数已达上限", "人工复核")
            return ReviewDecision("retry_technical", "技术结果不合格", "修复代码并重跑")

        if not biological_ok:
            if hypothesis_retry_count >= self.max_hypothesis_retries:
                return ReviewDecision("stop", "假设迭代次数已达上限", "人工复核")
            return ReviewDecision("retry_hypothesis", "生物学解释不充分", "调整假设与分析重点")

        return ReviewDecision("accept", "技术和生物学评价均通过", "进入下一步")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, list[str]] = {}

    def register(self, package: str, symbols: list[str]) -> None:
        self._tools[package] = symbols

    def as_prompt_text(self) -> str:
        lines: list[str] = []
        for package, symbols in sorted(self._tools.items()):
            symbol_text = ", ".join(symbols)
            lines.append(f"- {package}: {symbol_text}")
        return "\n".join(lines)

    @property
    def allowed_imports(self) -> set[str]:
        return set(self._tools)

    def snapshot(self) -> dict[str, list[str]]:
        return dict(self._tools)


class MetadataInspector:
    @staticmethod
    def summarize(
        obs_columns: list[str],
        var_columns: list[str],
        uns_keys: list[str],
        n_obs: int | None = None,
        n_vars: int | None = None,
    ) -> dict[str, Any]:
        return {
            "obs_columns": obs_columns,
            "var_columns": var_columns,
            "uns_keys": uns_keys,
            "n_obs": n_obs,
            "n_vars": n_vars,
        }
