# scCellAgent

一个面向单细胞分析任务的 Python Agent 脚手架，重点解决以下问题：

- 使用 MiniMax / MinMax 等大模型时的代码幻觉控制。
- 分离“技术迭代”和“生物学假设迭代”。
- 用本地记忆减少 token 消耗。
- 自动沉淀可复用代码、关键数据、关键图、技术报告、分析报告和论文式报告。
- 利用 **MiniMax 视觉模型** 对 QC 图、UMAP、差异表达图等进行二次质量评审。
- 自动检测单细胞分析工具是否缺少说明书，并追加到 `Tool Documentation`。

## 设计原则

1. **先约束，后生成**：不直接让大模型自由写整段分析脚本，而是给出受约束的任务、可用 API 白名单、已有变量和数据字典。
2. **先检查，后执行**：所有模型生成代码都必须先经过 AST 静态检查，再进入受控执行环境。
3. **技术问题和假设问题分流**：技术问题回到执行层修代码；生物学问题回到规划层改假设。
4. **本地状态优先**：用本地 JSON 记住分析过的内容、关键结果、已有文件和环境能力，减少重复上下文。
5. **文本 + 视觉双评审**：文本模型负责解释，视觉模型负责评估图是否可读、是否支持结论。
6. **说明书自动补齐**：注册到 Agent 的工具如果不在说明书里，会被自动追加到 `tool_documentation.md`。
7. **产物结构固定化**：输出目录和报告模板标准化，方便复用和审计。

## 目录结构

```text
src/sc_cell_agent/
├── agent.py            # Agent 主循环与本地执行器
├── config.py           # 配置与目录初始化
├── documentation.py    # Tool Documentation 自动检测与补齐
├── memory.py           # 本地记忆管理
├── planner.py          # 规划与迭代决策
├── prompts.py          # MiniMax 提示词模板
├── reports.py          # 报告与论文模板
└── validator.py        # 幻觉防护与静态检查
```

## 模型 API 配置

当前仓库已经把 **文本模型** 和 **视觉模型** 抽象为两个协议：

- `LLMClient.generate(prompt: str) -> str`
- `VisionClient.review_image(prompt: str, image_path: Path) -> str`

你可以把 MiniMax 的 API 封装成这两个 client，然后注入到 `CellAnalysisAgent`。

### 推荐环境变量

建议使用环境变量管理模型配置，而不是把 API Key 写死在代码里：

```bash
export MINIMAX_API_KEY="your_api_key"
export MINIMAX_BASE_URL="https://api.minimax.chat"
export MINIMAX_TEXT_MODEL="MiniMax-Text"
export MINIMAX_VISION_MODEL="MiniMax-Vision"
```

如果你的部署是私有网关或代理，只需要修改 `MINIMAX_BASE_URL`。

### 推荐的客户端职责划分

**文本客户端 `MiniMaxTextClient`** 应负责：

- 读取 `MINIMAX_API_KEY`。
- 组装文本请求。
- 调用规划、核对、代码生成等 prompt。
- 对 API 报错做重试和错误包装。

**视觉客户端 `MiniMaxVisionClient`** 应负责：

- 读取 `MINIMAX_API_KEY`。
- 接收 `image_path`。
- 把图像传给 MiniMax 视觉模型。
- 返回结构化视觉评审结论，例如 `visual_ok / issues / suggestions`。

### 建议的最小封装接口

下面这个例子不是完整 SDK，只是告诉你接入点应该长什么样：

```python
from pathlib import Path
import os


class MiniMaxTextClient:
    def __init__(self) -> None:
        self.api_key = os.environ["MINIMAX_API_KEY"]
        self.base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat")
        self.model = os.environ.get("MINIMAX_TEXT_MODEL", "MiniMax-Text")

    def generate(self, prompt: str) -> str:
        # 在这里调用真实 MiniMax 文本 API
        raise NotImplementedError


class MiniMaxVisionClient:
    def __init__(self) -> None:
        self.api_key = os.environ["MINIMAX_API_KEY"]
        self.base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat")
        self.model = os.environ.get("MINIMAX_VISION_MODEL", "MiniMax-Vision")

    def review_image(self, prompt: str, image_path: Path) -> str:
        # 在这里调用真实 MiniMax 视觉 API
        raise NotImplementedError
```

### Agent 初始化方式

当你完成上面的 client 封装后，推荐像下面这样初始化：

```python
from pathlib import Path

from sc_cell_agent import AgentConfig, CellAnalysisAgent, LocalPythonExecutor

config = AgentConfig(project_root=Path("./project_run"))
agent = CellAnalysisAgent(
    config=config,
    llm_client=MiniMaxTextClient(),
    executor=LocalPythonExecutor(),
    vision_client=MiniMaxVisionClient(),
)
```

## 推荐 workflow

下面是一个适合你目标的最小工作流。

### Step 1. 准备输入

你需要至少准备两类输入：

1. **背景描述**：疾病、组织、实验设计、重点问题。
2. **数据元信息**：`obs_columns`、`var_columns`、`uns_keys`、样本说明。

