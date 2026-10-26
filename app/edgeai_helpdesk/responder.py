"""Ruta lenta: redacción de la respuesta con el LLM local.

El modelo de decisión ya eligió la categoría; aquí solo se inyecta la base de
conocimiento de *esa* categoría (recuperación guiada por la decisión), lo que
mantiene el prompt corto y reduce el tiempo de inferencia en la RPi4.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .config import Config
from .decision import AUTOSERVICIO, SIN_CLASIFICAR, Decision
from .ollama_client import OllamaClient, OllamaError

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "respuesta": {"type": "string"},
        "resumen": {"type": "string"},
    },
    "required": ["respuesta", "resumen"],
}


@dataclass
class Reply:
    respuesta: str
    resumen: str
    latencia_ms: float
    modelo: str
    ok: bool
    error: str = ""


def _nivel_texto(dominio: dict, nivel: int) -> str:
    niveles = dominio["urgencia"]
    nivel = max(0, min(nivel, len(niveles) - 1))
    return niveles[nivel].split(":")[0].strip()


def build_messages(dominio: dict, texto: str, decision: Decision) -> list[dict]:
    servicio = dominio["servicio"]
    cat = dominio["categorias"].get(decision.categoria)
    if cat:
        conocimiento = "\n".join(f"- {linea}" for linea in cat.get("conocimiento", []))
        categoria_txt = f"{decision.categoria} ({cat['descripcion']})"
    else:
        conocimiento = "- No hay información específica; indique que un encargado revisará el caso."
        categoria_txt = SIN_CLASIFICAR

    if decision.estado == AUTOSERVICIO:
        objetivo = "Dé pasos concretos para que la persona lo resuelva por su cuenta."
    else:
        objetivo = "Confirme que el caso quedó en la cola y dé indicaciones mientras le atienden."

    extra = ""
    if decision.datos_sensibles >= 0.5:
        extra = " El mensaje parece incluir datos sensibles: recuerde no compartir contraseñas ni datos personales."

    system = (
        f"Eres el asistente de la {servicio['nombre']}. Responde siempre en español, "
        "con tono amable y profesional, en un máximo de 90 palabras. "
        "Usa solo la información de la base de conocimiento; no inventes horarios, "
        "nombres, correos ni teléfonos. Si la información no alcanza, di que un "
        "encargado revisará el caso. Devuelve JSON con 'respuesta' (texto para la "
        "persona) y 'resumen' (máximo 12 palabras, para la cola de atención)."
    )
    user = (
        f"Categoría: {categoria_txt}\n"
        f"Urgencia: {_nivel_texto(dominio, decision.urgencia_nivel)}\n"
        f"Objetivo: {objetivo}{extra}\n"
        f"Base de conocimiento:\n{conocimiento}\n\n"
        f"Mensaje de la persona:\n{texto.strip()}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_content(content: str, texto: str) -> tuple[str, str, bool]:
    """Extrae respuesta y resumen. Si el JSON viene mal, usa el texto crudo."""
    content = (content or "").strip()
    try:
        data = json.loads(content)
        respuesta = str(data.get("respuesta", "")).strip()
        resumen = str(data.get("resumen", "")).strip()
        if respuesta:
            return respuesta, resumen or texto.strip()[:80], True
    except (ValueError, AttributeError):
        pass
    if content:
        return content, texto.strip()[:80], False
    return "", texto.strip()[:80], False


class Responder:
    def __init__(self, cfg: Config, client: OllamaClient):
        self.cfg = cfg
        self.client = client

    def reply(self, texto: str, decision: Decision) -> Reply:
        o = self.cfg.ollama
        messages = build_messages(self.cfg.dominio, texto, decision)
        try:
            result = self.client.chat(
                o.modelo_llm,
                messages,
                timeout=o.timeout_llm,
                fmt=RESPONSE_SCHEMA,
                options={
                    "temperature": o.llm_temperatura,
                    "num_ctx": o.llm_num_ctx,
                    "num_predict": o.llm_num_predict,
                },
                think=o.llm_think,
            )
        except OllamaError as exc:
            plantilla = self.cfg.dominio["plantillas"]["error_llm"]
            return Reply(plantilla, texto.strip()[:80], 0.0, o.modelo_llm, False, str(exc))
        content = result.data.get("message", {}).get("content", "")
        respuesta, resumen, parsed = parse_content(content, texto)
        if not respuesta:
            plantilla = self.cfg.dominio["plantillas"]["error_llm"]
            return Reply(plantilla, resumen, result.elapsed_ms, o.modelo_llm, False, "respuesta vacía")
        return Reply(
            respuesta,
            resumen,
            round(result.elapsed_ms, 1),
            result.data.get("model", o.modelo_llm),
            True,
            "" if parsed else "JSON inválido; se usó el texto crudo",
        )
