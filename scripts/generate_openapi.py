#!/usr/bin/env python3
"""Generate OpenAPI specification from FastAPI app without running the server."""

import pathlib
import sys
from pathlib import Path

import orjson

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.services.backend.app import create_app


def generate_openapi_spec() -> None:
    """Generate OpenAPI JSON specification from the FastAPI app."""
    app = create_app()
    openapi_spec = app.openapi()

    output_path = Path(__file__).parent.parent / "frontend" / "openapi.json"
    output_path.write_bytes(orjson.dumps(openapi_spec, option=orjson.OPT_INDENT_2))

    print(f"✅ OpenAPI specification generated successfully at {output_path}")


if __name__ == "__main__":
    generate_openapi_spec()
