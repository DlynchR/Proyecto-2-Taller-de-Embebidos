"""Kiosco de texto para la pantalla HDMI y el teclado de la Raspberry Pi.

Corre en tty1 como servicio de systemd y habla con la API local, igual que el
formulario web. No necesita entorno gráfico.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import subprocess
import sys
import time
import urllib.error
import urllib.request

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
RED, GREEN, YELLOW, CYAN = "\033[31m", "\033[32m", "\033[33m", "\033[36m"
CLEAR = "\033[2J\033[H"
NO_BLANK = "\033[9;0]"  # desactiva el apagado de pantalla de la consola Linux
URGENCIA_COLOR = [GREEN, YELLOW, RED, RED]


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, payload: dict | None = None, timeout: float = 180) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                msg = json.loads(exc.read().decode()).get("error", str(exc))
            except ValueError:
                msg = str(exc)
            raise RuntimeError(msg) from exc


def local_addresses() -> list[str]:
    try:
        out = subprocess.run(["ip", "-4", "-o", "addr", "show"], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    addrs = []
    for line in out.splitlines():
        parts = line.split()
        if "inet" in parts:
            ip = parts[parts.index("inet") + 1].split("/")[0]
            if not ip.startswith("127."):
                addrs.append(ip)
    return addrs


def read_line(prompt: str, timeout: float | None = None) -> str | None:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    if timeout is not None and sys.stdin.isatty():
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            return None
    line = sys.stdin.readline()
    if line == "":
        raise EOFError
    return line.rstrip("\n")


def wrap(text: str, width: int = 72) -> str:
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return "\n".join("  " + x for x in out)


def banner(dominio: dict, port: int) -> None:
    sys.stdout.write(CLEAR + NO_BLANK)
    nombre = dominio.get("servicio", {}).get("nombre", "Mesa de ayuda")
    print(f"{BOLD}{CYAN}  ┌{'─' * 66}┐{RESET}")
    print(f"{BOLD}{CYAN}  │ {nombre[:64]:<64} │{RESET}")
    print(f"{BOLD}{CYAN}  └{'─' * 66}┘{RESET}")
    print(f"{DIM}  Asistente local: su consulta se procesa en este equipo, sin internet.{RESET}")
    addrs = local_addresses()
    if addrs:
        sufijo = "" if port == 80 else f":{port}"
        urls = "  ".join(f"http://{a}{sufijo}" for a in addrs)
        print(f"{DIM}  También desde su celular: {urls}{RESET}")
    print()


def wait_for_api(api: Api) -> dict:
    shown = False
    while True:
        try:
            return api.call("GET", "/api/dominio", timeout=5)
        except (OSError, RuntimeError):
            if not shown:
                print("  Iniciando el sistema, un momento...")
                shown = True
            time.sleep(3)


def ask_ticket(api: Api, dominio: dict, port: int) -> None:
    banner(dominio, port)
    print(f"  {BOLD}Describa su consulta{RESET} y presione Enter dos veces para enviarla.")
    print(f"{DIM}  (Escriba 'salir' para limpiar la pantalla){RESET}\n")
    lines: list[str] = []
    while True:
        line = read_line("  > ")
        if line is None:
            continue
        if line.strip().lower() == "salir":
            return
        if not line.strip():
            if lines:
                break
            continue
        lines.append(line.strip())
    texto = " ".join(lines)
    nombre = read_line(f"\n  Su nombre {DIM}(opcional, Enter para omitir){RESET}: ", timeout=60) or ""

    print(f"\n  {DIM}Analizando su consulta...{RESET}")
    try:
        t = api.call("POST", "/api/tickets", {"texto": texto, "nombre": nombre})
    except (RuntimeError, OSError) as exc:
        print(f"\n  {RED}No se pudo registrar: {exc}{RESET}")
        read_line("\n  Presione Enter para continuar...", timeout=20)
        return

    categorias = dominio.get("categorias", {})
    niveles = dominio.get("urgencia", [])
    estados = dominio.get("estados", {})
    nivel = int(t.get("urgencia_nivel") or 0)
    color = URGENCIA_COLOR[min(nivel, len(URGENCIA_COLOR) - 1)]
    print(f"\n  {BOLD}Tiquete #{t['id']}{RESET}  ({t.get('lat_decision_ms') or 0:.0f} ms)")
    print(f"  Categoría: {BOLD}{categorias.get(t['categoria'], t['categoria'])}{RESET}")
    if niveles:
        print(f"  Urgencia:  {color}{BOLD}{niveles[min(nivel, len(niveles) - 1)]}{RESET}")
    print(f"  Estado:    {estados.get(t['estado'], t['estado'])}")

    respuesta = t.get("respuesta") or ""
    if t.get("respuesta_estado") in ("pendiente", "generando"):
        sys.stdout.write(f"\n  {DIM}Redactando respuesta")
        sys.stdout.flush()
        deadline = time.time() + 300
        while time.time() < deadline:
            time.sleep(1.5)
            sys.stdout.write(".")
            sys.stdout.flush()
            try:
                c = api.call("GET", f"/api/consulta/{t['id']}?clave={t['clave']}", timeout=10)
            except (RuntimeError, OSError):
                continue
            if c.get("respuesta_estado") not in ("pendiente", "generando"):
                respuesta = c.get("respuesta") or ""
                break
        sys.stdout.write(RESET + "\n")
    if respuesta:
        print(f"\n{wrap(respuesta)}")
    read_line(f"\n  {DIM}Presione Enter para una nueva consulta.{RESET}", timeout=90)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kiosco de texto de la mesa de ayuda EdgeAI")
    parser.add_argument("--api", default=os.environ.get("EDGEAI_API", "http://127.0.0.1:80"))
    args = parser.parse_args(argv)
    port = int(args.api.rsplit(":", 1)[-1]) if args.api.count(":") > 1 else 80
    api = Api(args.api)
    dominio = wait_for_api(api)
    while True:
        try:
            ask_ticket(api, dominio, port)
        except KeyboardInterrupt:
            continue
        except EOFError:
            return 0


if __name__ == "__main__":
    sys.exit(main())
