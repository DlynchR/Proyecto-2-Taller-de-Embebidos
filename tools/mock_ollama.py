#!/usr/bin/env python3
"""Simulador de Ollama para desarrollar y probar sin Raspberry Pi ni modelos.

Implementa el subconjunto de la API que usa la mesa de ayuda:

  GET  /api/version, /api/tags
  POST /v1/systemone   (choice / noul / score con heurísticas de palabras clave)
  POST /api/chat       (respuesta JSON con 'respuesta' y 'resumen')
  POST /api/generate   (precarga)
  POST /api/pull       (descarga simulada en streaming)

No es un modelo: sirve para probar el flujo completo, la interfaz y las
pruebas automáticas. Los tiempos se pueden simular con --latencia-*.

    python3 tools/mock_ollama.py --port 11435
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KEYWORDS = {
    "soporte_tecnico": ["computadora", "pc", "enciende", "impresora", "red", "wifi", "inalambrica", "internet",
                        "contrasena", "usuario", "osciloscopio", "senal", "software", "laptop", "conecto"],
    "prestamo_equipo": ["prestamo", "presten", "prestar", "kit", "devolver", "devolucion", "componentes",
                        "multimetro", "herramienta"],
    "tramite": ["constancia", "reservar", "reserva", "induccion", "horario", "tramite", "beca"],
    "infraestructura": ["humo", "quemado", "tomacorriente", "fuga", "agua", "aire acondicionado", "luz",
                        "techo", "silla", "mesa rota", "chispa", "ruido"],
}
CRITICAL = ["humo", "quemado", "chispa", "fuga", "incendio", "electrico"]
HIGH = ["practica evaluada", "ninguno", "todo el grupo", "en este momento", "no podemos trabajar"]
OUT_OF_SCOPE = ["receta", "almuerzo", "futbol", "partido", "pelicula", "chiste", "clima"]
OFFENSIVE = ["idiota", "inutiles", "porqueria", "estupido", "malditos"]
SENSITIVE = ["contrasena", "password", "cedula", "clave es", "pin"]
SELF_SERVICE = ["como me conecto", "como hago", "que ocupo", "como solicito", "quiero reservar", "como puedo"]


def norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def softmax(scores: dict[str, float]) -> dict[str, float]:
    m = max(scores.values())
    exp = {k: math.exp(v - m) for k, v in scores.items()}
    s = sum(exp.values())
    return {k: v / s for k, v in exp.items()}


def confidence(probs: dict[str, float]) -> float:
    n = len(probs)
    h = -sum(p * math.log(p) for p in probs.values() if p > 0)
    return 1 - h / math.log(n) if n > 1 else 1.0


def message_of(state) -> str:
    if isinstance(state, dict):
        return str(state.get("mensaje_del_usuario") or json.dumps(state, ensure_ascii=False))
    return str(state)


def answer(qname: str, q: dict, text: str) -> dict:
    t = norm(text)
    has = lambda words: sum(1 for w in words if w in t)  # noqa: E731
    qtype = q.get("type")
    if qtype == "choice":
        options = list(q.get("criteria", {}).keys())
        scores = {o: 0.2 for o in options}
        for o in options:
            scores[o] += 2.5 * has(KEYWORDS.get(o, []))
        if "otro" in scores and max(scores.values()) <= 0.2:
            scores["otro"] += 1.5
        probs = softmax(scores)
        best = max(probs, key=probs.get)
        return {"type": "choice", "choice": best, "probabilities": {k: round(v, 4) for k, v in probs.items()},
                "confidence": round(confidence(probs), 4)}
    if qtype == "score":
        n = len(q.get("criteria", []))
        level = 0
        if has(HIGH):
            level = 2
        if has(CRITICAL):
            level = n - 1
        elif has(["no enciende", "no puedo", "falla", "no funciona"]):
            level = max(level, 1)
        raw = {str(i): (3.0 if i == level else 1.0 / (1 + abs(i - level))) for i in range(n)}
        probs = softmax(raw)
        score = sum(int(k) * p for k, p in probs.items())
        return {"type": "score", "score": round(score, 4),
                "legend": {str(i): c for i, c in enumerate(q.get("criteria", []))},
                "probabilities": {k: round(v, 4) for k, v in probs.items()},
                "confidence": round(confidence(probs), 4)}
    # noul
    if qname == "en_alcance":
        p = 0.08 if has(OUT_OF_SCOPE) else 0.93
    elif qname == "apropiado":
        p = 0.04 if has(OFFENSIVE) >= 2 else 0.97
    elif qname == "datos_sensibles":
        p = 0.91 if has(SENSITIVE) else 0.05
    elif qname == "autoservicio":
        p = 0.82 if has(SELF_SERVICE) else 0.2
    else:
        p = 0.5
    return {"type": "noul", "noul": p}


class Handler(BaseHTTPRequestHandler):
    models = ["tev1:0.8b", "qwen2.5:1.5b"]
    lat_decision = 0.0
    lat_llm = 0.0
    fail_systemone = False

    def log_message(self, *args):  # silencioso
        pass

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):  # noqa: N802
        if self.path == "/api/version":
            return self._json({"version": "0.40.6-mock"})
        if self.path == "/api/tags":
            return self._json({"models": [{"name": m, "model": m} for m in self.models]})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        req = self._body()
        model = req.get("model", "")
        if self.path in ("/v1/systemone", "/api/chat", "/api/generate") and not any(
            model == m or model + ":latest" == m for m in self.models
        ):
            return self._json({"error": f"model '{model}' not found"}, 404)
        if self.path == "/v1/systemone":
            if self.fail_systemone:
                return self._json({"error": "scoring failed"}, 500)
            time.sleep(self.lat_decision)
            text = message_of(req.get("state", ""))
            answers = {k: answer(k, q, text) for k, q in req.get("questions", {}).items()}
            return self._json({"model": model, "answers": answers,
                               "usage": {"input_tokens": len(text.split()) * 3, "output_tokens": len(answers)}})
        if self.path == "/api/chat":
            time.sleep(self.lat_llm)
            user = req["messages"][-1]["content"]
            cat = re.search(r"Categoría: (\S+)", user)
            mensaje = user.split("Mensaje de la persona:", 1)[-1].strip()
            respuesta = (f"Gracias por su consulta. La registramos como "
                         f"{cat.group(1) if cat else 'general'}. Un encargado le dará seguimiento; "
                         "mientras tanto, revise las indicaciones del laboratorio.")
            content = json.dumps({"respuesta": respuesta, "resumen": mensaje[:60]}, ensure_ascii=False)
            return self._json({"model": model, "message": {"role": "assistant", "content": content},
                               "done": True})
        if self.path == "/api/generate":
            return self._json({"model": model, "response": "", "done": True})
        if self.path == "/api/pull":
            if model not in self.models:
                self.models.append(model)
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            for ev in ({"status": "pulling manifest"}, {"status": "downloading", "total": 100, "completed": 100},
                       {"status": "success"}):
                self.wfile.write((json.dumps(ev) + "\n").encode())
            return None
        return self._json({"error": "not found"}, 404)


def serve(port: int, models=None, lat_decision=0.0, lat_llm=0.0, host="127.0.0.1"):
    handler = type("MockHandler", (Handler,), {
        "models": list(models or Handler.models), "lat_decision": lat_decision, "lat_llm": lat_llm,
    })
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=11435)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--modelos", default="tev1:0.8b,qwen2.5:1.5b", help="modelos 'instalados'")
    p.add_argument("--latencia-decision", type=float, default=0.3, help="segundos")
    p.add_argument("--latencia-llm", type=float, default=2.0, help="segundos")
    a = p.parse_args()
    server = serve(a.port, a.modelos.split(","), a.latencia_decision, a.latencia_llm, a.host)
    print(f"Simulador de Ollama en http://{a.host}:{a.port} (modelos: {a.modelos})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
