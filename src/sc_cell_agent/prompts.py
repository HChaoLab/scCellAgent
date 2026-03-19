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
            - 输出中不要包含 Markdown 代码块。
            """
        ).strip()
