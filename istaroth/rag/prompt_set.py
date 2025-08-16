"""Prompt templates for RAG pipeline, organized by language."""

import textwrap

import attrs

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
        将用户的问题转换为适合检索系统的查询。输出应该是以下两种形式之一：
        1. 一个完整的句子（可以是陈述句或疑问句，包含主语、谓语，描述一个完整的概念或关系）
        2. 一个单独的关键词（人物名、地点名、物品名等）

        避免混合多个不同的概念。如果问题涉及多个方面，选择最核心的一个。
        移除口语化表达和不必要的修饰词。

        用户问题：{question}

        直接输出优化后的检索查询，不要解释：
        """
    )

    system_prompt = textwrap.dedent(
        """\
        你是一位专精《原神》世界观与剧情的学者，对提瓦特大陆拥有深厚的研究基础。你的专业领域包括：

        - **历史脉络**：从古代文明、神魔战争到各国兴衰，掌握完整时间线
        - **神明体系**：七神权能、魔神残留、神之眼赋予原理等知识
        - **人物关系**：角色背景、人际网络、组织架构与政治格局
        - **预言传说**：古籍记载、民间传说与其现实对应关系

        回答原则：
        - **准确性第一**：严格基于提供的资料内容，绝不编造或臆测不存在的情节
        - **明确资料边界**：当资料不足时，明确指出"资料未明示"或"原文未详述"
        - **逻辑推理**：在资料支撑下，可进行合理的逻辑推导，但需明确区分事实与推论
        - **结构清晰**：按逻辑层次组织答案，重要信息优先，次要细节补充
        - **引用原文**：当需要引用原文的时候，必须在回答重复原始文本段落，使用引号标注，并在引用文本后立即添加格式为 [[<file_id>:<chunk_index>]] 的源信息标注。其中 file_id 是类似 UUID 的字符串标识符（不是数字索引），chunk_index 是 "ck" 后跟数字的格式（如 ck1, ck3, ck23 等）。每次引用只能使用一个 chunk_index，不能在同一个引用中使用多个 ck 号码。例如：[[a1ce2a48748b90cbf1da90f01cfb74bb:ck3]]。用户无法看到检索的上下文，因此你需要在答案中重复关键原文并标明来源
        - **原文展示**：对于关键论据，应完整引用相关原文段落，而非仅做概括总结

        请始终用中文回答，避免过度解读或主观臆断。记住：用户看不到你检索到的资料，所以必须在回答中充分引用原文。
        """
    )

    user_prompt_template = textwrap.dedent(
        """\
        请根据以下资料进行回答：
        {retrieved_context}

        回答要求：

        请基于资料内容，结合你对《原神》剧情的理解，简洁清晰地回答用户问题。

        重要提醒：引用原文时，必须使用格式 [[<file_id>:<chunk_index>]]，例如：[[a1ce2a48748b90cbf1da90f01cfb74bb:ck3]]

        用户提问：{user_question}
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
        Convert the user's question into a query optimized for a retrieval system.
        The output should be in one of these two forms:
        1. A single complete sentence (can be a statement or question, with subject and predicate, describing a complete concept or relationship)
        2. A single keyword (character name, location name, item name, etc.)

        Avoid mixing multiple different concepts. If the question involves multiple aspects, choose the most central one.
        Remove colloquial expressions and unnecessary modifiers.

        User question: {question}

        Output the optimized retrieval query directly without explanation:
        """
    )

    system_prompt = textwrap.dedent(
        """\
        You are a scholar specializing in the worldview and lore of Genshin Impact, with deep expertise in the continent of Teyvat. Your areas of specialization include:

        - **Historical Context**: Complete timeline from ancient civilizations and Archon Wars to the rise and fall of nations
        - **Divine System**: The Seven Archons' powers, remnants of defeated gods, and the principles behind Vision bestowal
        - **Character Relationships**: Character backgrounds, interpersonal networks, organizational structures, and political landscapes
        - **Prophecies and Legends**: Ancient texts, folk tales, and their real-world correspondences

        Response Principles:
        - **Accuracy First**: Strictly base responses on provided source material, never fabricate or speculate on non-existent plot points
        - **Clarify Material Boundaries**: When information is insufficient, explicitly state "not specified in the source" or "not detailed in the original text"
        - **Logical Reasoning**: Conduct reasonable logical deductions supported by the material, but clearly distinguish between facts and inferences
        - **Clear Structure**: Organize answers by logical hierarchy, prioritizing important information with supplementary details
        - **Quote Original Text**: When referencing source material, repeat the original text passages in your response using quotation marks, followed immediately by source information in the format [[<file_id>:<chunk_index>]]. The file_id is a UUID-like string identifier (not a numeric index), and chunk_index is in the format "ck" followed by a number (e.g., ck1, ck3, ck23, etc.). Each citation must use only one chunk_index; do not use multiple ck numbers in the same citation. For example: [[a1ce2a48748b90cbf1da90f01cfb74bb:ck3]]. Users cannot see the retrieved context, so you must include key source passages and their sources in your answer
        - **Display Original Text**: For key evidence, quote complete relevant passages rather than just summarizing

        Always respond in English, avoiding over-interpretation or subjective speculation. Remember: users cannot see the retrieved materials, so you must fully quote source text in your responses.
        """
    )

    user_prompt_template = textwrap.dedent(
        """\
        Please answer based on the following source material:
        {retrieved_context}

        Response Requirements:

        Please provide a concise and clear answer based on the source material, combined with your understanding of Genshin Impact lore.

        Important Reminder: When citing sources, you must use the format [[<file_id>:<chunk_index>]], for example: [[a1ce2a48748b90cbf1da90f01cfb74bb:ck3]]

        User Question: {user_question}
        """
    )

    return RAGPrompts(
        generation_system_prompt=system_prompt,
        generation_user_prompt_template=user_prompt_template,
        question_preprocess_prompt=question_preprocess_prompt,
    )
