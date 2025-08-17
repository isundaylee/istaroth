"""Prompt templates for RAG pipeline, organized by language."""

import textwrap

import attrs

from istaroth import shared_prompts
from istaroth.agd import localization


@attrs.define
class RAGPrompts:
    """Container for language-specific RAG pipeline prompts."""

    generation_system_prompt: str = attrs.field()
    generation_user_prompt_template: str = attrs.field()
    question_preprocess_prompt: str = attrs.field()


def get_rag_prompts(language: localization.Language) -> RAGPrompts:
    """Get RAG prompts for the specified language."""
    if language == localization.Language.CHS:
        return _get_chinese_prompts()
    elif language == localization.Language.ENG:
        return _get_english_prompts()
    else:
        raise ValueError(f"Unsupported language: {language}")


def _get_chinese_prompts() -> RAGPrompts:
    """Get Chinese language prompts."""
    question_preprocess_prompt = textwrap.dedent(
        """\
        将用户的问题转换为1-3个适合检索系统的查询。

        每个查询应该是：
        - 一个完整的句子（可以是陈述句或疑问句）
        - 或一个单独的关键词（人物名、地点名、物品名等）

        规则：
        - 如果一个查询就能覆盖问题，只输出一个
        - 如果问题涉及多个独立概念，可以分解为多个查询（最多3个）
        - 每个查询聚焦于一个特定概念或关系
        - 移除口语化表达和不必要的修饰词

        用户问题：{question}

        每行输出一个查询，不要编号或解释：
        """
    )

    genshin_expertise = shared_prompts.get_genshin_expertise_description(
        localization.Language.CHS
    )
    response_principles = shared_prompts.get_response_principles(
        localization.Language.CHS
    )
    citation_guidelines = shared_prompts.get_citation_guidelines(
        localization.Language.CHS
    )

    system_prompt = textwrap.dedent(
        f"""\
        {genshin_expertise}

        {response_principles}

        {citation_guidelines}

        请始终用中文回答，避免过度解读或主观臆断。记住：用户看不到你检索到的资料，所以必须在回答中充分引用原文。
        """
    )

    citation_reminder = shared_prompts.get_citation_reminder(localization.Language.CHS)

    user_prompt_template = textwrap.dedent(
        f"""\
        请根据以下资料进行回答：
        {{retrieved_context}}

        回答要求：

        请基于资料内容，结合你对《原神》剧情的理解，简洁清晰地回答用户问题。

        {citation_reminder}

        用户提问：{{user_question}}
        """
    )

    return RAGPrompts(
        generation_system_prompt=system_prompt,
        generation_user_prompt_template=user_prompt_template,
        question_preprocess_prompt=question_preprocess_prompt,
    )


def _get_english_prompts() -> RAGPrompts:
    """Get English language prompts."""
    question_preprocess_prompt = textwrap.dedent(
        """\
        Convert the user's question into 1-3 queries optimized for a retrieval system.

        Each query should be:
        - A complete sentence (can be a statement or question)
        - Or a single keyword (character name, location name, item name, etc.)

        Rules:
        - If one query can cover the question, output only one
        - If the question involves multiple independent concepts, decompose into multiple queries (max 3)
        - Each query should focus on a specific concept or relationship
        - Remove colloquial expressions and unnecessary modifiers

        User question: {question}

        Output one query per line, without numbering or explanation:
        """
    )

    genshin_expertise = shared_prompts.get_genshin_expertise_description(
        localization.Language.ENG
    )
    response_principles = shared_prompts.get_response_principles(
        localization.Language.ENG
    )
    citation_guidelines = shared_prompts.get_citation_guidelines(
        localization.Language.ENG
    )

    system_prompt = textwrap.dedent(
        f"""\
        {genshin_expertise}

        {response_principles}

        {citation_guidelines}

        Always respond in English, avoiding over-interpretation or subjective speculation. Remember: users cannot see the retrieved materials, so you must fully quote source text in your responses.
        """
    )

    citation_reminder = shared_prompts.get_citation_reminder(localization.Language.ENG)

    user_prompt_template = textwrap.dedent(
        f"""\
        Please answer based on the following source material:
        {{retrieved_context}}

        Response Requirements:

        Please provide a concise and clear answer based on the source material, combined with your understanding of Genshin Impact lore.

        {citation_reminder}

        User Question: {{user_question}}
        """
    )

    return RAGPrompts(
        generation_system_prompt=system_prompt,
        generation_user_prompt_template=user_prompt_template,
        question_preprocess_prompt=question_preprocess_prompt,
    )
