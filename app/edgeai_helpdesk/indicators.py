"""Indicadores físicos: semáforo de tres LEDs.

El hardware se declara en el árbol de dispositivos (overlay ``gpio-led`` en
``config.txt``), de modo que el kernel expone:

* ``/sys/class/leds/edgeai-{verde,amarillo,rojo}/brightness``

Así la aplicación no necesita bibliotecas de GPIO: escribe ``0``/``1`` en
sysfs. Si los LEDs no están presentes (por ejemplo en una laptop), el módulo
funciona en modo simulado y el panel web muestra los LEDs virtuales.

Significado de los LEDs:

* Verde: encendido = sistema listo; parpadeo lento = cargando modelos.
* Amarillo: encendido = hay tiquetes en cola; parpadeo = el LLM está redactando.
* Rojo: encendido = hay tiquetes urgentes; parpadeo rápido = Ollama no responde.
"""

from __future__ import annotations

import logging
import os
import threading

from .config import IndicadoresConfig

log = logging.getLogger("edgeai.indicadores")

NOMBRES = ("verde", "amarillo", "rojo")


class LedBank:
    def __init__(self, cfg: IndicadoresConfig):
        self.cfg = cfg
        self.paths = {
            "verde": os.path.join(cfg.leds_dir, cfg.led_verde, "brightness"),
            "amarillo": os.path.join(cfg.leds_dir, cfg.led_amarillo, "brightness"),
            "rojo": os.path.join(cfg.leds_dir, cfg.led_rojo, "brightness"),
        }
        self.state = {n: False for n in NOMBRES}
        self.available = {
            n: cfg.habilitado and os.path.exists(p) and os.access(p, os.W_OK) for n, p in self.paths.items()
        }
        self._lock = threading.Lock()
        presentes = [n for n, ok in self.available.items() if ok]
        if presentes:
            log.info("LEDs físicos disponibles: %s", ", ".join(presentes))
        else:
            log.info("Sin LEDs físicos: modo simulado (ver panel web)")

    @property
    def mode(self) -> str:
        return "sysfs" if any(self.available.values()) else "simulado"

    def set(self, name: str, on: bool) -> None:
        with self._lock:
            if self.state.get(name) == on:
                return
            self.state[name] = on
            if self.available.get(name):
                try:
                    with open(self.paths[name], "w") as fh:
                        fh.write("1" if on else "0")
                except OSError as exc:
                    log.warning("No se pudo escribir %s: %s", self.paths[name], exc)
                    self.available[name] = False

    def snapshot(self) -> dict:
        with self._lock:
            return {"modo": self.mode, "estado": dict(self.state), "fisicos": dict(self.available)}

    def all_off(self) -> None:
        for n in NOMBRES:
            self.set(n, False)


class IndicatorController(threading.Thread):
    """Hilo que traduce el estado del sistema en patrones de LEDs."""

    TICK = 0.25

    def __init__(self, leds: LedBank):
        super().__init__(name="indicadores", daemon=True)
        self.leds = leds
        self._status = {"ollama_ok": False, "modelos_ok": False, "en_cola": 0, "urgentes": 0, "generando": 0}
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def update(self, **status) -> None:
        with self._lock:
            self._status.update(status)

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        tick = 0
        while not self._stop.is_set():
            with self._lock:
                st = dict(self._status)
            slow = (tick // 4) % 2 == 0  # 1 s de periodo
            fast = tick % 2 == 0  # 0.5 s de periodo
            if not st["ollama_ok"]:
                self.leds.set("verde", False)
                self.leds.set("amarillo", False)
                self.leds.set("rojo", fast)
            else:
                self.leds.set("verde", True if st["modelos_ok"] else slow)
                if st["generando"] > 0:
                    self.leds.set("amarillo", fast)
                else:
                    self.leds.set("amarillo", st["en_cola"] > 0)
                self.leds.set("rojo", st["urgentes"] > 0)
            tick += 1
            self._stop.wait(self.TICK)
        self.leds.all_off()
