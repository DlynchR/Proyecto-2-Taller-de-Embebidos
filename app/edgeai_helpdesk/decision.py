"""Ruta rápida: clasificación con el modelo de decisión System One (JEV).

Una sola llamada a ``/v1/systemone`` responde seis preguntas tipadas sobre la
consulta. Luego una política determinista (umbrales configurables) convierte
esas probabilidades en un estado del tiquete. El LLM solo se usa después, y
solo si la política lo permite.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field

from .config import Config
from .ollama_client import OllamaClient, OllamaError

# Estados del tiquete
EN_COLA = "en_cola"
AUTOSERVICIO = "autoservicio"
RECHAZADO = "rechazado"
FUERA_ALCANCE = "fuera_alcance"
ATENDIDO = "atendido"
ESTADOS = (EN_COLA, AUTOSERVICIO, RECHAZADO, FUERA_ALCANCE, ATENDIDO)

SIN_CLASIFICAR = "sin_clasificar"


@dataclass
class Decision:
    categoria: str
    categoria_conf: float
    categoria_probs: dict
    urgencia_score: float
    urgencia_nivel: int
    en_alcance: float
    apropiado: float
    datos_sensibles: float
    autoservicio: float
    estado: str = EN_COLA
    revision_manual: bool = False
    riesgo: bool = False
    usar_llm: bool = True
    motivo: str = ""
    # Clave de 'plantillas' con la respuesta fija (riesgo/emergencia); vacía = redacta el LLM.
    plantilla: str = ""
    latencia_ms: float = 0.0
    modelo: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def build_questions(dominio: dict) -> dict:
    """Construye las preguntas tipadas a partir de ``categorias.json``."""
    p = dominio["preguntas"]
    categorias = {key: cat["descripcion"] for key, cat in dominio["categorias"].items()}
    return {
        "categoria": {
            "type": "choice",
            "instructions": p["categoria"],
            "criteria": categorias,
        },
        "urgencia": {
            "type": "score",
            "instructions": p["urgencia"],
            "criteria": list(dominio["urgencia"]),
        },
        "en_alcance": {
            "type": "noul",
            "instructions": p["en_alcance"],
        },
        "apropiado": {
            "type": "noul",
            "instructions": p["apropiado"],
            "criteria": {
                "true": "Mensaje respetuoso; puede ser informal o expresar una queja sin groserías.",
                "false": "Groserías o insultos (también contra el servicio), acoso, amenazas, spam o contenido sexual.",
            },
        },
        "datos_sensibles": {
            "type": "noul",
            "instructions": p["datos_sensibles"],
        },
        "autoservicio": {
            "type": "noul",
            "instructions": p["autoservicio"],
        },
    }


def build_state(dominio: dict, texto: str) -> dict:
    servicio = dominio["servicio"]
    return {
        "servicio": servicio["nombre"],
        "que_atiende": servicio["descripcion"],
        "mensaje_del_usuario": texto.strip(),
    }


def _noul(answers: dict, key: str, default: float) -> float:
    try:
        return float(answers[key]["noul"])
    except (KeyError, TypeError, ValueError):
        return default


def parse_answers(answers: dict, dominio: dict) -> Decision:
    cat = answers.get("categoria", {})
    probs = cat.get("probabilities") or {}
    categoria = cat.get("choice") or (max(probs, key=probs.get) if probs else SIN_CLASIFICAR)
    if categoria not in dominio["categorias"]:
        categoria = SIN_CLASIFICAR
    urg = answers.get("urgencia", {})
    max_nivel = len(dominio["urgencia"]) - 1
    try:
        score = float(urg.get("score", 1.0))
    except (TypeError, ValueError):
        score = 1.0
    score = min(max(score, 0.0), float(max_nivel))
    return Decision(
        categoria=categoria,
        categoria_conf=float(cat.get("confidence", 0.0) or 0.0),
        categoria_probs={k: round(float(v), 4) for k, v in probs.items()},
        urgencia_score=round(score, 3),
        urgencia_nivel=int(score + 0.5),
        en_alcance=_noul(answers, "en_alcance", 1.0),
        apropiado=_noul(answers, "apropiado", 1.0),
        datos_sensibles=_noul(answers, "datos_sensibles", 0.0),
        autoservicio=_noul(answers, "autoservicio", 0.0),
    )


def parse_cuts(texto: str, niveles: int) -> list[float] | None:
    """Lee ``cortes_urgencia`` ("0.8, 1.6, 2.4"). Devuelve None si no es válido."""
    try:
        cortes = [float(x) for x in str(texto or "").replace(";", ",").split(",") if x.strip()]
    except ValueError:
        return None
    if len(cortes) != niveles - 1 or cortes != sorted(cortes):
        return None
    return cortes


def urgency_level(score: float, cortes: list[float] | None, niveles: int) -> int:
    """Convierte el puntaje esperado (0..niveles-1) en un nivel discreto.

    El modelo devuelve el promedio ponderado de los niveles. Un modelo pequeño
    reparte probabilidad entre todos y el promedio se carga hacia el centro, así
    que redondear casi nunca da el nivel 0 ("baja"). Los cortes compensan ese sesgo.
    """
    if cortes is None:
        return min(int(score + 0.5), niveles - 1)
    return sum(1 for c in cortes if score >= c)


def _normalize(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def detect_risk(texto: str, dominio: dict, regla: str = "riesgo") -> bool:
    """Regla determinista: palabras de 'riesgo' (humo, chispas...) o de 'emergencia' (armas, desmayos...)."""
    palabras = (dominio.get(regla) or {}).get("palabras") or []
    if not texto or not palabras:
        return False
    norm = _normalize(texto)
    return any(re.search(rf"\b{re.escape(_normalize(p))}\b", norm) for p in palabras)


def apply_risk(decision: Decision, dominio: dict, regla: str = "riesgo") -> Decision:
    """Marca el riesgo: urgencia máxima, la categoría de la regla y su respuesta fija (si existen)."""
    r = dominio.get(regla) or {}
    max_nivel = len(dominio["urgencia"]) - 1
    decision.riesgo = True
    decision.urgencia_nivel = max_nivel
    decision.urgencia_score = max(decision.urgencia_score, float(max_nivel))
    categoria = r.get("categoria")
    if categoria in dominio["categorias"]:
        decision.categoria = categoria
    plantilla = r.get("plantilla", "")
    decision.plantilla = plantilla if plantilla in dominio["plantillas"] else ""
    return decision


def _reject(decision: Decision) -> Decision:
    decision.estado = RECHAZADO
    decision.usar_llm = False
    decision.plantilla = ""
    decision.motivo = "Contenido no apropiado"
    return decision


def apply_policy(decision: Decision, cfg: Config, texto: str = "") -> Decision:
    """Política determinista: convierte probabilidades en un estado."""
    pol = cfg.politica
    dominio = cfg.dominio
    niveles = len(dominio["urgencia"])
    cortes = parse_cuts(pol.cortes_urgencia, niveles)
    decision.urgencia_nivel = urgency_level(decision.urgencia_score, cortes, niveles)
    emergencia = detect_risk(texto, dominio, "emergencia")
    if emergencia:
        apply_risk(decision, dominio, "emergencia")
    elif detect_risk(texto, dominio):
        apply_risk(decision, dominio)

    # Claramente ofensivo: se rechaza siempre, salvo una emergencia (armas, heridos):
    # quien la reporta puede estar alterado y el aviso no se puede perder.
    if decision.apropiado < pol.umbral_ofensivo and not emergencia:
        return _reject(decision)
    # Un riesgo o una emergencia nunca se descartan como fuera de alcance.
    if decision.en_alcance < pol.umbral_alcance and not decision.riesgo:
        decision.estado = FUERA_ALCANCE
        decision.usar_llm = False
        decision.motivo = "Fuera del alcance del servicio"
        return decision
    # Dudoso (entre umbral_ofensivo y umbral_apropiado): el modelo también baja
    # 'apropiado' en preguntas ajenas (p. ej. una receta), por eso se decide después
    # del alcance; si está en alcance y no es claramente apropiado, se rechaza.
    # Un riesgo no se rechaza aquí: el modelo baja 'apropiado' cuando el mensaje
    # menciona fuego o armas, aunque sea un aviso legítimo.
    if decision.apropiado < pol.umbral_apropiado and not decision.riesgo:
        return _reject(decision)

    # Con respuesta fija (riesgo/emergencia) no se espera al LLM.
    decision.usar_llm = not decision.plantilla
    if emergencia:
        decision.motivo = "Emergencia de seguridad o salud: atender de inmediato"
    elif decision.riesgo:
        decision.motivo = "Riesgo para personas o equipos: atender de inmediato"
    elif decision.categoria == SIN_CLASIFICAR or decision.categoria_conf < pol.umbral_confianza:
        decision.revision_manual = True
        elegida = decision.categoria
        # Con poca confianza el modelo tiende a elegir la categoría más amplia
        # (soporte técnico). Se envía a la categoría de respaldo para que un
        # encargado la clasifique.
        if elegida != SIN_CLASIFICAR and pol.categoria_dudosa in dominio["categorias"]:
            decision.categoria = pol.categoria_dudosa
        decision.motivo = f"Clasificación dudosa (modelo: {elegida}): revisar manualmente"

    urgente = decision.urgencia_nivel >= pol.nivel_urgente
    if (
        not urgente
        and not decision.revision_manual
        and decision.autoservicio >= pol.umbral_autoservicio
    ):
        decision.estado = AUTOSERVICIO
        decision.motivo = decision.motivo or "Se puede resolver con instrucciones"
    else:
        decision.estado = EN_COLA
        if urgente and not decision.motivo:
            decision.motivo = "Urgencia alta"
    return decision


def fallback_decision(reason: str, dominio: dict) -> Decision:
    """Decisión de respaldo cuando el modelo de decisión no está disponible.

    El tiquete no se pierde: entra a la cola con urgencia media y marcado para
    revisión manual (degradación controlada).
    """
    medio = min(1, len(dominio["urgencia"]) - 1)
    return Decision(
        categoria=SIN_CLASIFICAR,
        categoria_conf=0.0,
        categoria_probs={},
        urgencia_score=float(medio),
        urgencia_nivel=medio,
        en_alcance=1.0,
        apropiado=1.0,
        datos_sensibles=0.0,
        autoservicio=0.0,
        estado=EN_COLA,
        revision_manual=True,
        usar_llm=True,
        motivo=f"Clasificación no disponible: {reason}",
    )


class Decider:
    def __init__(self, cfg: Config, client: OllamaClient):
        self.cfg = cfg
        self.client = client
        self.questions = build_questions(cfg.dominio)

    def decide(self, texto: str) -> Decision:
        state = build_state(self.cfg.dominio, texto)
        result = self.client.systemone(
            self.cfg.ollama.modelo_decision,
            state,
            self.questions,
            timeout=self.cfg.ollama.timeout_decision,
        )
        decision = parse_answers(result.data.get("answers", {}), self.cfg.dominio)
        decision.latencia_ms = round(result.elapsed_ms, 1)
        decision.modelo = result.data.get("model", self.cfg.ollama.modelo_decision)
        decision.raw = result.data
        return apply_policy(decision, self.cfg, texto)

    def decide_safe(self, texto: str) -> Decision:
        try:
            return self.decide(texto)
        except OllamaError as exc:
            return fallback_decision(str(exc), self.cfg.dominio)
