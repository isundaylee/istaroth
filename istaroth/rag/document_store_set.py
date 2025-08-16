"""Document store set for multiple languages."""

import logging
import os
import pathlib
import shutil
import subprocess
import tempfile
from urllib.request import urlopen

import attrs

from istaroth import utils
from istaroth.agd import localization
from istaroth.rag import query_transform, rerank
from istaroth.rag.document_store import DocumentStore

logger = logging.getLogger(__name__)


def _download_and_extract_checkpoint(
    language: localization.Language, target_dir: pathlib.Path
) -> None:
    """Download and extract checkpoint for a specific language.

    Args:
        language: Language code (e.g., 'chs', 'eng')
        target_dir: Directory where checkpoint should be extracted

    Raises:
        urllib.error.URLError: If download fails
        subprocess.CalledProcessError: If extraction fails
    """
    # Create URL for the checkpoint
    base_url = "https://github.com/isundaylee/istaroth/releases/latest/download"
    checkpoint_url = f"{base_url}/{language.value.lower()}.tar.gz"

    logger.info(
        "Downloading checkpoint for language '%s' from %s",
        language.name,
        checkpoint_url,
    )

    # Create target directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)

    # Download to temporary file
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
        temp_path = pathlib.Path(temp_file.name)
        try:
            with urlopen(checkpoint_url) as response:
                shutil.copyfileobj(response, temp_file)
            logger.info("Downloaded checkpoint to temporary file: %s", temp_path)
        except:
            temp_path.unlink(missing_ok=True)
            raise

    # Extract tar.gz to target directory using command line tar
    try:
        subprocess.run(
            ["tar", "-xzf", str(temp_path), "-C", str(target_dir)], check=True
        )
        logger.info("Successfully extracted checkpoint to %s", target_dir)
    finally:
        # Clean up temporary file
        temp_path.unlink(missing_ok=True)


def _maybe_download_checkpoint(
    language: localization.Language, store_path: pathlib.Path
) -> None:
    """Download checkpoint if ISTAROTH_DOWNLOAD_CHECKPOINT_RELEASE is set and
    directory doesn't exist."""
    if os.getenv("ISTAROTH_DOWNLOAD_CHECKPOINT_RELEASE") != "1":
        return

    # Check if directory exists and is non-empty
    if store_path.exists():
        logger.debug("Document store directory already exists: %s", store_path)
        return

    # Directory doesn't exist or is empty, download checkpoint
    logger.info(
        "Document store directory %s doesn't exist, downloading checkpoint", store_path
    )

    _download_and_extract_checkpoint(language, store_path)
    logger.info("Successfully downloaded and extracted checkpoint to %s", store_path)


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

                # Ensure checkpoint directory exists (download if needed)
                _maybe_download_checkpoint(language, store_path)

                if not store_path.exists():
                    raise ValueError(
                        f"Document store path does not exist for language '{language.name}': {store_path}"
                    )

                logger.info(
                    "Loading document store for language '%s' from %s",
                    language.name,
                    store_path,
                )
                stores[language] = DocumentStore.load(
                    store_path,
                    query_transformer=query_transform.QueryTransformer.from_env(),
                    reranker=rerank.Reranker.from_env(),
                )

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
