#!/usr/bin/env python3
"""Generate OpenAPI specification from FastAPI app without running the server."""

import json
import pathlib
import sys
from pathlib import Path

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth.backend.app import create_app


def generate_openapi_spec() -> None:
    """Generate OpenAPI JSON specification from the FastAPI app."""
    app = create_app()
    openapi_spec = app.openapi()

    output_path = Path(__file__).parent.parent / "frontend" / "openapi.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_spec, f, indent=2, ensure_ascii=False)

    print(f"✅ OpenAPI specification generated successfully at {output_path}")


if __name__ == "__main__":
    generate_openapi_spec()
