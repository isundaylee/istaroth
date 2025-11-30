"""Document store set for multiple languages."""

import logging
import os
import pathlib

import attrs

from istaroth import utils
from istaroth.agd import localization
from istaroth.rag import document_store, query_transform, rerank, text_set, vector_store

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


@attrs.define
class DocumentStoreSet:
    """Set of document stores for different languages."""

    _stores: dict[localization.Language, document_store.DocumentStore] = attrs.field()
    _checkpoint_paths: dict[localization.Language, pathlib.Path] = attrs.field()

    @classmethod
    def from_env(cls) -> "DocumentStoreSet":
        """Create from ISTAROTH_DOCUMENT_STORE_SET env var (CHS:path,ENG:path)."""
        with utils.timer("document store set initialization from environment"):
            store_set_str = os.getenv("ISTAROTH_DOCUMENT_STORE_SET")
            if not store_set_str:
                raise ValueError(
                    "ISTAROTH_DOCUMENT_STORE_SET environment variable is required. "
                    "Expected format: LANG1:path1,LANG2:path2"
                )

            # Parse external Chroma servers configuration
            external_chroma_servers = _parse_external_chroma_servers()

            stores = {}
            checkpoint_paths = {}
            pairs = store_set_str.split(",")

            for pair in pairs:
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
                        f"Invalid language '{language_str}' in ISTAROTH_DOCUMENT_STORE_SET. Available languages: {available}"
                    ) from e

                store_path = pathlib.Path(path_str)
                checkpoint_paths[language] = store_path

                # Check if this language should use external Chroma server
                if language in external_chroma_servers:
                    host, port = external_chroma_servers[language]
                    logger.info(
                        "Loading document store for language '%s' from external Chroma server %s:%d",
                        language.name,
                        host,
                        port,
                    )

                    # Create external vector store
                    external_vs = vector_store.ChromaExternalVectorStore.create(
                        host, port
                    )
                else:
                    external_vs = None

                # Ensure checkpoint directory exists
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

            if not stores:
                raise ValueError(
                    "No document stores configured in ISTAROTH_DOCUMENT_STORE_SET"
                )

            language_names = [lang.name for lang in stores.keys()]
            logger.info(
                "Document store set initialized with languages: %s", language_names
            )
            return cls(stores, checkpoint_paths)

    def get_store(
        self, language: localization.Language
    ) -> document_store.DocumentStore:
        """Get document store for language."""
        if language not in self._stores:
            available = ", ".join(lang.name for lang in self._stores.keys())
            raise KeyError(
                f"Language '{language.name}' not available. Available languages: {available}"
            )

        return self._stores[language]

    @property
    def available_languages(self) -> list[localization.Language]:
        """Available languages."""
        return list(self._stores.keys())

    def get_text_set(self, language: localization.Language) -> text_set.TextSet:
        """Get TextSet for a language."""
        if language not in self._checkpoint_paths:
            available = ", ".join(lang.name for lang in self._checkpoint_paths.keys())
            raise KeyError(
                f"Language '{language.name}' not available. Available languages: {available}"
            )

        checkpoint_path = self._checkpoint_paths[language]
        text_path = checkpoint_path / "text"
        return text_set.TextSet(text_path=text_path, language=language)
