"""Ruta rápida: clasificación con el modelo de decisión System One (JEV).

Una sola llamada a ``/v1/systemone`` responde seis preguntas tipadas sobre la
consulta. Luego una política determinista (umbrales configurables) convierte
esas probabilidades en un estado del tiquete. El LLM solo se usa después, y
solo si la política lo permite.
"""

from __future__ import annotations

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
    usar_llm: bool = True
    motivo: str = ""
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
                "true": "Mensaje respetuoso, aunque sea informal o esté molesto.",
                "false": "Insultos, acoso, amenazas, spam o contenido sexual.",
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


def apply_policy(decision: Decision, cfg: Config) -> Decision:
    """Política determinista: convierte probabilidades en un estado."""
    pol = cfg.politica
    if decision.apropiado < pol.umbral_apropiado:
        decision.estado = RECHAZADO
        decision.usar_llm = False
        decision.motivo = "Contenido no apropiado"
        return decision
    if decision.en_alcance < pol.umbral_alcance:
        decision.estado = FUERA_ALCANCE
        decision.usar_llm = False
        decision.motivo = "Fuera del alcance del servicio"
        return decision

    decision.usar_llm = True
    if decision.categoria == SIN_CLASIFICAR or decision.categoria_conf < pol.umbral_confianza:
        decision.revision_manual = True
        decision.motivo = "Clasificación con baja confianza: revisar manualmente"

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
        return apply_policy(decision, self.cfg)

    def decide_safe(self, texto: str) -> Decision:
        try:
            return self.decide(texto)
        except OllamaError as exc:
            return fallback_decision(str(exc), self.cfg.dominio)
