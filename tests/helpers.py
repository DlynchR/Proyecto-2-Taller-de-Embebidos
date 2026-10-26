"""Utilidades comunes de las pruebas."""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "tools"))

from edgeai_helpdesk.config import load_config  # noqa: E402


def make_config(tmp: str, ollama_url: str = "http://127.0.0.1:9", leds_dir: str | None = None):
    os.environ["EDGEAI_DB"] = os.path.join(tmp, "tickets.db")
    os.environ["EDGEAI_OLLAMA_URL"] = ollama_url
    os.environ["EDGEAI_LEDS_DIR"] = leds_dir or os.path.join(tmp, "leds")
    try:
        cfg = load_config(str(ROOT / "app" / "config" / "helpdesk.dev.conf"))
    finally:
        for k in ("EDGEAI_DB", "EDGEAI_OLLAMA_URL", "EDGEAI_LEDS_DIR"):
            os.environ.pop(k, None)
    return cfg


def tempdir():
    return tempfile.TemporaryDirectory(prefix="edgeai-test-")


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
