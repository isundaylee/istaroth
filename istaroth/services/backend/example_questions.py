"""Example questions for the Istaroth RAG system."""

import random

from istaroth.agd import localization

_EXAMPLE_QUESTIONS = {
    localization.Language.CHS: [
        "深渊教团的真实身份是什么？",
        "坎瑞亚为什么会覆灭？",
        "蒙德的四风守护是指哪些？",
        "玛丽安与西摩尔的关系是什么样的",
        "捷德为什么要去永恒绿洲？",
    ],
    localization.Language.ENG: [
        "What is the true identity of the Abyss Order?",
        "Why did Khaenri'ah fall?",
        "What are the Four Winds of Mondstadt?",
        "What is the relationship between Mary-Ann and Seymour?",
        "Why does Jeht go to the Eternal Oasis?",
    ],
}


def get_random_example_question(language: localization.Language) -> str:
    """Get a random example question for the specified language."""
    if language not in _EXAMPLE_QUESTIONS:
        raise ValueError(f"Unsupported language: {language}")

    return random.choice(_EXAMPLE_QUESTIONS[language])
