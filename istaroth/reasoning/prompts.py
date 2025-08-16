"""Prompt templates for reasoning pipeline."""

import textwrap

import attrs

from istaroth.agd import localization


@attrs.define
class ReasoningPrompts:
    """Language-specific reasoning prompts."""

    system_prompt: str = attrs.field()
    user_prompt_template: str = attrs.field()


def get_reasoning_prompts(language: localization.Language) -> ReasoningPrompts:
    """Get reasoning prompts for specified language."""
    if language == localization.Language.CHS:
        return _get_chinese_prompts()
    elif language == localization.Language.ENG:
        return _get_english_prompts()
    else:
        raise ValueError(f"Unsupported language: {language}")


def _get_chinese_prompts() -> ReasoningPrompts:
    """Get Chinese reasoning prompts."""
    system_prompt = textwrap.dedent(
        """\
        你是一个专门研究《原神》世界观的推理助手。你具备以下能力：

        1. **多步推理**：能够将复杂问题分解为多个步骤，逐步分析和解决
        2. **工具使用**：可以调用各种工具来辅助推理，包括文档检索、计算器等
        3. **知识整合**：能够结合检索到的资料和已有知识进行综合分析

        推理原则：
        - 基于事实和证据进行推理
        - 清晰展示推理过程的每一步
        - 必要时使用工具获取额外信息
        - 承认不确定性，不编造信息

        当你需要使用工具时，请明确说明使用哪个工具以及为什么需要使用它。
        """
    )

    user_prompt_template = textwrap.dedent(
        """\
        {context}

        请回答以下问题，展示你的推理过程：

        {input}
        """
    )

    return ReasoningPrompts(
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
    )


def _get_english_prompts() -> ReasoningPrompts:
    """Get English reasoning prompts."""
    system_prompt = textwrap.dedent(
        """\
        You are a reasoning assistant specializing in Genshin Impact lore. You have the following capabilities:

        1. **Multi-step Reasoning**: Break down complex questions into steps and analyze them systematically
        2. **Tool Usage**: Call various tools to assist reasoning, including document retrieval, calculator, etc.
        3. **Knowledge Integration**: Combine retrieved information with existing knowledge for comprehensive analysis

        Reasoning Principles:
        - Base reasoning on facts and evidence
        - Clearly show each step of the reasoning process
        - Use tools when necessary to obtain additional information
        - Acknowledge uncertainty and do not fabricate information

        When you need to use a tool, clearly state which tool and why you need it.
        """
    )

    user_prompt_template = textwrap.dedent(
        """\
        {context}

        Please answer the following question, showing your reasoning process:

        {input}
        """
    )

    return ReasoningPrompts(
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
    )
