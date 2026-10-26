"""edgeai-admin: administración de la mesa de ayuda desde la terminal.

Ejemplos (en la Raspberry Pi, por SSH o en tty2):

    edgeai-admin estado
    edgeai-admin cola
    edgeai-admin atender 12
    edgeai-admin modelos asegurar --descargar
    edgeai-admin modelos precargar
    edgeai-admin leds probar
    edgeai-admin exportar --salida /tmp/tickets.csv
    edgeai-admin purgar --dias 30
    edgeai-admin autoprueba
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

from .config import Config, load_config
from .indicators import NOMBRES, LedBank
from .ollama_client import OllamaClient, OllamaError
from .store import TicketStore

SERVICIOS = ("ollama", "edgeai-helpdesk", "edgeai-kiosk", "edgeai-provision")


def api(cfg: Config, method: str, path: str, payload: dict | None = None) -> dict | list:
    host = "127.0.0.1" if cfg.web.host in ("0.0.0.0", "") else cfg.web.host
    url = f"http://{host}:{cfg.web.puerto}{path}"
    headers = {"Content-Type": "application/json"}
    if cfg.web.panel_token:
        headers["X-Panel-Token"] = cfg.web.panel_token
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Error {exc.code}: {exc.read().decode(errors='replace')}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise SystemExit(f"La API no responde en {url} ({exc}). ¿Está activo edgeai-helpdesk?") from exc


def _fmt_ms(v) -> str:
    return f"{v / 1000:.1f} s" if v else "-"


def cmd_estado(cfg: Config, _args) -> int:
    if shutil.which("systemctl"):
        print("Servicios:")
        for s in SERVICIOS:
            st = subprocess.run(["systemctl", "is-active", s], capture_output=True, text=True).stdout.strip() or "?"
            print(f"  {s:<18} {st}")
    h = api(cfg, "GET", "/api/health")
    o = h["ollama"]
    print(f"\nMesa de ayuda {h['version']}  listo={h['listo']}  uptime={h['uptime_s']} s")
    print(f"Ollama {o['version'] or '-'} ({'OK' if o['ok'] else 'SIN RESPUESTA'})  {o['url']}")
    print(f"  decisión: {o['modelo_decision']}   LLM: {o['modelo_llm']}")
    if o["modelos_faltantes"]:
        print(f"  FALTAN MODELOS: {', '.join(o['modelos_faltantes'])}  -> edgeai-admin modelos asegurar --descargar")
    ind = h["indicadores"]
    leds = " ".join(f"{k}={'ON' if v else 'off'}" for k, v in ind["estado"].items())
    print(f"LEDs ({ind['modo']}): {leds}")
    e = h["estadisticas"]
    print(f"Tiquetes: total={e['total']} en_cola={e['en_cola']} urgentes={e['urgentes']} "
          f"respuestas_pendientes={e['respuestas_pendientes']}")
    print(f"Latencia decisión: prom {_fmt_ms(e['decision_ms_promedio'])}, máx {_fmt_ms(e['decision_ms_max'])}")
    print(f"Latencia LLM:      prom {_fmt_ms(e['llm_ms_promedio'])}, máx {_fmt_ms(e['llm_ms_max'])}")
    return 0


def _print_tickets(rows: list[dict]) -> None:
    if not rows:
        print("(sin tiquetes)")
        return
    print(f"{'#':>4}  {'estado':<13} {'categoría':<16} {'urg':>4}  {'resumen / texto'}")
    for t in rows:
        txt = (t.get("resumen") or t.get("texto") or "").replace("\n", " ")
        print(f"{t['id']:>4}  {t['estado']:<13} {t['categoria']:<16} {t['urgencia_score'] or 0:>4.1f}  {txt[:60]}")


def cmd_cola(cfg, _args) -> int:
    _print_tickets(api(cfg, "GET", "/api/cola"))
    return 0


def cmd_tiquetes(cfg, args) -> int:
    q = f"?limit={args.limite}" + (f"&estado={args.estado}" if args.estado else "")
    _print_tickets(api(cfg, "GET", "/api/tickets" + q))
    return 0


def cmd_tiquete(cfg, args) -> int:
    print(json.dumps(api(cfg, "GET", f"/api/tickets/{args.id}"), ensure_ascii=False, indent=2))
    return 0


def cmd_atender(cfg, args) -> int:
    t = api(cfg, "POST", f"/api/tickets/{args.id}/atender")
    print(f"Tiquete #{t['id']} -> {t['estado']}")
    return 0


def cmd_reabrir(cfg, args) -> int:
    t = api(cfg, "POST", f"/api/tickets/{args.id}/reabrir")
    print(f"Tiquete #{t['id']} -> {t['estado']}")
    return 0


def cmd_siguiente(cfg, _args) -> int:
    t = api(cfg, "POST", "/api/atender-siguiente")
    print(t.get("mensaje") or f"Tiquete #{t['id']} atendido: {t.get('resumen') or t['texto'][:60]}")
    return 0


def cmd_exportar(cfg, args) -> int:
    n = TicketStore(cfg.datos.db).export_csv(args.salida)
    print(f"{n} tiquetes exportados a {args.salida}")
    return 0


def cmd_purgar(cfg, args) -> int:
    n = TicketStore(cfg.datos.db).purge(args.dias)
    print(f"{n} tiquetes con más de {args.dias} días eliminados")
    return 0


def _wait_ollama(client: OllamaClient, seconds: int) -> bool:
    deadline = time.time() + seconds
    while True:
        try:
            client.version()
            return True
        except OllamaError:
            if time.time() >= deadline:
                return False
            time.sleep(2)


def cmd_modelos(cfg, args) -> int:
    o = cfg.ollama
    client = OllamaClient(o.url, o.keep_alive)
    if not _wait_ollama(client, args.esperar):
        print(f"Ollama no responde en {o.url}", file=sys.stderr)
        return 2
    instalados = client.models()
    requeridos = [o.modelo_decision, o.modelo_llm]
    if args.accion == "listar":
        print("Instalados:", ", ".join(instalados) or "(ninguno)")
        for m in requeridos:
            print(f"  {m:<20} {'OK' if OllamaClient.has_model(instalados, m) else 'FALTA'}")
        return 0
    if args.accion == "asegurar":
        faltan = [m for m in requeridos if not OllamaClient.has_model(instalados, m)]
        if not faltan:
            print("Modelos completos:", ", ".join(requeridos))
            return 0
        if not args.descargar:
            print("Faltan modelos:", ", ".join(faltan), "(use --descargar con conexión a internet)")
            return 1
        for m in faltan:
            print(f"Descargando {m}...")
            last = {"t": 0.0}

            def progress(ev, last=last):
                if time.time() - last["t"] > 5 and ev.get("total"):
                    pct = 100 * ev.get("completed", 0) / ev["total"]
                    print(f"  {ev.get('status', '')} {pct:5.1f}%")
                    last["t"] = time.time()

            try:
                client.pull(m, progress=progress)
            except OllamaError as exc:
                print(f"No se pudo descargar {m}: {exc}", file=sys.stderr)
                return 1
        print("Modelos listos.")
        return 0
    if args.accion == "precargar":
        from .decision import build_questions
        print(f"Cargando {o.modelo_decision} ...")
        r = client.systemone(o.modelo_decision, "prueba de arranque",
                             {"ok": {"type": "noul", "instructions": "¿Es una prueba?"}}, timeout=o.timeout_decision)
        print(f"  listo en {r.elapsed_ms / 1000:.1f} s")
        build_questions(cfg.dominio)  # valida el dominio
        print(f"Cargando {o.modelo_llm} ...")
        print(f"  listo en {client.warmup_llm(o.modelo_llm) / 1000:.1f} s")
        return 0
    return 1


def cmd_leds(cfg, _args) -> int:
    leds = LedBank(cfg.indicadores)
    print(f"Modo: {leds.mode}")
    for nombre, ok in leds.available.items():
        print(f"  {nombre:<9} {'presente' if ok else 'NO presente'}  {leds.paths[nombre]}")
    if leds.mode == "simulado":
        print("No hay LEDs físicos: revise el cableado y 'dtoverlay=gpio-led' en /boot/config.txt")
        return 1
    print("Encendiendo cada LED 1 s (detenga antes edgeai-helpdesk para que no interfiera)...")
    for nombre in NOMBRES:
        leds.set(nombre, True)
        time.sleep(1)
        leds.set(nombre, False)
    return 0


def cmd_autoprueba(cfg: Config, _args) -> int:
    fallos = 0

    def check(nombre: str, ok: bool, detalle: str = "") -> None:
        nonlocal fallos
        fallos += 0 if ok else 1
        print(f"[{'OK ' if ok else 'ERR'}] {nombre}{' - ' + detalle if detalle else ''}")

    check("configuración", True, cfg.origen)
    check("dominio (categorias.json)", True, f"{len(cfg.dominio['categorias'])} categorías")
    try:
        store = TicketStore(cfg.datos.db)
        store.stats(cfg.politica.nivel_urgente)
        check("base de datos", True, cfg.datos.db)
    except Exception as exc:  # noqa: BLE001
        check("base de datos", False, str(exc))
    client = OllamaClient(cfg.ollama.url)
    try:
        version = client.version()
        instalados = client.models()
        check("ollama", True, f"v{version} en {cfg.ollama.url}")
        for m in (cfg.ollama.modelo_decision, cfg.ollama.modelo_llm):
            check(f"modelo {m}", OllamaClient.has_model(instalados, m))
    except OllamaError as exc:
        check("ollama", False, str(exc))
    leds = LedBank(cfg.indicadores)
    check("LEDs físicos", leds.mode == "sysfs", leds.mode)
    print(f"\n{'Sin fallos' if not fallos else f'{fallos} verificación(es) fallaron'}")
    return 0 if not fallos else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="edgeai-admin", description="Administración de la mesa de ayuda EdgeAI")
    parser.add_argument("--config", default=os.environ.get("EDGEAI_CONFIG"))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("estado", help="servicios, modelos, LEDs y métricas").set_defaults(fn=cmd_estado)
    sub.add_parser("cola", help="cola de atención por urgencia").set_defaults(fn=cmd_cola)
    p = sub.add_parser("tiquetes", help="listar tiquetes")
    p.add_argument("--estado")
    p.add_argument("--limite", type=int, default=30)
    p.set_defaults(fn=cmd_tiquetes)
    for name, fn in (("tiquete", cmd_tiquete), ("atender", cmd_atender), ("reabrir", cmd_reabrir)):
        p = sub.add_parser(name)
        p.add_argument("id", type=int)
        p.set_defaults(fn=fn)
    sub.add_parser("siguiente", help="atender el tiquete más prioritario").set_defaults(fn=cmd_siguiente)
    p = sub.add_parser("exportar", help="exportar tiquetes a CSV")
    p.add_argument("--salida", default="tiquetes.csv")
    p.set_defaults(fn=cmd_exportar)
    p = sub.add_parser("purgar", help="borrar tiquetes antiguos")
    p.add_argument("--dias", type=int, required=True)
    p.set_defaults(fn=cmd_purgar)
    p = sub.add_parser("modelos", help="listar, asegurar o precargar modelos")
    p.add_argument("accion", choices=("listar", "asegurar", "precargar"))
    p.add_argument("--descargar", action="store_true", help="descargar los modelos faltantes")
    p.add_argument("--esperar", type=int, default=60, help="segundos a esperar a Ollama")
    p.set_defaults(fn=cmd_modelos)
    p = sub.add_parser("leds", help="probar los LEDs del semáforo")
    p.add_argument("accion", choices=("probar",))
    p.set_defaults(fn=cmd_leds)
    sub.add_parser("autoprueba", help="verificar configuración, BD, Ollama, modelos y LEDs").set_defaults(
        fn=cmd_autoprueba)
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    return args.fn(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
