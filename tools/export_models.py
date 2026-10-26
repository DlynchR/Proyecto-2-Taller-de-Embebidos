#!/usr/bin/env python3
"""Empaqueta modelos ya descargados con Ollama para precargarlos en la imagen.

En una PC con Ollama (cualquier arquitectura: los pesos GGUF son portables):

    ollama pull tev1:0.8b
    ollama pull qwen2.5:1.5b
    python3 tools/export_models.py tev1:0.8b qwen2.5:1.5b -o models/ollama-models.tar

Luego, en build/conf/local.conf (o edgeai-secrets.conf):

    EDGEAI_PRELOAD_MODELS = "1"

La receta edgeai-models extrae el tar en /var/lib/ollama/models y la Pi queda
lista sin conexión a internet desde el primer arranque.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tarfile
from pathlib import Path


def default_models_dir() -> Path:
    if os.environ.get("OLLAMA_MODELS"):
        return Path(os.environ["OLLAMA_MODELS"])
    for cand in (Path.home() / ".ollama" / "models", Path("/usr/share/ollama/.ollama/models"),
                 Path("/var/lib/ollama/models")):
        if (cand / "manifests").is_dir():
            return cand
    return Path.home() / ".ollama" / "models"


def manifest_path(name: str) -> Path:
    """Convierte 'tev1:0.8b' en registry.ollama.ai/library/tev1/0.8b."""
    model, _, tag = name.partition(":")
    tag = tag or "latest"
    parts = model.split("/")
    if len(parts) == 1:
        parts = ["registry.ollama.ai", "library", parts[0]]
    elif len(parts) == 2:
        parts = ["registry.ollama.ai", *parts]
    return Path(*parts, tag)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("modelos", nargs="+")
    p.add_argument("-d", "--models-dir", type=Path, default=default_models_dir())
    p.add_argument("-o", "--output", type=Path, default=Path("models/ollama-models.tar"))
    a = p.parse_args()

    root = a.models_dir
    entries: list[tuple[Path, str]] = []
    total = 0
    for name in a.modelos:
        rel = Path("manifests") / manifest_path(name)
        mpath = root / rel
        if not mpath.is_file():
            print(f"No encontré el manifiesto de {name} en {mpath}. ¿Ejecutó 'ollama pull {name}'?",
                  file=sys.stderr)
            return 1
        manifest = json.loads(mpath.read_text())
        entries.append((mpath, str(rel)))
        digests = [manifest["config"]["digest"], *[layer["digest"] for layer in manifest.get("layers", [])]]
        for digest in digests:
            blob = Path("blobs") / digest.replace(":", "-")
            if not (root / blob).is_file():
                print(f"Falta el blob {blob} de {name}", file=sys.stderr)
                return 1
            entries.append((root / blob, str(blob)))
            total += (root / blob).stat().st_size
        print(f"{name}: {len(digests)} archivos")

    a.output.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    with tarfile.open(a.output, "w") as tar:
        for src, arc in entries:
            if arc in seen:
                continue
            seen.add(arc)
            tar.add(src, arcname=arc)
    print(f"Listo: {a.output} ({total / 1e9:.2f} GB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
