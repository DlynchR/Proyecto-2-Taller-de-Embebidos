"""Cliente HTTP mínimo para Ollama (solo biblioteca estándar).

Endpoints usados:

* ``POST /v1/systemone``: modelos de decisión System One (API JEV de TypeSafe),
  disponibles en Ollama >= 0.35. Responde varias preguntas tipadas (choice,
  noul, score) sobre un mismo texto en una sola solicitud.
* ``POST /api/chat``: generación de texto con el LLM, con salida JSON
  restringida por esquema.
* ``GET /api/tags`` y ``GET /api/version``: salud y modelos instalados.
* ``POST /api/pull``: descarga de modelos (aprovisionamiento).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


class OllamaError(RuntimeError):
    """Error al comunicarse con Ollama."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class TimedResult:
    data: dict
    elapsed_ms: float


class OllamaClient:
    def __init__(self, base_url: str, keep_alive: str = "24h"):
        self.base_url = base_url.rstrip("/")
        self.keep_alive = keep_alive

    # ------------------------------------------------------------------ util
    def _request(self, method: str, path: str, payload: dict | None, timeout: float) -> dict:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("error", detail)
            except (ValueError, AttributeError):
                pass
            raise OllamaError(f"{method} {path} -> HTTP {exc.code}: {detail}", exc.code) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise OllamaError(f"{method} {path}: Ollama no responde ({exc})") from exc
        try:
            return json.loads(body.decode("utf-8")) if body else {}
        except ValueError as exc:
            raise OllamaError(f"{method} {path}: respuesta no es JSON") from exc

    # ---------------------------------------------------------------- salud
    def version(self, timeout: float = 5.0) -> str:
        return self._request("GET", "/api/version", None, timeout).get("version", "?")

    def models(self, timeout: float = 5.0) -> list[str]:
        data = self._request("GET", "/api/tags", None, timeout)
        return [m.get("name", "") for m in data.get("models", [])]

    @staticmethod
    def has_model(installed: list[str], wanted: str) -> bool:
        """Compara nombres tolerando la etiqueta implícita ``:latest``."""
        if ":" not in wanted:
            wanted = wanted + ":latest"
        normal = {n if ":" in n else n + ":latest" for n in installed}
        return wanted in normal

    # ------------------------------------------------------------ decisiones
    def systemone(self, model: str, state, questions: dict, timeout: float) -> TimedResult:
        payload = {
            "model": model,
            "state": state,
            "questions": questions,
            "keep_alive": self.keep_alive,
        }
        start = time.perf_counter()
        data = self._request("POST", "/v1/systemone", payload, timeout)
        elapsed = (time.perf_counter() - start) * 1000.0
        if "answers" not in data:
            raise OllamaError("/v1/systemone: respuesta sin 'answers'")
        return TimedResult(data, elapsed)

    # ------------------------------------------------------------ generación
    def chat(
        self,
        model: str,
        messages: list[dict],
        timeout: float,
        fmt: dict | str | None = None,
        options: dict | None = None,
        think: str = "",
    ) -> TimedResult:
        payload: dict = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        if fmt is not None:
            payload["format"] = fmt
        if options:
            payload["options"] = options
        if think.strip().lower() in ("true", "false"):
            payload["think"] = think.strip().lower() == "true"
        start = time.perf_counter()
        data = self._request("POST", "/api/chat", payload, timeout)
        elapsed = (time.perf_counter() - start) * 1000.0
        return TimedResult(data, elapsed)

    def warmup_llm(self, model: str, timeout: float = 300.0) -> float:
        """Carga el LLM en memoria sin generar texto (prompt vacío)."""
        start = time.perf_counter()
        self._request("POST", "/api/generate", {"model": model, "prompt": "", "keep_alive": self.keep_alive}, timeout)
        return (time.perf_counter() - start) * 1000.0

    # ------------------------------------------------------- aprovisionamiento
    def pull(self, model: str, timeout: float = 3600.0, progress=None) -> None:
        """Descarga un modelo mostrando el avance (respuesta en streaming)."""
        payload = json.dumps({"model": model, "stream": True}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/pull",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if "error" in event:
                        raise OllamaError(f"pull {model}: {event['error']}")
                    if progress:
                        progress(event)
        except urllib.error.HTTPError as exc:
            raise OllamaError(f"pull {model}: HTTP {exc.code}", exc.code) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OllamaError(f"pull {model}: {exc}") from exc
