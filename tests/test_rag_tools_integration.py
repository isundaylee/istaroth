"""Integration test for rag_tools script."""

import pathlib
import subprocess
from collections.abc import Generator

import pytest


@pytest.fixture
def test_data_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create temporary directory with test text files."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()

    (data_dir / "genshin_lore.txt").write_text(
        "钟离是岩王帝君的人间形态，真实身份是摩拉克斯。\n" "温迪是风神巴巴托斯，常常以吟游诗人的身份出现。", encoding="utf-8"
    )
    (data_dir / "regions.txt").write_text(
        "蒙德以风元素为主，充满了自由的气息。\n" "璃月以岩元素为主，商业繁荣，历史悠久。", encoding="utf-8"
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


def test_complete_rag_workflow(
    test_data_dir: pathlib.Path, rag_env: pathlib.Path
) -> None:
    """Test complete RAG workflow: build -> retrieve -> search."""
    checkpoint_dir = rag_env

    # 1. Build document store
    build_result = run_rag_tools("build", str(test_data_dir))
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"
    assert "Building document store" in build_result.stdout
    assert "Total documents in store:" in build_result.stdout

    # Verify files were created
    assert checkpoint_dir.exists()
    assert (checkpoint_dir / "faiss_index").exists()
    assert (checkpoint_dir / "documents.json").exists()
    assert (checkpoint_dir / "full_texts.json").exists()

    # 2. Test retrieve command
    retrieve_result = run_rag_tools("retrieve", "钟离", "--k", "2")
    assert retrieve_result.returncode == 0, f"Retrieve failed: {retrieve_result.stderr}"
    assert "钟离" in retrieve_result.stdout or "摩拉克斯" in retrieve_result.stdout
    assert "Result 1" in retrieve_result.stdout

    # 3. Test search command
    search_result = run_rag_tools("search", "风神")
    assert search_result.returncode == 0, f"Search failed: {search_result.stderr}"
    assert (
        "Found" in search_result.stdout
        and "documents containing '风神'" in search_result.stdout
    )
    assert "巴巴托斯" in search_result.stdout or "温迪" in search_result.stdout
