"""Servidor HTTP (API JSON + interfaz web) con la biblioteca estándar.

Rutas:

Kiosco (público)
  GET  /                         formulario de consulta
  GET  /api/dominio              servicio, categorías y niveles de urgencia
  POST /api/tickets              crear tiquete (decisión JEV inmediata)
  GET  /api/consulta/<id>?clave= estado y respuesta de un tiquete propio

Panel de atención (requiere X-Panel-Token si panel_token está configurado)
  GET  /panel                    tablero de la cola
  GET  /api/health               salud del sistema, LEDs y métricas
  GET  /api/cola                 cola ordenada por urgencia
  GET  /api/tickets[?estado=&limit=]
  GET  /api/tickets/<id>
  POST /api/tickets/<id>/atender
  POST /api/tickets/<id>/reabrir
  POST /api/atender-siguiente
"""

from __future__ import annotations

import argparse
import hmac
import json
import logging
import re
import signal
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__
from .config import load_config
from .service import HelpdeskService, ValidationError
from .store import CONSULTA_FIELDS

log = logging.getLogger("edgeai.web")
WEB_DIR = Path(__file__).resolve().parent / "web"
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}
MAX_BODY = 16 * 1024
TICKET_ROUTE = re.compile(r"^/api/tickets/(\d+)(?:/(atender|reabrir))?$")
CONSULTA_ROUTE = re.compile(r"^/api/consulta/(\d+)$")


def make_handler(service: HelpdeskService):
    token = service.cfg.web.panel_token

    class Handler(BaseHTTPRequestHandler):
        server_version = f"EdgeAI-Helpdesk/{__version__}"

        # ---------------------------------------------------------- utilidades
        def log_message(self, fmt, *args):  # noqa: N802 - firma heredada
            log.debug("%s - %s", self.address_string(), fmt % args)

        def _headers(self, status: int, ctype: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()

        def _json(self, data, status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(body))
            self.wfile.write(body)

        def _error(self, status: int, message: str) -> None:
            self._json({"error": message}, status)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ValidationError("Solicitud demasiado grande")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValidationError("JSON inválido") from exc
            if not isinstance(data, dict):
                raise ValidationError("Se esperaba un objeto JSON")
            return data

        def _panel_ok(self) -> bool:
            if not token:
                return True
            sent = self.headers.get("X-Panel-Token", "")
            return hmac.compare_digest(sent.encode(), token.encode())

        def _static(self, name: str) -> None:
            path = (WEB_DIR / name).resolve()
            if WEB_DIR not in path.parents or path.suffix not in STATIC_TYPES or not path.is_file():
                self._error(404, "No encontrado")
                return
            body = path.read_bytes()
            self._headers(200, STATIC_TYPES[path.suffix], len(body))
            self.wfile.write(body)

        # --------------------------------------------------------------- GET
        def do_GET(self):  # noqa: N802
            url = urlparse(self.path)
            path = url.path.rstrip("/") or "/"
            query = parse_qs(url.query)
            if path == "/":
                return self._static("index.html")
            if path == "/panel":
                return self._static("panel.html")
            if path.startswith("/static/"):
                return self._static(path[len("/static/"):])
            if path == "/api/dominio":
                return self._json(service.domain_summary())
            m = CONSULTA_ROUTE.match(path)
            if m:
                ticket = service.store.get(int(m.group(1)))
                clave = (query.get("clave") or [""])[0]
                if not ticket or not hmac.compare_digest((ticket.get("clave") or "").encode(), clave.encode()):
                    return self._error(404, "Tiquete no encontrado")
                return self._json({k: ticket[k] for k in CONSULTA_FIELDS})

            if not path.startswith("/api/"):
                return self._error(404, "No encontrado")
            if not self._panel_ok():
                return self._error(401, "Token del panel requerido")
            if path == "/api/health":
                return self._json(service.health())
            if path == "/api/cola":
                return self._json(service.store.queue())
            if path == "/api/tickets":
                estado = (query.get("estado") or [None])[0]
                try:
                    limit = max(1, min(500, int((query.get("limit") or ["100"])[0])))
                except ValueError:
                    return self._error(400, "limit inválido")
                return self._json(service.store.list(estado, limit))
            m = TICKET_ROUTE.match(path)
            if m and not m.group(2):
                ticket = service.store.get(int(m.group(1)))
                return self._json(ticket) if ticket else self._error(404, "Tiquete no encontrado")
            return self._error(404, "No encontrado")

        # -------------------------------------------------------------- POST
        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path.rstrip("/")
            try:
                if path == "/api/tickets":
                    data = self._body()
                    ticket = service.submit(
                        str(data.get("texto", "")), str(data.get("nombre", "")), str(data.get("contacto", ""))
                    )
                    return self._json(ticket, 201)
                if not self._panel_ok():
                    return self._error(401, "Token del panel requerido")
                if path == "/api/atender-siguiente":
                    ticket = service.attend_next()
                    return self._json(ticket or {"mensaje": "La cola está vacía"})
                m = TICKET_ROUTE.match(path)
                if m and m.group(2):
                    ticket_id = int(m.group(1))
                    ok = service.attend(ticket_id) if m.group(2) == "atender" else service.reopen(ticket_id)
                    if not ok:
                        return self._error(409, "El tiquete no admite ese cambio de estado")
                    return self._json(service.store.get(ticket_id))
                return self._error(404, "No encontrado")
            except ValidationError as exc:
                return self._error(400, str(exc))
            except Exception:  # noqa: BLE001
                log.exception("Error atendiendo %s", path)
                return self._error(500, "Error interno")

    return Handler


def build_server(service: HelpdeskService, host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(service))
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mesa de ayuda EdgeAI (API + web)")
    parser.add_argument("--config", help="ruta a helpdesk.conf")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    cfg = load_config(args.config)
    host = args.host or cfg.web.host
    port = args.port or cfg.web.puerto

    service = HelpdeskService(cfg)
    service.start()
    server = build_server(service, host, port)
    log.info("Mesa de ayuda EdgeAI %s en http://%s:%d (config: %s)", __version__, host, port, cfg.origen)
    log.info("Decisión: %s | LLM: %s | Ollama: %s", cfg.ollama.modelo_decision, cfg.ollama.modelo_llm, cfg.ollama.url)

    def _shutdown(*_):
        log.info("Deteniendo...")
        server.shutdown()

    # shutdown() bloquea hasta que serve_forever termina: se llama desde otro hilo.
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=_shutdown, daemon=True).start())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
