"""Carga de configuración.

La configuración vive en dos archivos:

* ``helpdesk.conf`` (INI): parámetros operativos (Ollama, umbrales, web, datos,
  indicadores).
* ``categorias.json``: dominio de la aplicación (servicio, categorías, base de
  conocimiento, textos de las preguntas al modelo de decisión y plantillas).

Separar el dominio del código permite adaptar la mesa de ayuda a otra oficina
editando solo el JSON, sin reconstruir la imagen.
"""

from __future__ import annotations

import configparser
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
APP_DIR = PACKAGE_DIR.parent
DEFAULT_CONFIG_PATHS = (
    Path("/etc/edgeai/helpdesk.conf"),          # imagen Yocto
    APP_DIR / "config" / "helpdesk.dev.conf",   # desarrollo en una PC
)


@dataclass
class OllamaConfig:
    url: str = "http://127.0.0.1:11434"
    modelo_decision: str = "tev1:0.8b"
    modelo_llm: str = "qwen2.5:1.5b"
    timeout_decision: float = 120.0
    timeout_llm: float = 240.0
    keep_alive: str = "24h"
    llm_num_ctx: int = 2048
    llm_num_predict: int = 220
    llm_temperatura: float = 0.3
    llm_think: str = ""  # vacío = no se envía el campo "think"


@dataclass
class PoliticaConfig:
    umbral_apropiado: float = 0.5
    umbral_alcance: float = 0.4
    umbral_confianza: float = 0.25
    umbral_autoservicio: float = 0.6
    umbral_sensible: float = 0.5
    nivel_urgente: int = 2


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    puerto: int = 8080
    panel_token: str = ""


@dataclass
class DatosConfig:
    db: str = str(APP_DIR.parent / "var" / "tickets.db")
    categorias: str = str(APP_DIR / "config" / "categorias.json")
    casos: str = str(APP_DIR / "config" / "casos_demo.json")


@dataclass
class IndicadoresConfig:
    habilitado: bool = True
    leds_dir: str = "/sys/class/leds"
    led_verde: str = "edgeai-verde"
    led_amarillo: str = "edgeai-amarillo"
    led_rojo: str = "edgeai-rojo"


@dataclass
class Config:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    politica: PoliticaConfig = field(default_factory=PoliticaConfig)
    web: WebConfig = field(default_factory=WebConfig)
    datos: DatosConfig = field(default_factory=DatosConfig)
    indicadores: IndicadoresConfig = field(default_factory=IndicadoresConfig)
    dominio: dict = field(default_factory=dict)
    origen: str = "(valores por defecto)"


def _coerce(value: str, target_type):
    if target_type is bool:
        return value.strip().lower() in ("1", "true", "yes", "si", "sí", "on")
    if target_type is int:
        return int(value)
    if target_type is float:
        return float(value)
    return value.strip()


def _apply_section(parser: configparser.ConfigParser, section: str, obj) -> None:
    if not parser.has_section(section):
        return
    for name, current in vars(obj).items():
        if parser.has_option(section, name):
            raw = parser.get(section, name)
            setattr(obj, name, _coerce(raw, type(current)))


def load_domain(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        dominio = json.load(fh)
    validate_domain(dominio)
    return dominio


def validate_domain(dominio: dict) -> None:
    """Valida lo mínimo para que el modelo de decisión reciba preguntas válidas."""
    faltan = [k for k in ("servicio", "categorias", "urgencia", "preguntas", "plantillas") if k not in dominio]
    if faltan:
        raise ValueError(f"categorias.json incompleto, faltan: {', '.join(faltan)}")
    cats = dominio["categorias"]
    if not 2 <= len(cats) <= 24:
        # Tev1 acepta como máximo 24 opciones por pregunta de tipo choice.
        raise ValueError("Se requieren entre 2 y 24 categorías")
    for key, cat in cats.items():
        if not key or not cat.get("descripcion"):
            raise ValueError(f"La categoría '{key}' necesita una descripción")
    niveles = dominio["urgencia"]
    if not 2 <= len(niveles) <= 10:
        raise ValueError("La escala de urgencia debe tener entre 2 y 10 niveles")


def load_config(path: str | None = None) -> Config:
    """Carga la configuración. Orden: argumento, $EDGEAI_CONFIG, /etc, repo."""
    cfg = Config()
    candidatos = []
    if path:
        candidatos.append(Path(path))
    elif os.environ.get("EDGEAI_CONFIG"):
        candidatos.append(Path(os.environ["EDGEAI_CONFIG"]))
    else:
        candidatos.extend(DEFAULT_CONFIG_PATHS)

    for candidato in candidatos:
        if candidato.is_file():
            parser = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
            parser.read(candidato, encoding="utf-8")
            for section in ("ollama", "politica", "web", "datos", "indicadores"):
                _apply_section(parser, section, getattr(cfg, section))
            # Las rutas relativas se resuelven respecto del archivo de configuración.
            base = candidato.resolve().parent
            for name in ("db", "categorias", "casos"):
                value = getattr(cfg.datos, name)
                if value and not os.path.isabs(value):
                    setattr(cfg.datos, name, str((base / value).resolve()))
            cfg.origen = str(candidato)
            break
    else:
        if path:
            raise FileNotFoundError(f"No existe el archivo de configuración: {path}")

    # Variables de entorno útiles en desarrollo y pruebas.
    cfg.ollama.url = os.environ.get("EDGEAI_OLLAMA_URL", cfg.ollama.url)
    cfg.datos.db = os.environ.get("EDGEAI_DB", cfg.datos.db)
    if os.environ.get("EDGEAI_PORT"):
        cfg.web.puerto = int(os.environ["EDGEAI_PORT"])
    if os.environ.get("EDGEAI_LEDS_DIR"):
        cfg.indicadores.leds_dir = os.environ["EDGEAI_LEDS_DIR"]

    cfg.dominio = load_domain(cfg.datos.categorias)
    return cfg
