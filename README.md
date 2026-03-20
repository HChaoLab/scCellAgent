# scCellAgent

一个面向单细胞分析任务的 Python Agent 脚手架，重点解决以下问题：

- 使用 MiniMax / MinMax 等大模型时的代码幻觉控制。
- 分离“技术迭代”和“生物学假设迭代”。
- 用本地记忆减少 token 消耗。
- 自动沉淀可复用代码、关键数据、关键图、技术报告、分析报告和论文式报告。
- 利用 **MiniMax 视觉模型** 对 QC 图、UMAP、差异表达图等进行二次质量评审。
- 自动检测单细胞分析工具是否缺少说明书，并追加到 `Tool Documentation`。
- 支持从 `.env` 自动读取 MiniMax 文本/视觉模型配置。

## 设计原则

1. **先约束，后生成**：不直接让大模型自由写整段分析脚本，而是给出受约束的任务、可用 API 白名单、已有变量和数据字典。
2. **先检查，后执行**：所有模型生成代码都必须先经过 AST 静态检查，再进入受控执行环境。
3. **技术问题和假设问题分流**：技术问题回到执行层修代码；生物学问题回到规划层改假设。
4. **本地状态优先**：用本地 JSON 记住分析过的内容、关键结果、已有文件和环境能力，减少重复上下文。
5. **文本 + 视觉双评审**：文本模型负责解释，视觉模型负责评估图是否可读、是否支持结论。
6. **说明书自动补齐**：注册到 Agent 的工具如果不在说明书里，会被自动追加到 `tool_documentation.md`。
7. **配置文件化**：模型 API Key、URL 和模型名优先从 `.env` 自动加载。
8. **产物结构固定化**：输出目录和报告模板标准化，方便复用和审计。

## 目录结构

```text
src/sc_cell_agent/
├── agent.py            # Agent 主循环与本地执行器
├── config.py           # 配置与目录初始化
├── documentation.py    # Tool Documentation 自动检测与补齐
├── env.py              # .env 加载器
├── memory.py           # 本地记忆管理
├── minimax.py          # MiniMax 文本/视觉客户端
├── planner.py          # 规划与迭代决策
├── prompts.py          # MiniMax 提示词模板
├── reports.py          # 报告与论文模板
└── validator.py        # 幻觉防护与静态检查
```

## 安装说明

项目地址：`https://github.com/HChaoLab/scCellAgent`

### 是否需要创建 conda 环境？

**建议创建独立环境，但不是绝对强制。**

原因是这个项目后续通常会接入：

- `scanpy`
- `anndata`
- `numpy`
- `pandas`
- `matplotlib`
- 以及可能的富集分析、批次校正、可视化相关依赖

这些包在不同项目之间比较容易发生版本冲突，所以更推荐使用 **conda/mamba 环境** 单独管理。  
如果你已经有一个干净的 Python 3.11 环境，也可以直接使用 `venv`。

### 方式 1：推荐，使用 conda

```bash
git clone https://github.com/HChaoLab/scCellAgent.git
cd scCellAgent
conda create -n scCellAgent python=3.11 -y
conda activate scCellAgent
pip install -e .
```

### 方式 2：使用 venv

```bash
git clone https://github.com/HChaoLab/scCellAgent.git
cd scCellAgent
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 安装后建议先检查

```bash
python -c "import sc_cell_agent; print('sc_cell_agent imported successfully')"
pytest -q
```

如果后续你接入 `scanpy` 等单细胞库，建议再按你的分析需要补装依赖。

## 第一步：用 `.env` 管理 MiniMax API

现在建议不要再手动 `export` 环境变量，而是在项目根目录放一个 `.env` 文件，让 Agent 自动读取。

### 1. 复制模板

```bash
cp .env.example .env
```

### 2. 填写你的配置

`.env.example` 中包含以下字段：

```dotenv
MINIMAX_API_KEY=your_api_key
MINIMAX_TEXT_MODEL=MiniMax-Text
MINIMAX_TEXT_API_URL=https://your-minimax-text-endpoint
MINIMAX_VISION_MODEL=MiniMax-Vision
MINIMAX_VISION_API_URL=https://your-minimax-vision-endpoint
```

说明：

- `MINIMAX_API_KEY`：你的 MiniMax API Key
- `MINIMAX_TEXT_MODEL`：文本模型名
- `MINIMAX_TEXT_API_URL`：文本模型接口 URL
- `MINIMAX_VISION_MODEL`：视觉模型名
- `MINIMAX_VISION_API_URL`：视觉模型接口 URL

> 这里刻意把 **URL** 也放进 `.env`，是因为不同部署环境可能使用不同网关或代理；由你自己填写可以避免把错误 endpoint 写死在代码中。

## `.env` 自动读取方式

当前仓库新增了：

- `load_env_file()`：读取 `.env` 并写入 `os.environ`
- `MiniMaxSettings.from_env()`：从 `.env` 解析 MiniMax 配置
- `MiniMaxTextClient.from_env()`：自动从 `.env` 初始化文本客户端
- `MiniMaxVisionClient.from_env()`：自动从 `.env` 初始化视觉客户端

因此你可以像下面这样直接初始化：

```python
from pathlib import Path

