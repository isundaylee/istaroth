"""Integration test for rag_tools script."""

import pathlib
import socket
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager

import chromadb
import pytest

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


def test_retrieve_relevant_content_with_k1(
    built_checkpoint_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that retrieval with k=1 returns the most relevant document for various queries."""
    monkeypatch.setenv("ISTAROTH_TRAINING_DEVICE", "cpu")
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
        built_checkpoint_dir,
        query_transformer=query_transform.IdentityTransformer(),
        reranker=rerank.RRFReranker(),
    )
    _test_retrieval(ds)

    # Test with external Chroma vector store
    chroma_index_path = built_checkpoint_dir / "chroma_index"
    if chroma_index_path.exists():
        with _chroma_server(str(chroma_index_path)) as port:
            external_vector_store = ChromaExternalVectorStore.create("localhost", port)

            ds_external = document_store.DocumentStore.load(
                built_checkpoint_dir,
                query_transformer=query_transform.IdentityTransformer(),
                reranker=rerank.RRFReranker(),
                external_vector_store=external_vector_store,
            )

            _test_retrieval(ds_external)
