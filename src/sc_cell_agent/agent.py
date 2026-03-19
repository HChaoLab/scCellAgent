from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from .config import AgentConfig
from .memory import AnalysisState, StateStore
from .planner import MetadataInspector, ReviewDecision, ReviewEngine, ToolRegistry
from .prompts import PromptBuilder
from .reports import ReportWriter
from .validator import CodeValidator, ValidationResult


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str: ...


class ExecutionBackend(Protocol):
    def run_python(self, code: str) -> tuple[bool, str]: ...


class CellAnalysisAgent:
    def __init__(
        self,
        config: AgentConfig,
        llm_client: LLMClient,
        executor: ExecutionBackend,
    ) -> None:
        self.config = config
        self.llm_client = llm_client
        self.executor = executor
        self.registry = ToolRegistry()
        self.review_engine = ReviewEngine(
            max_technical_retries=config.max_technical_retries,
            max_hypothesis_retries=config.max_hypothesis_retries,
        )
        self.report_writer = ReportWriter()
        self.state_store = StateStore(config.state_path)
        self.config.ensure_directories()

    def bootstrap_tools(self) -> None:
        self.registry.register("json", ["loads", "dumps"])
        self.registry.register("pathlib", ["Path"])
        self.registry.register("math", ["sqrt", "log1p"])

    def initialize_state(
        self,
        background_text: str,
        obs_columns: list[str],
        var_columns: list[str],
        uns_keys: list[str],
        n_obs: int | None = None,
        n_vars: int | None = None,
    ) -> AnalysisState:
        state = self.state_store.load()
        state.background_summary = {"background_text": background_text}
        state.dataset_summary = MetadataInspector.summarize(
            obs_columns=obs_columns,
            var_columns=var_columns,
            uns_keys=uns_keys,
            n_obs=n_obs,
            n_vars=n_vars,
        )
        state.available_tools = self.registry.snapshot()
        self.state_store.save(state)
        return state

    def verify_alignment(self, background_text: str, state: AnalysisState) -> str:
        prompt = PromptBuilder.build_alignment_prompt(background_text, state.dataset_summary)
        return self.llm_client.generate(prompt)

    def generate_step_code(self, task_name: str, state: AnalysisState) -> str:
        prompt = PromptBuilder.build_code_prompt(
            task_name=task_name,
            state_summary={
                "dataset_summary": state.dataset_summary,
                "completed_steps": state.completed_steps,
                "available_tools": state.available_tools,
            },
            tool_reference=self.registry.as_prompt_text(),
        )
        return self.llm_client.generate(prompt)

    def validate_code(self, code: str, state: AnalysisState) -> ValidationResult:
        known_variables = {
            "obs_columns",
            "var_columns",
            "uns_keys",
            "state",
            "Path",
        }
        known_variables |= set(state.dataset_summary.keys())
        validator = CodeValidator(
            allowed_imports=self.registry.allowed_imports,
            known_variables=known_variables,
        )
        return validator.validate(code)

    def execute_step(self, task_name: str, code: str, state: AnalysisState) -> tuple[bool, str]:
        ok, output = self.executor.run_python(code)
        if ok:
            self.state_store.append_step(state, task_name)
        return ok, output

    def review_step(
        self,
        technical_ok: bool,
        biological_ok: bool,
        technical_retry_count: int,
        hypothesis_retry_count: int,
    ) -> ReviewDecision:
        return self.review_engine.decide(
            technical_ok=technical_ok,
            biological_ok=biological_ok,
            technical_retry_count=technical_retry_count,
            hypothesis_retry_count=hypothesis_retry_count,
        )

    def finalize_outputs(self, state: AnalysisState) -> dict[str, Path]:
        tech = self.report_writer.write_technical_report(self.config.technical_report_dir, state)
        analysis = self.report_writer.write_analysis_report(self.config.analysis_report_dir, state)
        manuscript = self.report_writer.write_manuscript(self.config.manuscript_path, state)
        return {
            "technical_report": tech,
            "analysis_report": analysis,
            "manuscript": manuscript,
        }

    def state_snapshot(self, state: AnalysisState) -> dict[str, object]:
        return asdict(state)
