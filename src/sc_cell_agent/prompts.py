from __future__ import annotations

from textwrap import dedent
from typing import Any


class PromptBuilder:
    @staticmethod
    def build_alignment_prompt(background_text: str, dataset_summary: dict[str, Any]) -> str:
        return dedent(
            f"""
            你是单细胞分析 Agent 的规划器。
            请核对“背景描述”和“数据元信息”是否一致，并列出风险点。

            背景描述：
            {background_text}

            数据元信息：
            {dataset_summary}

            输出要求：
            1. 用项目符号列出一致点。
            2. 用项目符号列出冲突点。
            3. 给出必须额外确认的字段。
            4. 不要编造数据中不存在的列名。
            """
        ).strip()

    @staticmethod
    def build_planning_prompt(background_text: str, state_summary: dict[str, Any], focus_points: list[str]) -> str:
        return dedent(
            f"""
            你是单细胞科研分析 Agent 的规划器。
            请基于背景、数据概况和重点关注内容，输出“分析假设”和“分析计划”。

            背景：
            {background_text}

            当前状态：
            {state_summary}

            特殊关注点：
            {focus_points}

            输出要求：
            1. 先给出 2-4 条可检验的生物学假设。
            2. 再给出分步骤分析计划，每一步必须说明输入、输出和判定标准。
            3. 如果背景与数据不充分匹配，必须明确写出风险。
            4. 不要创造不存在的数据字段。
            """
        ).strip()

    @staticmethod
    def _build_task_prompt(
        task_name: str,
        task_goal: str,
        task_requirements: list[str],
        state_summary: dict[str, Any],
        tool_reference: str,
    ) -> str:
        requirements = "\n".join(f"- {item}" for item in task_requirements)
        return dedent(
            f"""
            你现在只需要完成一个最小任务：{task_name}。
            当前任务目标：{task_goal}

            可用上下文：
            {state_summary}

            工具与软件说明书：
            {tool_reference}

            当前任务要求：
            {requirements}

            通用代码约束：
            - 只能生成 Python 代码。
            - 只能使用上下文中已经声明过的变量名。
            - 如果不确定列名，先打印列名，不要猜测。
            - 不允许导入未在说明书中出现的库。
            - 代码必须尽量短小，可单步执行。
            - 如果需要保存图，必须同时导出 png 和 pdf。
            - 输出中不要包含 Markdown 代码块。
            """
        ).strip()

    @staticmethod
    def build_code_prompt(task_name: str, state_summary: dict[str, Any], tool_reference: str) -> str:
        return PromptBuilder._build_task_prompt(
            task_name=task_name,
            task_goal="执行当前分析子步骤并返回最小可运行代码。",
            task_requirements=[
                "只完成当前单个子任务，不要扩展到后续分析。",
                "如果会修改 adata，请先清晰说明输出对象或保存路径。",
            ],
            state_summary=state_summary,
            tool_reference=tool_reference,
        )

    @staticmethod
    def build_qc_prompt(state_summary: dict[str, Any], tool_reference: str) -> str:
        return PromptBuilder._build_task_prompt(
            task_name="单细胞质量控制（QC）",
            task_goal="完成细胞和基因层面的质量控制，并输出可审阅的 QC 指标与图形。",
            task_requirements=[
                "优先检查 n_genes_by_counts、total_counts、pct_counts_mt 等常见指标是否可用。",
                "如果线粒体基因或核糖体基因前缀不确定，先检查 var 信息再决定。",
                "输出过滤前后细胞数、基因数和关键阈值。",
                "至少生成 1 张 QC 图，并同时导出 png 和 pdf。",
                "不要直接进入聚类或差异表达。",
            ],
            state_summary=state_summary,
            tool_reference=tool_reference,
        )

    @staticmethod
    def build_clustering_prompt(state_summary: dict[str, Any], tool_reference: str) -> str:
        return PromptBuilder._build_task_prompt(
            task_name="单细胞聚类分析",
            task_goal="完成邻居图、降维和聚类，并输出可解释的聚类结果。",
            task_requirements=[
                "优先基于已有高变基因、PCA 或邻接图信息选择最小必要步骤。",
                "必须明确使用的聚类参数，例如邻居数、主成分数、resolution。",
                "输出簇数量和每个簇的基本规模。",
                "至少生成 1 张 UMAP 或 t-SNE 图，并同时导出 png 和 pdf。",
                "不要在本步骤混入差异表达和细胞注释。",
            ],
            state_summary=state_summary,
            tool_reference=tool_reference,
        )

    @staticmethod
    def build_differential_expression_prompt(state_summary: dict[str, Any], tool_reference: str) -> str:
        return PromptBuilder._build_task_prompt(
            task_name="差异表达分析",
            task_goal="针对指定分组或簇计算差异表达，并输出可审阅的结果表与图形。",
            task_requirements=[
                "必须先确认比较组存在于 obs 中，不要猜测分组列。",
                "明确比较对象、统计方法和多重检验校正方式。",
                "输出 top markers 或 top DEGs 的表格保存路径。",
                "如果生成火山图、热图或 dotplot，必须同时导出 png 和 pdf。",
                "不要在本步骤直接给出细胞类型命名结论。",
            ],
            state_summary=state_summary,
            tool_reference=tool_reference,
        )

    @staticmethod
    def build_cell_annotation_prompt(state_summary: dict[str, Any], tool_reference: str) -> str:
        return PromptBuilder._build_task_prompt(
            task_name="细胞注释",
            task_goal="基于 marker、参考知识和已有聚类结果，为细胞簇生成谨慎的细胞类型注释。",
            task_requirements=[
                "优先引用差异表达或 marker 结果，不要脱离证据直接命名。",
                "如果证据不足，必须输出候选注释和不确定性说明。",
                "明确注释是按 cluster 还是按单细胞进行。",
                "输出注释结果写回 obs 的列名或保存路径。",
                "不要在缺少 marker 支持时强行给出过细的亚群命名。",
            ],
            state_summary=state_summary,
            tool_reference=tool_reference,
        )

    @staticmethod
    def build_visual_review_prompt(task_name: str, state_summary: dict[str, Any]) -> str:
        return dedent(
            f"""
            你是单细胞分析结果的视觉评审器。
            请评估当前图像是否满足科研汇报要求。

            当前任务：{task_name}
            状态摘要：{state_summary}

            输出要求：
            1. 判断图像是否清晰、标签是否可读、颜色是否可区分。
            2. 判断图像是否支持当前分析结论。
            3. 返回 JSON 风格结论，包含 visual_ok、issues、suggestions 三个字段。
            """
        ).strip()
