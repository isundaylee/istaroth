#!/usr/bin/env python3
"""Sanity check pytest for text corpus."""

import pathlib


def test_chinese_corpus_sanity():
    """Comprehensive sanity check for Chinese text corpus."""
    base_path = pathlib.Path(__file__).parent.parent / "text"
    chs_path = base_path / "chs"

    # Define test cases with file paths and expected content (1-to-1 mapping)
    test_cases = {
        "agd_artifact_set/15029_旅途中的鲜花.txt": "「是啊，我不会怨恨。我明白，你不曾见到我曾目睹的景象。所以你才会想阻止我。」",
        "agd_character_story/10000048_烟绯.txt": "所以烟绯也拥有神之眼——而且她的神之眼，与她信奉的「规则」等价。",
        "agd_material_type/562370359652035705_MATERIAL_AVATAR_MATERIAL.txt": "传说在最初的僭主来到原始之海时，水国的先主曾赠予他一杯水。",
        "agd_quest/74078_溪舟的尾波.txt": "水仙的追迹·第四幕 溪舟的尾波",
        "agd_quest/74078_溪舟的尾波.txt": "纳齐森科鲁兹: 我想知道，你们做了什么样的梦。",
        "agd_readable/200334_日月前事.txt": "我们称呼她「卡伊洛斯」，或者「不变世界的统领与执政」。真正秘密的名字，我们不敢直言，所以在这里倒写。「露塔斯伊」——我仅提一次。",
        "agd_readable/200982_某人留下的铭记其一.txt": "…留给我们的唯有一条路，那就是希巴拉克的道路…",
        "agd_readable/294414_白辰之环.txt": "抑或是用巧技让人造的流星在深空绽放的一族，",
        "agd_subtitle/480745599316975833_Cs_Mengde_EQ401260901_AA_CHS.txt": "溪流与梦想汇入沧洋\n晶蝶点水的须臾\n星河下的少年白发成长",
        "agd_talk_group/143001_GadgetGroup.txt": "夜鸦乘务员: 客人，欢迎使用夜鸦航线，请问您想前往哪一个站点？",
        "agd_talk_group/1255_NpcGroup.txt": "遗迹的铭文 (铭文): 「风带来故事的种子，时间使之发芽。」",
        "agd_voiceline/10000089_芙宁娜.txt": "没想到你会对我的事这么上心，这是否意味着你仍然需要我的「力量」呢？然而如今的我…或许无法给你足够的回报…你说看重的是我「本人」？既然这样，就让你我共同出演我们的未来吧。",
    }

    # Test each file and its expected content
    for file_path, expected_content in test_cases.items():
        full_path = chs_path / file_path
        content = full_path.read_text(encoding="utf-8")
        assert (
            expected_content in content
        ), f"Expected content '{expected_content}' not found in {file_path}"


def test_english_corpus_sanity():
    """Comprehensive sanity check for English text corpus."""
    base_path = pathlib.Path(__file__).parent.parent / "text"
    eng_path = base_path / "eng"

    # Define test cases with file paths and expected content (1-to-1 mapping)
    test_cases = {
        "agd_artifact_set/15029_Odyssean_Flower.txt": "Yes, hatred shall not fill me. I know that you have not seen the sights I have, and that is why you wish to stop me.",
        "agd_character_story/10000048_Yanfei.txt": "That is why Yanfei possesses a Vision, one that is of equal weight to her principles.",
        "agd_material_type/562370359652035705_MATERIAL_AVATAR_MATERIAL.txt": "Legend says that when the first usurper came to the primordial sea, the first sovereign gave him a goblet of water.",
        "agd_quest/74078_Rowboats_Wake.txt": "In the Wake of Narcissus: Act IV Rowboat's Wake",
        "agd_quest/74078_Rowboats_Wake.txt": "Narzissenkreuz: I would like to know what sort of dreams you had.",
        "agd_readable/200334_Before_Sun_and_Moon.txt": 'We call her Kairos, or "the ruler of the unchanging world." We dare not speak her true, secret name, and so I pen it here, only once, and in reverse: "Htoratsi."',
        "agd_readable/200982_Notes_Someone_Left_Behind_I.txt": "...The only road left to us is the path of Xbalanque...",
        "agd_readable/294414_Hakushin_Ring.txt": "Or the clan who used ingenious techniques to make man-made meteors bloom in the skies...",
        "agd_subtitle/885308807013307542_Cs_Mengde_EQ401260901_AA_EN.txt": "Far from my native land I roamed\nIn streams I slept\nMany seasons I met as the suns set and rose",
        "agd_talk_group/143001_GadgetGroup.txt": "Night Raven Flight Attendant: Welcome, dear guest, and thank you for choosing Nachtraben Airlines. Where do you wish to alight today?",
        "agd_talk_group/1255_NpcGroup.txt": 'Carving Marks (Inscription): "Seeds of stories, brought by the wind and cultivated by time."',
        "agd_voiceline/10000089_Furina.txt": "I didn't know you cared so much about me. Does that mean that you still need my power? But given the way I am now... there's a chance I won't be able to give you everything you need. Hmm? All you really care about is... me? In that case, then let us act out our future journey together!",
    }

    # Test each file and its expected content
    for file_path, expected_content in test_cases.items():
        full_path = eng_path / file_path
        content = full_path.read_text(encoding="utf-8")
        assert (
            expected_content in content
        ), f"Expected content '{expected_content}' not found in {file_path}"
