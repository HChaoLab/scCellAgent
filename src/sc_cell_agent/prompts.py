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
    def build_code_prompt(task_name: str, state_summary: dict[str, Any], tool_reference: str) -> str:
        return dedent(
            f"""
            你现在只需要完成一个最小任务：{task_name}。

            可用上下文：
            {state_summary}

            工具与软件说明书：
            {tool_reference}

            代码约束：
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
