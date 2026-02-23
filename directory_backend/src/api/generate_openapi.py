"""
Generate and persist the OpenAPI spec for the backend service.

This script is used by automation/CI to produce `interfaces/openapi.json`.

It MUST import the actual FastAPI app from `src.api.main:app` so that
routers (/auth, /residents, /audit) are included in the generated spec.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.api.main import app


def main() -> None:
    """Generate OpenAPI JSON from the FastAPI app and write it to interfaces/openapi.json."""
    spec = app.openapi()
    out_path = Path(__file__).resolve().parents[2] / "interfaces" / "openapi.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
