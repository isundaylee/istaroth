"""Embedding backend selection for RAG pipeline."""

import functools
import logging
import os

from langchain_core import embeddings as lc_embeddings

logger = logging.getLogger(__name__)


@functools.cache
def create_embeddings() -> lc_embeddings.Embeddings:
    """Create embeddings instance based on ISTAROTH_EMBEDDINGS env var.

    - "local" (default): HuggingFace BAAI/bge-m3
    - "deepinfra": DeepInfra-hosted BAAI/bge-m3 via OpenAI-compatible API
    """
    match (backend := os.environ.get("ISTAROTH_EMBEDDINGS", "local")):
        case "local":
            from langchain_huggingface import HuggingFaceEmbeddings

            logger.info("Using local HuggingFace embeddings")
            return HuggingFaceEmbeddings(
                model_name="BAAI/bge-m3",
                model_kwargs={
                    "device": os.getenv("ISTAROTH_TRAINING_DEVICE", "cuda")
                },
                encode_kwargs={"normalize_embeddings": True},
            )
        case "deepinfra":
            from langchain_openai import OpenAIEmbeddings

            logger.info("Using DeepInfra embeddings")
            return OpenAIEmbeddings(
                base_url="https://api.deepinfra.com/v1/openai",
                model="BAAI/bge-m3",
                api_key=os.environ["DEEPINFRA_API_KEY"],
                check_embedding_ctx_length=False,
            )
        case _:
            raise ValueError(f"Unknown ISTAROTH_EMBEDDINGS: {backend}")
