"""Shared test fixtures."""

import json
import os
import pathlib
import shutil
import subprocess

import pytest

from istaroth import utils
from istaroth.agd import localization, repo


@pytest.fixture
def agd_path() -> str:
    """Get AGD path from environment variable."""
    agd_path_value = os.environ.get("AGD_PATH")
    if not agd_path_value:
        pytest.skip("AGD_PATH environment variable not set")
    return utils.assert_not_none(agd_path_value)


@pytest.fixture
def data_repo() -> repo.DataRepo:
    """Create DataRepo instance from environment."""
    try:
        return repo.DataRepo.from_env()
    except ValueError:
        pytest.skip("AGD_PATH environment variable not set")
        # This line will never be reached due to pytest.skip() raising an exception
        # but mypy doesn't understand that, so we need a return statement
        raise  # pragma: no cover


_PROJECT_ROOT = pathlib.Path(__file__).parent.parent


def run_rag_tools(*args: str) -> subprocess.CompletedProcess[str]:
    """Run rag_tools script with given arguments."""
    script_path = _PROJECT_ROOT / "scripts" / "rag_tools.py"
    return subprocess.run(
        ["python", str(script_path), *args],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
    )


@pytest.fixture(scope="session")
def test_text_dir(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """Create temporary directory with test text files containing diverse content."""
    data_dir = tmp_path_factory.mktemp("test_text")

    documents = {
        "zhongli_lore.txt": (
            "钟离是岩王帝君摩拉克斯的人间化身。作为最古老的七神之一，他守护璃月已有三千七百年。"
            "钟离的真实身份是岩之神摩拉克斯，他创造了摩拉货币系统，并签订了终结魔神战争的契约。"
        ),
        "venti_story.txt": (
            "温迪是蒙德的风神巴巴托斯，以吟游诗人的形象出现在人间。他热爱自由与诗歌，"
            "经常在天使的馈赠酒馆演奏。温迪曾经帮助蒙德人民推翻了旧贵族的统治。"
        ),
        "cooking_recipes.txt": (
            "提瓦特大陆的美食多种多样。蒙德烤蘑菇披萨需要蘑菇、面粉、卷心菜和奶酪。"
            "璃月的珍珠翡翠白玉汤使用豆腐、莲蓬和金鱼草制作，是一道清淡的素食料理。"
        ),
        "hilichurl_language.txt": (
            "丘丘人有自己独特的语言体系。Unu表示一，du表示二，unu du表示三。"
            "Mosi mita表示吃肉，gusha表示蔬菜植物，mosi gusha意为吃蔬菜。Ya表示人类。"
        ),
        "weapons_guide.txt": (
            "武器分为单手剑、双手剑、长柄武器、法器和弓箭五种类型。五星武器拥有最高的基础攻击力。"
            "狼的末路是双手剑，适合物理输出角色。天空之翼是弓箭，提供暴击率和暴击伤害加成。"
        ),
        "elemental_reactions.txt": (
            "元素反应是战斗的核心机制。火元素与水元素触发蒸发反应，造成1.5倍或2倍伤害。"
            "雷元素与冰元素产生超导反应，降低敌人物理抗性。风元素可以扩散其他元素。"
        ),
        "khaenriah_history.txt": (
            "坎瑞亚是五百年前被毁灭的无神之国。这个国家依靠科技和炼金术发展，不信仰任何神明。"
            "深渊教团的成员多为坎瑞亚遗民，他们被诅咒转化为深渊使徒和深渊咏者。"
        ),
        "fishing_mechanics.txt": (
            "钓鱼需要鱼竿、鱼饵和耐心。不同的鱼类需要特定的鱼饵，例如果酿饵适合钓鳉鱼。"
            "黄金钓鱼协会提供各种钓鱼相关的奖励。雷鸣仙是稻妻特有的观赏鱼。"
        ),
        "artifact_farming.txt": (
            "圣遗物分为生之花、死之羽、时之沙、空之杯和理之冠五个部位。主词条和副词条决定了圣遗物的价值。"
            "绝缘之旗印套装适合需要元素充能的角色。追忆之注连适合普通攻击输出角色。"
        ),
        "mondstadt_culture.txt": (
            "蒙德崇尚自由，由西风骑士团守护。每年举办风花节庆祝春天的到来。"
            "蒙德的特产包括蒲公英酒、苹果酒和各种以风为主题的诗歌。巴巴托斯是他们信仰的风神。"
        ),
    }

    category_dir = data_dir / "agd_readable"
    category_dir.mkdir()
    for filename, content in documents.items():
        (category_dir / filename).write_text(content, encoding="utf-8")

    (data_dir / "metadata.json").write_text(
        json.dumps({"language": localization.Language.CHS.value})
    )

    manifest_dir = data_dir / "manifest"
    manifest_dir.mkdir()
    manifest_data = [
        {
            "category": "agd_readable",
            "title": filename.replace(".txt", "").replace("_", " ").title(),
            "id": idx,
            "relative_path": f"agd_readable/{filename}",
        }
        for idx, filename in enumerate(documents.keys())
    ]
    (manifest_dir / "test.json").write_text(
        json.dumps(manifest_data, indent=2, ensure_ascii=False)
    )

    return data_dir


@pytest.fixture(scope="session")
def built_checkpoint_dir(
    test_text_dir: pathlib.Path, tmp_path_factory: pytest.TempPathFactory
) -> pathlib.Path:
    """Build a document store checkpoint from test text data (shared across session)."""
    checkpoint_dir = tmp_path_factory.mktemp("rag") / "checkpoint"
    env = {**os.environ, "ISTAROTH_TRAINING_DEVICE": "cpu"}
    script_path = _PROJECT_ROOT / "scripts" / "rag_tools.py"
    result = subprocess.run(
        ["python", str(script_path), "build", str(test_text_dir), str(checkpoint_dir)],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
        env=env,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"
    shutil.copytree(test_text_dir, checkpoint_dir / "text")
    return checkpoint_dir
