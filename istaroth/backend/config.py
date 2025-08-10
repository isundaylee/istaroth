"""Configuration for the backend server."""

import os

import attrs


@attrs.define
class BackendConfig:
    """Configuration for the backend server."""

    cors_origins: list[str] = attrs.field(
        factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )

    @classmethod
    def from_env(cls) -> "BackendConfig":
        """Create config from environment variables."""
        config = cls()

        if cors_origins := os.getenv("ISTAROTH_CORS_ORIGINS"):
            config.cors_origins = cors_origins.split(",")

        return config
