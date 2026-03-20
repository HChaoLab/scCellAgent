from pathlib import Path

from sc_cell_agent.agent import CellAnalysisAgent, LocalPythonExecutor
from sc_cell_agent.config import AgentConfig
from sc_cell_agent.documentation import ToolDocumentation
from sc_cell_agent.planner import ReviewEngine
from sc_cell_agent.prompts import PromptBuilder
from sc_cell_agent.validator import CodeValidator


class DummyLLM:
    def generate(self, prompt: str) -> str:
        if "最小任务" in prompt:
            return "import math\nvalue = math.sqrt(4)\nprint(value)"
        if "分析假设" in prompt:
            return "假设1: 存在应激相关免疫亚群\n步骤1: QC"
        return "- 一致点: 背景和数据都提到了细胞元数据"


class DummyVision:
    def review_image(self, prompt: str, image_path: Path) -> str:
        return f'{{"visual_ok": true, "issues": [], "suggestions": ["继续沿用当前配色"], "image": "{image_path.name}"}}'


def test_validator_blocks_unknown_variable() -> None:
    validator = CodeValidator(allowed_imports={"math"}, known_variables={"adata"})
    result = validator.validate("import math\nprint(not_defined_name)")
    assert result.ok is False
    assert any("未定义变量" in item for item in result.errors)


def test_review_engine_routes_retry_types() -> None:
    engine = ReviewEngine(max_technical_retries=2, max_hypothesis_retries=1)
    technical = engine.decide(False, True, technical_retry_count=0, hypothesis_retry_count=0)
    biological = engine.decide(True, False, technical_retry_count=0, hypothesis_retry_count=0)
    visual = engine.decide(True, True, technical_retry_count=0, hypothesis_retry_count=0, visual_ok=False)
    assert technical.status == "retry_technical"
    assert biological.status == "retry_hypothesis"
    assert visual.status == "retry_technical"


def test_local_executor_runs_python() -> None:
    executor = LocalPythonExecutor()
    ok, output = executor.run_python("print('ok')")
    assert ok is True
    assert output == "ok"


def test_tool_documentation_auto_appends_missing_tools(tmp_path: Path) -> None:
    config = AgentConfig(project_root=tmp_path)
    doc = ToolDocumentation(config.tool_doc_path)
    agent = CellAnalysisAgent(
        config=config,
        llm_client=DummyLLM(),
        executor=LocalPythonExecutor(),
    )
    agent.registry.register("scanpy", ["pp", "tl", "pl"], "单细胞预处理、分析和可视化。")
    missing = agent.sync_tool_documentation()
    content = doc.as_text()

    assert missing == ["scanpy"]
    assert "## scanpy" in content
    assert "单细胞预处理、分析和可视化。" in content


def test_agent_supports_planning_visual_review_and_tool_docs(tmp_path: Path) -> None:
    config = AgentConfig(project_root=tmp_path)
    image_path = tmp_path / "plot.png"
    image_path.write_text("fake image placeholder", encoding="utf-8")

    agent = CellAnalysisAgent(
        config=config,
        llm_client=DummyLLM(),
        executor=LocalPythonExecutor(),
        vision_client=DummyVision(),
    )
    missing = agent.bootstrap_tools()
    state = agent.initialize_state(
        background_text="肺癌单细胞数据",
        obs_columns=["cell_type", "batch"],
        var_columns=["gene_symbol"],
        uns_keys=["neighbors"],
        n_obs=100,
        n_vars=500,
        sample_notes=["包含治疗前后样本"],
    )
    plan = agent.plan_analysis("肺癌单细胞数据", state, ["免疫微环境", "治疗前后差异"])
    visual = agent.review_visual_output("umap", state, image_path)
    state.key_metrics["cells_after_qc"] = 80
    state.technical_findings.append("未发现语法错误")
    state.biological_findings.append("发现潜在的肿瘤相关免疫亚群")
    outputs = agent.finalize_outputs(state)

    assert sorted(missing) == ["json", "math", "pathlib"]
    assert config.tool_doc_path.exists()
    assert "json" in config.tool_doc_path.read_text(encoding="utf-8")
    assert "假设1" in plan
    assert "visual_ok" in visual
    assert outputs["technical_report"].exists()
    assert outputs["analysis_report"].exists()
    assert outputs["manuscript"].exists()
    assert outputs["tool_documentation"].exists()


def test_task_specific_prompt_templates_include_expected_constraints() -> None:
    state_summary = {"dataset_summary": {"obs_columns": ["cell_type", "cluster"]}}
    tool_reference = "## scanpy\n- symbols: pp, tl, pl"

    qc_prompt = PromptBuilder.build_qc_prompt(state_summary, tool_reference)
    clustering_prompt = PromptBuilder.build_clustering_prompt(state_summary, tool_reference)
    de_prompt = PromptBuilder.build_differential_expression_prompt(state_summary, tool_reference)
    annotation_prompt = PromptBuilder.build_cell_annotation_prompt(state_summary, tool_reference)

    assert "质量控制（QC）" in qc_prompt
    assert "过滤前后细胞数" in qc_prompt
    assert "聚类分析" in clustering_prompt
    assert "resolution" in clustering_prompt
    assert "差异表达分析" in de_prompt
    assert "多重检验校正" in de_prompt
    assert "细胞注释" in annotation_prompt
    assert "候选注释和不确定性说明" in annotation_prompt