例如：

```python
background_text = "肺癌治疗前后单细胞转录组数据，重点关注免疫微环境变化。"
obs_columns = ["cell_type", "batch", "sample", "condition"]
var_columns = ["gene_symbol"]
uns_keys = ["neighbors"]
sample_notes = ["包含治疗前与治疗后样本", "包含多个病人批次"]
```

### Step 2. 注册工具并自动补齐 Tool Documentation

```python
missing = agent.bootstrap_tools()
```

这一步会：

- 注册当前允许模型使用的工具。
- 检查这些工具是否已经存在于 `tool_documentation.md`。
- 若缺失，则自动补写说明书。

如果你要引入 `scanpy`、`anndata`、`pandas`，推荐在这里继续注册，并补充 description。

### Step 3. 初始化状态

```python
state = agent.initialize_state(
    background_text=background_text,
    obs_columns=obs_columns,
    var_columns=var_columns,
    uns_keys=uns_keys,
    n_obs=12000,
    n_vars=22000,
    sample_notes=sample_notes,
)
```

这一步会把背景、数据概况、工具快照、本地说明书同步情况写进 `state.json`。

### Step 4. 先做背景-数据核对

```python
alignment = agent.verify_alignment(background_text, state)
```

这里不要急着直接做分析，而要先确认：

- 背景描述和数据字段是否一致。
- 是否缺少关键分组列。
- 是否存在重点关注但数据里没有的信息。

### Step 5. 生成分析假设与分析计划

```python
plan = agent.plan_analysis(
    background_text,
    state,
    focus_points=["免疫微环境", "治疗前后差异", "T 细胞亚群变化"],
)
```

建议让模型先输出：

- 2-4 条生物学假设。
- 每一步分析任务的输入、输出、判定标准。
- 潜在风险和限制。

### Step 6. 按“小步骤”生成代码

```python
code = agent.generate_step_code("执行 QC 并输出 QC 图", state)
validation = agent.validate_code(code, state)
```

如果 `validation.ok` 为 `False`，就不要运行，直接让模型根据报错修复。

### Step 7. 执行代码

```python
ok, output = agent.execute_step("qc", code, state)
```

建议每一步都做到：

- 代码尽量短小。
- 只做一个动作。
- 生成中间结果后立刻写入状态。

### Step 8. 对关键图做视觉评审

```python
visual_review = agent.review_visual_output("umap", state, Path("output/plots/umap.png"))
```

MiniMax 视觉模型建议重点看：

- 标签是否可读。
- 颜色是否区分明确。
- 图是否支持当前结论。
- 图是否适合作为汇报/论文插图。

### Step 9. 区分技术迭代和假设迭代

```python
decision = agent.review_step(
    technical_ok=True,
    biological_ok=False,
    technical_retry_count=0,
    hypothesis_retry_count=0,
    visual_ok=True,
)
```

推荐规则：

- `technical_ok=False` 或 `visual_ok=False`：回到技术修复。
- `biological_ok=False`：回到假设/规划层。
- 两者都通过：进入下一分析步骤。

### Step 10. 生成最终输出

```python
outputs = agent.finalize_outputs(state)
```

当前会生成并登记：

- 技术报告
- 分析报告
- 论文草稿
- Tool Documentation

后续你可以继续扩展到：

- `output/code/` 可复用脚本
- `output/data/` 关键结果表与 `.h5ad`
- `output/plots/` 的 `.png + .pdf`

## Tool Documentation 机制

- 每个注册工具都带有 `package + symbols + description`。
- Agent 在 `bootstrap_tools()` 和 `initialize_state()` 阶段自动检查 `tool_documentation.md`。
- 如果某个工具不存在于说明书中，就自动补写说明书条目。
- 后续代码生成 prompt 使用的不是临时字符串，而是完整的 `Tool Documentation` 文件内容。

## 为什么这样能减轻 MiniMax 的代码幻觉

- 不让模型“猜”变量名：提示词中注入 `obs_columns`、`var_columns`、已注册对象名。
- 不让模型“猜”库函数：提示词中直接注入 `Tool Documentation` 内容。
- 不让模型“一次写完所有流程”：只生成当前步骤的最小可执行代码。
- 不让错误进入主流程：静态检查器先拦截未定义变量、禁用导入、未授权函数。
- 不让历史上下文无限膨胀：状态管理器把关键结果压缩为结构化摘要。
- 不让“图画得很差但文本说得很好”的情况蒙混过关：关键图额外走视觉评审。
- 不让“工具注册了但没有说明书”的情况混过去：自动检测并补齐工具说明。

## 你下一步应该优先补什么

1. 实现真实的 MiniMax 文本客户端与视觉客户端。
2. 把 `scanpy/anndata/pandas/numpy/matplotlib` 注册为受控工具，并写出高质量 description。
3. 对关键图统一导出 `.png + .pdf`。
4. 为 QC、聚类、差异表达、细胞注释分别设计独立 prompt 模板。
5. 将 `state.json`、`tool_documentation.md` 与输出目录纳入实验审计链路。
