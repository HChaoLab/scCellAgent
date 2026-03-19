from pathlib import Path

from sc_cell_agent.agent import CellAnalysisAgent
from sc_cell_agent.config import AgentConfig
from sc_cell_agent.planner import ReviewEngine
from sc_cell_agent.validator import CodeValidator


class DummyLLM:
    def generate(self, prompt: str) -> str:
        if "最小任务" in prompt:
            return "import math\nvalue = math.sqrt(4)"
        return "- 一致点: 背景和数据都提到了细胞元数据"


class DummyExecutor:
    def run_python(self, code: str) -> tuple[bool, str]:
        namespace: dict[str, object] = {}
        exec(code, {}, namespace)
        return True, str(namespace)


def test_validator_blocks_unknown_variable() -> None:
    validator = CodeValidator(allowed_imports={"math"}, known_variables={"adata"})
    result = validator.validate("import math\nprint(not_defined_name)")
    assert result.ok is False
    assert any("未定义变量" in item for item in result.errors)


def test_review_engine_routes_retry_types() -> None:
    engine = ReviewEngine(max_technical_retries=2, max_hypothesis_retries=1)
    technical = engine.decide(False, True, technical_retry_count=0, hypothesis_retry_count=0)
    biological = engine.decide(True, False, technical_retry_count=0, hypothesis_retry_count=0)
    assert technical.status == "retry_technical"
    assert biological.status == "retry_hypothesis"


def test_agent_bootstrap_and_finalize(tmp_path: Path) -> None:
    config = AgentConfig(project_root=tmp_path)
    agent = CellAnalysisAgent(config=config, llm_client=DummyLLM(), executor=DummyExecutor())
    agent.bootstrap_tools()
    state = agent.initialize_state(
        background_text="肺癌单细胞数据",
        obs_columns=["cell_type", "batch"],
        var_columns=["gene_symbol"],
        uns_keys=["neighbors"],
        n_obs=100,
        n_vars=500,
    )
    state.key_metrics["cells_after_qc"] = 80
    state.technical_findings.append("未发现语法错误")
    state.biological_findings.append("发现潜在的肿瘤相关免疫亚群")
    outputs = agent.finalize_outputs(state)
    assert outputs["technical_report"].exists()
    assert outputs["analysis_report"].exists()
    assert outputs["manuscript"].exists()
