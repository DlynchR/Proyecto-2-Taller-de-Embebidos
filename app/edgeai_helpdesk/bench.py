"""edgeai-bench: verificación de los casos de uso y medición de latencias.

Ejecuta cada caso de ``casos_demo.json`` contra los modelos reales (o el
simulador), compara el resultado con lo esperado y reporta tiempos. No escribe
en la base de datos de tiquetes.

    edgeai-bench                 # solo la ruta rápida (modelo de decisión)
    edgeai-bench --llm           # también redacta la respuesta con el LLM
    edgeai-bench --csv out.csv   # guarda el detalle
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys

from .config import load_config
from .decision import Decider
from .ollama_client import OllamaClient, OllamaError
from .responder import Responder


def evaluate(caso: dict, d) -> dict:
    esperado = caso.get("esperado", {})
    checks = {}
    if "estado" in esperado:
        checks["estado"] = d.estado in esperado["estado"]
    if "categoria" in esperado and d.estado not in ("rechazado", "fuera_alcance"):
        checks["categoria"] = d.categoria == esperado["categoria"]
    if "urgencia" in esperado and d.estado not in ("rechazado", "fuera_alcance"):
        tol = esperado.get("tolerancia", 1)
        checks["urgencia"] = abs(d.urgencia_nivel - esperado["urgencia"]) <= tol
    if "datos_sensibles" in esperado:
        checks["datos_sensibles"] = (d.datos_sensibles >= 0.5) == esperado["datos_sensibles"]
    return checks


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = max(0, min(len(values) - 1, round(q * (len(values) - 1))))
    return values[k]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="edgeai-bench", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config")
    parser.add_argument("--casos", help="archivo de casos (por defecto el de la configuración)")
    parser.add_argument("--llm", action="store_true", help="medir también la redacción con el LLM")
    parser.add_argument("--repeticiones", type=int, default=1)
    parser.add_argument("--csv", help="guardar resultados detallados en CSV")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    with open(args.casos or cfg.datos.casos, encoding="utf-8") as fh:
        casos = json.load(fh)["casos"]
    client = OllamaClient(cfg.ollama.url, cfg.ollama.keep_alive)
    decider, responder = Decider(cfg, client), Responder(cfg, client)
    try:
        print(f"Ollama {client.version()} | decisión: {cfg.ollama.modelo_decision} | LLM: {cfg.ollama.modelo_llm}")
    except OllamaError as exc:
        print(f"Ollama no responde: {exc}", file=sys.stderr)
        return 2

    filas, lat_dec, lat_llm = [], [], []
    aciertos = total_checks = casos_ok = 0
    print(f"\n{'caso':<6} {'estado':<13} {'categoría':<16} {'urg':>3} {'decisión':>9} {'LLM':>8}  verificación")
    for rep in range(args.repeticiones):
        for caso in casos:
            try:
                d = decider.decide(caso["texto"])
            except OllamaError as exc:
                print(f"{caso['id']:<6} ERROR {exc}")
                continue
            lat_dec.append(d.latencia_ms)
            llm_ms = 0.0
            respuesta = ""
            if args.llm and d.usar_llm:
                r = responder.reply(caso["texto"], d)
                llm_ms = r.latencia_ms
                respuesta = r.respuesta
                if r.ok:
                    lat_llm.append(llm_ms)
            checks = evaluate(caso, d)
            ok = all(checks.values())
            aciertos += sum(checks.values())
            total_checks += len(checks)
            casos_ok += ok
            marcas = " ".join(f"{k}:{'✓' if v else '✗'}" for k, v in checks.items())
            print(f"{caso['id']:<6} {d.estado:<13} {d.categoria:<16} {d.urgencia_nivel:>3} "
                  f"{d.latencia_ms / 1000:>8.2f}s {llm_ms / 1000 if llm_ms else 0:>7.2f}s  {marcas}")
            filas.append({
                "repeticion": rep + 1, "caso": caso["id"], "nombre": caso.get("nombre", ""),
                "estado": d.estado, "categoria": d.categoria, "categoria_conf": round(d.categoria_conf, 3),
                "urgencia_score": d.urgencia_score, "urgencia_nivel": d.urgencia_nivel,
                "en_alcance": round(d.en_alcance, 3), "apropiado": round(d.apropiado, 3),
                "datos_sensibles": round(d.datos_sensibles, 3), "autoservicio": round(d.autoservicio, 3),
                "lat_decision_ms": d.latencia_ms, "lat_llm_ms": llm_ms, "verificacion_ok": ok,
                "detalle": marcas, "respuesta": respuesta,
            })

    n = len(filas)
    print(f"\nCasos correctos: {casos_ok}/{n}   verificaciones: {aciertos}/{total_checks}")
    if lat_dec:
        print(f"Decisión (JEV): prom {statistics.mean(lat_dec) / 1000:.2f} s | p50 {pct(lat_dec, .5) / 1000:.2f} s"
              f" | p95 {pct(lat_dec, .95) / 1000:.2f} s")
    if lat_llm:
        print(f"Redacción (LLM): prom {statistics.mean(lat_llm) / 1000:.2f} s | p50 {pct(lat_llm, .5) / 1000:.2f} s"
              f" | p95 {pct(lat_llm, .95) / 1000:.2f} s")
        if statistics.mean(lat_llm) > statistics.mean(lat_dec) > 0:
            print(f"La ruta rápida es {statistics.mean(lat_llm) / statistics.mean(lat_dec):.1f}x más rápida "
                  "que la redacción con el LLM.")
    if args.csv and filas:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
            writer.writeheader()
            writer.writerows(filas)
        print(f"Detalle guardado en {args.csv}")
    return 0 if casos_ok == n and n else 1


if __name__ == "__main__":
    sys.exit(main())
