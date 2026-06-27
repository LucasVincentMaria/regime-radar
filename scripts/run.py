"""
Convenience launcher.

Starts the FastAPI dashboard (which also boots the background scheduler via its
lifespan handler). This is the single entry point for running 24/7 on localhost.

Usage:
    py scripts/run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is importable when run as a script.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn

import config


def main() -> None:
    """Run the uvicorn server with settings from config/.env."""
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