from sc_cell_agent import (
    AgentConfig,
    CellAnalysisAgent,
    LocalPythonExecutor,
    MiniMaxTextClient,
    MiniMaxVisionClient,
)

config = AgentConfig(project_root=Path("./project_run"))
agent = CellAnalysisAgent(
    config=config,
    llm_client=MiniMaxTextClient.from_env(),
    executor=LocalPythonExecutor(),
    vision_client=MiniMaxVisionClient.from_env(),
)
```

## 当前 MiniMax 客户端的定位

当前实现是**第一阶段的可配置客户端骨架**，重点解决：

- `.env` 自动读取
- 文本模型和视觉模型配置分离
- 文本/视觉请求分别走不同 URL
- 支持注入自定义 `transport`，便于你后续替换成真实 HTTP 调用逻辑或测试桩

这意味着：

- 现在已经能自动读 `.env`
- 也已经能通过统一入口构造文本/视觉 client
- 但你后续仍应根据自己的 MiniMax API 响应格式，继续微调 payload 和返回字段映射

## 推荐 workflow

下面是一个适合你目标的最小工作流。

### Step 1. 准备 `.env`

```bash
cp .env.example .env
```

然后填好你的 Key、文本 URL、视觉 URL、模型名。

### Step 2. 初始化 Agent

```python
from pathlib import Path

from sc_cell_agent import (
    AgentConfig,
    CellAnalysisAgent,
    LocalPythonExecutor,
    MiniMaxTextClient,
    MiniMaxVisionClient,
)

agent = CellAnalysisAgent(
    config=AgentConfig(project_root=Path("./project_run")),
    llm_client=MiniMaxTextClient.from_env(),
    executor=LocalPythonExecutor(),
    vision_client=MiniMaxVisionClient.from_env(),
)
```

### Step 3. 注册工具并自动补齐 Tool Documentation

```python
missing = agent.bootstrap_tools()
```

### Step 4. 初始化状态

```python
state = agent.initialize_state(
    background_text="肺癌治疗前后单细胞转录组数据，重点关注免疫微环境变化。",
    obs_columns=["cell_type", "batch", "sample", "condition"],
    var_columns=["gene_symbol"],
    uns_keys=["neighbors"],
    n_obs=12000,
    n_vars=22000,
    sample_notes=["包含治疗前与治疗后样本", "包含多个病人批次"],
)
```

### Step 5. 核对背景与数据

```python
alignment = agent.verify_alignment(state.background_summary["background_text"], state)
```

### Step 6. 生成分析计划

```python
plan = agent.plan_analysis(
    state.background_summary["background_text"],
    state,
    focus_points=["免疫微环境", "治疗前后差异", "T 细胞亚群变化"],
)
```

### Step 7. 生成并验证代码

```python
code = agent.generate_step_code("执行 QC 并输出 QC 图", state)
validation = agent.validate_code(code, state)
```

### Step 8. 执行代码

```python
ok, output = agent.execute_step("qc", code, state)
```

### Step 9. 视觉评审

```python
from pathlib import Path

visual_review = agent.review_visual_output("umap", state, Path("output/plots/umap.png"))
```

### Step 10. 生成最终输出

```python
outputs = agent.finalize_outputs(state)
```

## 单细胞专用 prompt 模板

对于单细胞核心步骤，推荐直接使用独立 prompt 模板：

```python
from sc_cell_agent.prompts import PromptBuilder

qc_prompt = PromptBuilder.build_qc_prompt(agent.state_snapshot(state), agent.tool_docs.as_text())
clustering_prompt = PromptBuilder.build_clustering_prompt(agent.state_snapshot(state), agent.tool_docs.as_text())
de_prompt = PromptBuilder.build_differential_expression_prompt(agent.state_snapshot(state), agent.tool_docs.as_text())
annotation_prompt = PromptBuilder.build_cell_annotation_prompt(agent.state_snapshot(state), agent.tool_docs.as_text())
```

它们分别对应：

- QC
- 聚类
- 差异表达
- 细胞注释

## 你接下来应该继续做什么

完成 `.env` 自动读取后，下一步建议优先做：

1. 把真实 MiniMax 响应格式接进 `MiniMaxTextClient` / `MiniMaxVisionClient`
2. 注册 `scanpy/anndata/pandas/numpy/matplotlib`
3. 先跑通 QC → 聚类 两个步骤
4. 再接差异表达和细胞注释
5. 最后补全报告和论文生成
