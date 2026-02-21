"""Multi-language container exposing both Retriever and TextSet views.

A DocumentStoreSet holds one Retriever and one TextSet per language, all
built from the same checkpoint directory. Retriever provides chunked
hybrid search; TextSet provides manifest-based catalog access to complete files.

Supports two modes:
- **Local**: loads full DocumentStore (BM25 + vector + documents) in-process
- **Remote**: uses a retrieval microservice via RetrievalClient, no heavy data
"""

import logging
import os
import pathlib

import attrs

from istaroth import utils
from istaroth.agd import localization
from istaroth.rag import (
    document_store,
    query_transform,
    rerank,
    retrieval_client,
    text_set,
    types,
    vector_store,
)

logger = logging.getLogger(__name__)


def _parse_external_chroma_servers() -> dict[localization.Language, tuple[str, int]]:
    """Parse ISTAROTH_EXTERNAL_CHROMA_SERVERS environment variable."""
    external_chroma_servers: dict[localization.Language, tuple[str, int]] = {}
    external_servers_str = os.getenv("ISTAROTH_EXTERNAL_CHROMA_SERVERS")

    if not external_servers_str:
        return external_chroma_servers

    for server_pair in external_servers_str.split(","):
        parts = server_pair.split(":", 2)
        if len(parts) != 3:
            raise ValueError(
                f"Invalid format in ISTAROTH_EXTERNAL_CHROMA_SERVERS: '{server_pair}'. "
                "Expected format: LANG:host:port"
            )

        language_str, host, port_str = parts
        language = localization.Language(language_str.strip().upper())
        host = host.strip()
        port = int(port_str.strip())

        external_chroma_servers[language] = (host, port)

    return external_chroma_servers


def _parse_checkpoint_paths() -> dict[localization.Language, pathlib.Path]:
    """Parse ISTAROTH_DOCUMENT_STORE_SET into language -> path mapping."""
    store_set_str = os.getenv("ISTAROTH_DOCUMENT_STORE_SET")
    if not store_set_str:
        raise ValueError(
            "ISTAROTH_DOCUMENT_STORE_SET environment variable is required. "
            "Expected format: LANG1:path1,LANG2:path2"
        )

    checkpoint_paths: dict[localization.Language, pathlib.Path] = {}
    for pair in store_set_str.split(","):
        if ":" not in pair:
            raise ValueError(
                f"Invalid format in ISTAROTH_DOCUMENT_STORE_SET: '{pair}'. "
                "Expected format: LANG:path"
            )

        language_str, path_str = pair.split(":", 1)
        language_str = language_str.strip()
        path_str = path_str.strip()

        if not language_str or not path_str:
            raise ValueError(
                f"Invalid language or path in ISTAROTH_DOCUMENT_STORE_SET: '{pair}'"
            )

        try:
            language = localization.Language(language_str.upper())
        except ValueError as e:
            available = ", ".join(lang.name for lang in localization.Language)
            raise ValueError(
                f"Invalid language '{language_str}' in ISTAROTH_DOCUMENT_STORE_SET. "
                f"Available languages: {available}"
            ) from e

        checkpoint_paths[language] = pathlib.Path(path_str)

    if not checkpoint_paths:
        raise ValueError("No document stores configured in ISTAROTH_DOCUMENT_STORE_SET")

    return checkpoint_paths


@attrs.define
class DocumentStoreSet:
    """Per-language registry of Retriever (search) and TextSet (catalog).

    Initialized from checkpoint paths via ``from_env()`` (local mode, loads
    full DocumentStore) or ``from_retrieval_service()`` (remote mode, uses
    lightweight HTTP client). Use ``get_store()`` for hybrid retrieval and
    ``get_text_set()`` for browsing / citation access.
    """

    _stores: dict[localization.Language, types.Retriever] = attrs.field()
    _checkpoint_paths: dict[localization.Language, pathlib.Path] = attrs.field()
    _text_sets: dict[localization.Language, text_set.TextSet] = attrs.field(
        factory=dict, init=False
    )

    @classmethod
    def from_env(cls) -> "DocumentStoreSet":
        """Create from ISTAROTH_DOCUMENT_STORE_SET env var, loading full DocumentStores."""
        with utils.timer("document store set initialization from environment"):
            checkpoint_paths = _parse_checkpoint_paths()
            external_chroma_servers = _parse_external_chroma_servers()

            stores: dict[localization.Language, types.Retriever] = {}
            for language, store_path in checkpoint_paths.items():
                # Check if this language should use external Chroma server
                if language in external_chroma_servers:
                    host, port = external_chroma_servers[language]
                    logger.info(
                        "Loading document store for language '%s' from external Chroma server %s:%d",
                        language.name,
                        host,
                        port,
                    )
                    external_vs = vector_store.ChromaExternalVectorStore.create(
                        host, port
                    )
                else:
                    external_vs = None

                if not store_path.exists():
                    raise ValueError(
                        f"Document store path does not exist for language '{language.name}': {store_path}. "
                        f"Please run 'scripts/checkpoint_tools.py download' to download checkpoints."
                    )

                logger.info(
                    "Loading document store for language '%s' from %s",
                    language.name,
                    store_path,
                )
                stores[language] = document_store.DocumentStore.load(
                    store_path,
                    query_transformer=query_transform.QueryTransformer.from_env(),
                    reranker=rerank.Reranker.from_env(),
                    external_vector_store=external_vs,
                )

            language_names = [lang.name for lang in stores.keys()]
            logger.info(
                "Document store set initialized (local) with languages: %s",
                language_names,
            )
            return cls(stores, checkpoint_paths)

    @classmethod
    def from_retrieval_service(cls) -> "DocumentStoreSet":
        """Create using remote retrieval service -- no heavy in-process data."""
        with utils.timer("document store set initialization (retrieval service)"):
            checkpoint_paths = _parse_checkpoint_paths()

            stores: dict[localization.Language, types.Retriever] = {}
            for language in checkpoint_paths:
                stores[language] = retrieval_client.RetrievalClient.from_env(
                    language.value
                )

            language_names = [lang.name for lang in stores.keys()]
            logger.info(
                "Document store set initialized (remote) with languages: %s",
                language_names,
            )
            return cls(stores, checkpoint_paths)

    def _validate_language(self, language: localization.Language) -> None:
        if language not in self._stores:
            available = ", ".join(lang.name for lang in self._stores.keys())
            raise KeyError(
                f"Language '{language.name}' not available. Available languages: {available}"
            )

    def get_store(self, language: localization.Language) -> types.Retriever:
        """Get retriever for language."""
        self._validate_language(language)
        return self._stores[language]

    @property
    def available_languages(self) -> list[localization.Language]:
        """Available languages."""
        return list(self._stores.keys())

    def get_checkpoint_versions(self) -> dict[localization.Language, str | None]:
        """Read checkpoint versions from .release tag files."""
        versions: dict[localization.Language, str | None] = {}
        for language, checkpoint_path in self._checkpoint_paths.items():
            tag_file = checkpoint_path.parent / f"{checkpoint_path.name}.release"
            versions[language] = (
                tag_file.read_text().strip() if tag_file.exists() else None
            )
        return versions

    def get_text_set(self, language: localization.Language) -> text_set.TextSet:
        """Get TextSet for a language (cached)."""
        if language not in self._text_sets:
            self._validate_language(language)
            checkpoint_path = self._checkpoint_paths[language]
            self._text_sets[language] = text_set.TextSet(
                text_path=checkpoint_path / "text", language=language
            )
        return self._text_sets[language]
