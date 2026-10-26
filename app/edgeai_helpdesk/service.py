"""Orquestación: decisión rápida, cola de redacción, salud e indicadores."""

from __future__ import annotations

import logging
import queue
import threading
import time

from . import __version__
from .config import Config
from .decision import AUTOSERVICIO, EN_COLA, SIN_CLASIFICAR, Decider, Decision
from .indicators import IndicatorController, LedBank
from .ollama_client import OllamaClient, OllamaError
from .responder import Responder
from .store import ERROR, GENERANDO, LISTA, OMITIDA, PENDIENTE, TicketStore

log = logging.getLogger("edgeai.servicio")

MIN_TEXTO, MAX_TEXTO = 5, 2000


class ValidationError(ValueError):
    pass


class HelpdeskService:
    def __init__(self, cfg: Config, client: OllamaClient | None = None, store: TicketStore | None = None,
                 leds: LedBank | None = None):
        self.cfg = cfg
        self.client = client or OllamaClient(cfg.ollama.url, cfg.ollama.keep_alive)
        self.store = store or TicketStore(cfg.datos.db)
        self.decider = Decider(cfg, self.client)
        self.responder = Responder(cfg, self.client)
        self.leds = leds or LedBank(cfg.indicadores)
        self.indicators = IndicatorController(self.leds)
        self._jobs: queue.Queue[int | None] = queue.Queue()
        self._stop = threading.Event()
        self._generating = 0
        self._health = {"ollama_ok": False, "ollama_version": None, "modelos": [], "faltantes": [],
                        "error": "sin verificar", "verificado": None}
        self._health_lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        self.started = time.time()

    # ---------------------------------------------------------- ciclo de vida
    def start(self) -> None:
        self.check_health()
        for ticket_id in self.store.pending_replies():
            self._jobs.put(ticket_id)
        worker = threading.Thread(target=self._worker, name="redactor", daemon=True)
        health = threading.Thread(target=self._health_loop, name="salud", daemon=True)
        self._threads = [worker, health]
        for t in self._threads:
            t.start()
        self.indicators.start()
        self._refresh_indicators()

    def stop(self) -> None:
        self._stop.set()
        self._jobs.put(None)
        self.indicators.stop()
        for t in self._threads:
            t.join(timeout=5)
        self.indicators.join(timeout=2)

    # ----------------------------------------------------------------- casos
    def submit(self, texto: str, nombre: str = "", contacto: str = "") -> dict:
        texto = (texto or "").strip()
        nombre = (nombre or "").strip()[:80]
        contacto = (contacto or "").strip()[:120]
        if len(texto) < MIN_TEXTO:
            raise ValidationError("Describa su consulta con al menos unas palabras.")
        if len(texto) > MAX_TEXTO:
            raise ValidationError(f"La consulta no debe superar {MAX_TEXTO} caracteres.")

        decision: Decision = self.decider.decide_safe(texto)
        plantillas = self.cfg.dominio["plantillas"]
        if decision.usar_llm:
            ticket_id = self.store.create(texto, decision, nombre, contacto)
            self._jobs.put(ticket_id)
        else:
            respuesta = plantillas.get(decision.estado, plantillas["fuera_alcance"])
            ticket_id = self.store.create(texto, decision, nombre, contacto, respuesta, OMITIDA)

        log.info("Tiquete #%d: %s / urgencia %.2f / %s (%.0f ms)", ticket_id, decision.categoria,
                 decision.urgencia_score, decision.estado, decision.latencia_ms)
        self._refresh_indicators()
        return self.store.get(ticket_id)

    def attend(self, ticket_id: int) -> bool:
        ok = self.store.mark_attended(ticket_id)
        self._refresh_indicators()
        return ok

    def reopen(self, ticket_id: int) -> bool:
        ok = self.store.reopen(ticket_id)
        self._refresh_indicators()
        return ok

    def attend_next(self) -> dict | None:
        """Atiende el tiquete más prioritario de la cola (botón del panel)."""
        cola = self.store.queue()
        if not cola:
            return None
        ticket = cola[0]
        self.attend(ticket["id"])
        log.info("Tiquete #%d marcado como atendido (siguiente en la cola)", ticket["id"])
        return self.store.get(ticket["id"])

    # ----------------------------------------------------------- redacción
    def _worker(self) -> None:
        while not self._stop.is_set():
            ticket_id = self._jobs.get()
            if ticket_id is None:
                break
            ticket = self.store.get(ticket_id)
            if not ticket or ticket["respuesta_estado"] not in (PENDIENTE, GENERANDO):
                continue
            self._generating += 1
            self.store.update(ticket_id, respuesta_estado=GENERANDO)
            self._refresh_indicators()
            try:
                decision = Decision(
                    categoria=ticket["categoria"], categoria_conf=ticket["categoria_conf"] or 0.0,
                    categoria_probs=ticket["categoria_probs"], urgencia_score=ticket["urgencia_score"] or 0.0,
                    urgencia_nivel=ticket["urgencia_nivel"] or 0, en_alcance=ticket["en_alcance"] or 0.0,
                    apropiado=ticket["apropiado"] or 0.0, datos_sensibles=ticket["datos_sensibles"] or 0.0,
                    autoservicio=ticket["autoservicio"] or 0.0, estado=ticket["estado"],
                    revision_manual=ticket["revision_manual"],
                )
                reply = self.responder.reply(ticket["texto"], decision)
                self.store.update(
                    ticket_id,
                    respuesta=reply.respuesta,
                    resumen=reply.resumen,
                    respuesta_estado=LISTA if reply.ok else ERROR,
                    lat_llm_ms=reply.latencia_ms or None,
                    modelo_llm=reply.modelo,
                    error=reply.error or None,
                )
                log.info("Tiquete #%d: respuesta %s en %.0f ms", ticket_id,
                         "lista" if reply.ok else "con error", reply.latencia_ms)
            except Exception as exc:  # noqa: BLE001 - un tiquete no debe tumbar el hilo
                log.exception("Fallo redactando el tiquete #%d", ticket_id)
                self.store.update(ticket_id, respuesta_estado=ERROR, error=str(exc),
                                  respuesta=self.cfg.dominio["plantillas"]["error_llm"])
            finally:
                self._generating -= 1
                self._refresh_indicators()

    # ----------------------------------------------------------------- salud
    def check_health(self) -> dict:
        o = self.cfg.ollama
        info = {"ollama_ok": False, "ollama_version": None, "modelos": [], "faltantes": [],
                "error": None, "verificado": time.time()}
        try:
            info["ollama_version"] = self.client.version()
            info["modelos"] = self.client.models()
            info["ollama_ok"] = True
            info["faltantes"] = [m for m in (o.modelo_decision, o.modelo_llm)
                                 if not OllamaClient.has_model(info["modelos"], m)]
        except OllamaError as exc:
            info["error"] = str(exc)
        with self._health_lock:
            self._health = info
        self._refresh_indicators()
        return info

    def _health_loop(self) -> None:
        while not self._stop.wait(10):
            self.check_health()

    def _refresh_indicators(self) -> None:
        stats = self.store.stats(self.cfg.politica.nivel_urgente)
        with self._health_lock:
            h = dict(self._health)
        self.indicators.update(
            ollama_ok=h["ollama_ok"],
            modelos_ok=h["ollama_ok"] and not h["faltantes"],
            en_cola=stats["en_cola"],
            urgentes=stats["urgentes"],
            generando=self._generating,
        )

    def health(self) -> dict:
        with self._health_lock:
            h = dict(self._health)
        o = self.cfg.ollama
        listo = h["ollama_ok"] and not h["faltantes"]
        return {
            "version": __version__,
            "listo": listo,
            "uptime_s": int(time.time() - self.started),
            "ollama": {
                "url": o.url,
                "ok": h["ollama_ok"],
                "version": h["ollama_version"],
                "error": h["error"],
                "modelo_decision": o.modelo_decision,
                "modelo_llm": o.modelo_llm,
                "modelos_instalados": h["modelos"],
                "modelos_faltantes": h["faltantes"],
            },
            "indicadores": self.leds.snapshot(),
            "estadisticas": self.store.stats(self.cfg.politica.nivel_urgente),
            "en_redaccion": self._generating,
            "configuracion": self.cfg.origen,
        }

    def domain_summary(self) -> dict:
        d = self.cfg.dominio
        return {
            "servicio": d["servicio"],
            "categorias": {**{k: v.get("etiqueta", k) for k, v in d["categorias"].items()},
                           SIN_CLASIFICAR: "Sin clasificar"},
            "descripciones": {k: v["descripcion"] for k, v in d["categorias"].items()},
            "urgencia": [n.split(":")[0].strip() for n in d["urgencia"]],
            "estados": {
                "en_cola": "En cola de atención",
                AUTOSERVICIO: "Resuelto con instrucciones",
                "rechazado": "Rechazado",
                "fuera_alcance": "Fuera de alcance",
                "atendido": "Atendido",
            },
        }
