"""Integration test for rag_tools script."""

import json
import pathlib
import socket
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager

import chromadb
import pytest

from istaroth.agd import localization
from istaroth.rag import document_store, query_transform, rerank
from istaroth.rag.vector_store import ChromaExternalVectorStore


def _find_free_port() -> int:
    """Find a free port for the Chroma server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@contextmanager
def _chroma_server(temp_dir: str) -> Generator[int, None, None]:
    """Start a Chroma server and return a connected client."""
    port = _find_free_port()
    server_process = subprocess.Popen(
        ["chroma", "run", "--path", temp_dir, "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Wait for server to start and test connection
        max_retries = 10
        for i in range(max_retries):
            try:
                # Test if server is ready
                test_client = chromadb.HttpClient(host=f"http://localhost:{port}")
                test_client.heartbeat()
                break
            except Exception:
                if i == max_retries - 1:
                    raise
                time.sleep(1)

        # Return connected client
        yield port

    finally:
        # Clean up the server process
        server_process.terminate()

        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()


@pytest.fixture
def test_text_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create temporary directory with test text files containing diverse content."""
    data_dir = tmp_path / "test_text"
    data_dir.mkdir()

    # Create 10 documents with very different, distinct topics
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

    for filename, content in documents.items():
        (data_dir / filename).write_text(content, encoding="utf-8")

    (data_dir / "metadata.json").write_text(
        json.dumps({"language": localization.Language.CHS.value})
    )

    # Create manifest.json file required by rag_tools
    manifest_data = [{"relative_path": filename} for filename in documents.keys()]
    (data_dir / "manifest.json").write_text(
        json.dumps(manifest_data, indent=2, ensure_ascii=False)
    )

    return data_dir


@pytest.fixture
def rag_env(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[pathlib.Path, None, None]:
    """Set up RAG environment variables."""
    checkpoint_dir = tmp_path / "checkpoint"
    monkeypatch.setenv("ISTAROTH_DOCUMENT_STORE", str(checkpoint_dir))
    monkeypatch.setenv("ISTAROTH_TRAINING_DEVICE", "cpu")
    yield checkpoint_dir


def run_rag_tools(*args: str) -> subprocess.CompletedProcess:
    """Run rag_tools script with given arguments."""
    script_path = pathlib.Path(__file__).parent.parent / "scripts" / "rag_tools.py"
    cmd = ["python", str(script_path)] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(pathlib.Path(__file__).parent.parent),
    )


def test_retrieve_relevant_content_with_k1(
    test_text_dir: pathlib.Path, rag_env: pathlib.Path
) -> None:
    """Test that retrieval with k=1 returns the most relevant document for various queries."""
    checkpoint_dir = rag_env

    # Build document store
    build_result = run_rag_tools("build", str(test_text_dir), str(checkpoint_dir))
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"
    assert "Building document store" in build_result.stderr

    # Test cases: each query should retrieve the most relevant document
    test_queries = [
        ("钟离的真实身份", "摩拉克斯"),
        ("如何制作蒙德披萨", "蘑菇"),
    ]

    def _test_retrieval(ds: document_store.DocumentStore) -> None:
        """Test retrieval with the given document store."""
        for query, expected_keywords in test_queries:
            r = ds.retrieve(query, k=1, chunk_context=0)
            [(_, docs)] = r.results
            [doc] = docs
            assert expected_keywords in doc.page_content

    # Test with default vector store (from config)
    ds = document_store.DocumentStore.load(
        checkpoint_dir,
        query_transformer=query_transform.IdentityTransformer(),
        reranker=rerank.RRFReranker(),
    )
    _test_retrieval(ds)

    # Test with external Chroma vector store
    # Launch server directly using the existing chroma_index from checkpoint
    chroma_index_path = checkpoint_dir / "chroma_index"
    if chroma_index_path.exists():
        with _chroma_server(str(chroma_index_path)) as port:
            # Create external vector store instance using existing data
            external_vector_store = ChromaExternalVectorStore.create("localhost", port)

            # Load DocumentStore with explicit external vector store
            ds_external = document_store.DocumentStore.load(
                checkpoint_dir,
                query_transformer=query_transform.IdentityTransformer(),
                reranker=rerank.RRFReranker(),
                external_vector_store=external_vector_store,
            )

            # Test the same queries with external Chroma
            _test_retrieval(ds_external)
