"""Process startup: environment file, logging, and the ASGI server."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import uvicorn

from fsdemo.auth import Settings

ROOT = Path(__file__).resolve().parents[2]


def load_dotenv() -> None:
    """Load KEY=VALUE lines from .env without overriding existing variables."""
    for path in (Path.cwd() / ".env", ROOT / ".env"):
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
        return


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s %(message)s",
    )
    quiet = (
        "httpx",
        "httpx2",
        "httpcore",
        "httpcore2",
        "mcp",
        "a2a",
        "uvicorn",
    )
    for name in quiet:
        logging.getLogger(name).setLevel(logging.WARNING)


def bootstrap() -> Settings:
    load_dotenv()
    configure_logging()
    return Settings.from_env()


def serve(app: Any, host: str, port: int) -> None:
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)
