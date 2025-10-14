#!/usr/bin/env python3
"""
Export the FastAPI OpenAPI schema to interfaces/openapi.json.

Usage:
  python -m scripts.export_openapi
  or
  python scripts/export_openapi.py

Notes:
- This imports the app from src.api.main and serializes app.openapi().
- Output path: MCPServer/interfaces/openapi.json (relative to this script).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Ensure package imports resolve when executed directly
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

from src.api.main import app  # type: ignore  # noqa: E402


def main() -> None:
    target = PROJECT_ROOT / "interfaces" / "openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    with target.open("w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, sort_keys=False)
    print(f"Wrote OpenAPI schema to {target}")


if __name__ == "__main__":
    main()
