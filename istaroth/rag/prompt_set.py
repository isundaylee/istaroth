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
        - 默认只输出一个查询
        - 只有当问题涉及多个需要分别检索证据的独立概念或关系时，才分解为多个查询（最多3个）
        - 不要输出同一查询的改写、同义表达、不同措辞或关键词变体
        - 每个查询必须对应一个不同的信息需求
        - 移除口语化表达和不必要的修饰词

        示例：
        问题：钟离的真实身份是什么？
        查询：
        钟离的真实身份

        问题：雷电将军为什么实行眼狩令，珊瑚宫反抗军为什么反抗？
        查询：
        雷电将军实行眼狩令的原因
        珊瑚宫反抗军反抗眼狩令的原因

        请同时判断该问题属于以下哪种检索意图类型（基于证据分布，而非问题复杂程度）：
        - variety：证据分散在大量不同的来源中（如列举型问题"七位执政官分别是谁"，或覆盖多个独立事件/角色的宽泛主题）
        - context：答案集中在同一个来源的连续段落中，需要获取其上下文来完整理解（如一个剧情场景、一段对话、一个角色的完整故事）
        - balanced：介于两者之间

        用户问题：{question}
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
        - Default to one query
        - Only decompose when the question contains multiple independent concepts or relationships that need separate evidence retrieval (max 3)
        - Do not output rewrites, paraphrases, alternate wording, or keyword variants of the same query
        - Each query must represent a distinct information need
        - Remove colloquial expressions and unnecessary modifiers

        Examples:
        Question: What is Zhongli's true identity?
        Queries:
        Zhongli's true identity

        Question: Why did the Raiden Shogun enforce the Vision Hunt Decree, and why did the Sangonomiya Resistance oppose it?
        Queries:
        Why the Raiden Shogun enforced the Vision Hunt Decree
        Why the Sangonomiya Resistance opposed the Vision Hunt Decree

        Also classify the question's retrieval intent into one of the following (based on evidence distribution, not how complex/deep the question sounds):
        - variety: evidence is scattered across many different sources (e.g. enumerations like "who are the seven Archons", or broad themes covering many independent events/characters)
        - context: the answer is concentrated in a continuous passage within a single source and needs its surrounding context to be fully understood (e.g. a quest scene, dialogue, a character's complete story)
        - balanced: something in between

        User question: {question}
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
