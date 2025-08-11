"""Document store set for multiple languages."""

import logging
import os
import pathlib

import attrs

from istaroth import utils
from istaroth.agd import localization
from istaroth.rag.document_store import DocumentStore

logger = logging.getLogger(__name__)


@attrs.define
class DocumentStoreSet:
    """Set of document stores for different languages."""

    _stores: dict[localization.Language, DocumentStore] = attrs.field()

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

            stores = {}
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
                if not store_path.exists():
                    raise ValueError(
                        f"Document store path does not exist for language '{language.name}': {store_path}"
                    )

                logger.info(
                    "Loading document store for language '%s' from %s",
                    language.name,
                    store_path,
                )
                stores[language] = DocumentStore.load(store_path)

            if not stores:
                raise ValueError(
                    "No document stores configured in ISTAROTH_DOCUMENT_STORE_SET"
                )

            language_names = [lang.name for lang in stores.keys()]
            logger.info(
                "Document store set initialized with languages: %s", language_names
            )
            return cls(stores)

    def get_store(self, language: localization.Language) -> DocumentStore:
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
