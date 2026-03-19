from __future__ import annotations

import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from .config import AgentConfig
from .memory import AnalysisState, StateStore
from .planner import MetadataInspector, ReviewBundle, ReviewDecision, ReviewEngine, ToolRegistry
from .prompts import PromptBuilder
from .reports import ReportWriter
from .validator import CodeValidator, ValidationResult


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str: ...


class VisionClient(Protocol):
    def review_image(self, prompt: str, image_path: Path) -> str: ...


class ExecutionBackend(Protocol):
    def run_python(self, code: str) -> tuple[bool, str]: ...


class LocalPythonExecutor:
    def run_python(self, code: str) -> tuple[bool, str]:
        process = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        output = "\n".join(part for part in [process.stdout.strip(), process.stderr.strip()] if part)
        return process.returncode == 0, output


class CellAnalysisAgent:
    def __init__(
        self,
        config: AgentConfig,
        llm_client: LLMClient,
        executor: ExecutionBackend,
        vision_client: VisionClient | None = None,
    ) -> None:
        self.config = config
        self.llm_client = llm_client
        self.executor = executor
        self.vision_client = vision_client
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
        sample_notes: list[str] | None = None,
    ) -> AnalysisState:
        state = self.state_store.load()
        state.background_summary = {"background_text": background_text}
        state.dataset_summary = MetadataInspector.summarize(
            obs_columns=obs_columns,
            var_columns=var_columns,
            uns_keys=uns_keys,
            n_obs=n_obs,
            n_vars=n_vars,
            sample_notes=sample_notes,
        )
        state.available_tools = self.registry.snapshot()
        self.state_store.save(state)
        return state

    def verify_alignment(self, background_text: str, state: AnalysisState) -> str:
        prompt = PromptBuilder.build_alignment_prompt(background_text, state.dataset_summary)
        result = self.llm_client.generate(prompt)
        state.technical_findings.append(f"背景-数据核对结果: {result}")
        self.state_store.save(state)
        return result

    def plan_analysis(self, background_text: str, state: AnalysisState, focus_points: list[str]) -> str:
        prompt = PromptBuilder.build_planning_prompt(
            background_text=background_text,
            state_summary=self.state_snapshot(state),
            focus_points=focus_points,
        )
        plan = self.llm_client.generate(prompt)
        state.plan_history.append({"focus_points": focus_points, "plan": plan})
        self.state_store.save(state)
        return plan

    def generate_step_code(self, task_name: str, state: AnalysisState) -> str:
        prompt = PromptBuilder.build_code_prompt(
            task_name=task_name,
            state_summary={
                "dataset_summary": state.dataset_summary,
                "completed_steps": state.completed_steps,
                "available_tools": state.available_tools,
                "generated_files": state.generated_files,
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
            "sample_notes",
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
            state.technical_findings.append(f"步骤 {task_name} 执行成功")
        else:
            state.technical_findings.append(f"步骤 {task_name} 执行失败: {output}")
        self.state_store.save(state)
        return ok, output

    def review_visual_output(self, task_name: str, state: AnalysisState, image_path: Path) -> str:
        if not self.vision_client:
            message = "未配置视觉模型，跳过视觉评审"
            state.visual_findings.append(message)
            self.state_store.save(state)
            return message

        prompt = PromptBuilder.build_visual_review_prompt(task_name, self.state_snapshot(state))
        result = self.vision_client.review_image(prompt, image_path)
        state.visual_findings.append(result)
        self.state_store.remember_file(state, f"visual::{task_name}", image_path)
        return result

    def build_review_bundle(
        self,
        technical_ok: bool,
        biological_ok: bool,
        visual_ok: bool,
        summary: str,
    ) -> ReviewBundle:
        return ReviewBundle(
            technical_ok=technical_ok,
            biological_ok=biological_ok,
            visual_ok=visual_ok,
            summary=summary,
        )

    def review_step(
        self,
        technical_ok: bool,
        biological_ok: bool,
        technical_retry_count: int,
        hypothesis_retry_count: int,
        visual_ok: bool = True,
    ) -> ReviewDecision:
        return self.review_engine.decide(
            technical_ok=technical_ok,
            biological_ok=biological_ok,
            technical_retry_count=technical_retry_count,
            hypothesis_retry_count=hypothesis_retry_count,
            visual_ok=visual_ok,
        )

    def finalize_outputs(self, state: AnalysisState) -> dict[str, Path]:
        tech = self.report_writer.write_technical_report(self.config.technical_report_dir, state)
        analysis = self.report_writer.write_analysis_report(self.config.analysis_report_dir, state)
        manuscript = self.report_writer.write_manuscript(self.config.manuscript_path, state)
        self.state_store.remember_file(state, "technical_report", tech)
        self.state_store.remember_file(state, "analysis_report", analysis)
        self.state_store.remember_file(state, "manuscript", manuscript)
        return {
            "technical_report": tech,
            "analysis_report": analysis,
            "manuscript": manuscript,
        }

    def state_snapshot(self, state: AnalysisState) -> dict[str, object]:
        return asdict(state)
