"""Checkpoint version endpoint."""

from fastapi import APIRouter

from istaroth.services.backend import dependencies, models
from istaroth.services.backend.utils import handle_unexpected_exception

router = APIRouter()


@router.get("/api/version", response_model=models.VersionResponse)
@handle_unexpected_exception
async def get_version(
    store_set: dependencies.DocumentStoreSet,
) -> models.VersionResponse:
    """Get version information."""
    checkpoint_versions = store_set.get_checkpoint_versions()
    return models.VersionResponse(
        checkpoint_versions={lang.value: v for lang, v in checkpoint_versions.items()}
    )
