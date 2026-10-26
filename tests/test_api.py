"""Prueba de punta a punta: servidor real + simulador de Ollama."""

import json
import threading
import time
import unittest
import urllib.error
import urllib.request

from helpers import ROOT, make_config, tempdir
from mock_ollama import serve as serve_mock

from edgeai_helpdesk.server import build_server
from edgeai_helpdesk.service import HelpdeskService


def free_server(factory):
    server = factory(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempdir()
        cls.mock, mock_port = free_server(lambda p: serve_mock(p, lat_llm=0.05))
        cls.cfg = make_config(cls.tmp.name, f"http://127.0.0.1:{mock_port}")
        cls.service = HelpdeskService(cls.cfg)
        cls.service.start()
        cls.server, port = free_server(lambda p: build_server(cls.service, "127.0.0.1", p))
        cls.base = f"http://127.0.0.1:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.service.stop()
        cls.service.store.close()
        cls.mock.shutdown()
        cls.mock.server_close()
        cls.tmp.cleanup()

    def call(self, method, path, body=None, headers=None):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def wait_reply(self, t, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            _, c = self.call("GET", f"/api/consulta/{t['id']}?clave={t['clave']}")
            if c["respuesta_estado"] not in ("pendiente", "generando"):
                return c
            time.sleep(0.1)
        self.fail("la respuesta no llegó")

    def test_health(self):
        st, h = self.call("GET", "/api/health")
        self.assertEqual(st, 200)
        self.assertTrue(h["listo"])
        self.assertEqual(h["ollama"]["modelos_faltantes"], [])
        self.assertEqual(h["indicadores"]["modo"], "simulado")

    def test_static_pages(self):
        for path, needle in (("/", b"Enviar consulta"), ("/panel", b"Panel de atenci"), ("/static/app.css", b":root")):
            with urllib.request.urlopen(self.base + path, timeout=5) as r:
                self.assertIn(needle, r.read())
        st, _ = self.call("GET", "/static/../service.py")
        self.assertEqual(st, 404)

    def test_full_flow_critical_ticket(self):
        st, t = self.call("POST", "/api/tickets", {"texto": "Sale humo del tomacorriente de la mesa 2"})
        self.assertEqual(st, 201)
        self.assertEqual(t["categoria"], "infraestructura")
        self.assertEqual(t["estado"], "en_cola")
        self.assertGreaterEqual(t["urgencia_nivel"], 2)
        c = self.wait_reply(t)
        self.assertEqual(c["respuesta_estado"], "lista")
        self.assertTrue(c["respuesta"])
        _, cola = self.call("GET", "/api/cola")
        self.assertEqual(cola[0]["id"], t["id"])  # la urgente va primero
        st, _ = self.call("POST", f"/api/tickets/{t['id']}/atender")
        self.assertEqual(st, 200)
        st, _ = self.call("POST", f"/api/tickets/{t['id']}/atender")
        self.assertEqual(st, 409)

    def test_out_of_scope_skips_llm(self):
        _, t = self.call("POST", "/api/tickets", {"texto": "Recomiéndenme una receta para el almuerzo"})
        self.assertEqual(t["estado"], "fuera_alcance")
        self.assertEqual(t["respuesta_estado"], "omitida")
        self.assertIn("solo atiende", t["respuesta"])

    def test_consulta_requires_key(self):
        _, t = self.call("POST", "/api/tickets", {"texto": "La impresora no imprime"})
        st, _ = self.call("GET", f"/api/consulta/{t['id']}?clave=mala")
        self.assertEqual(st, 404)
        st, c = self.call("GET", f"/api/consulta/{t['id']}?clave={t['clave']}")
        self.assertEqual(st, 200)
        self.assertNotIn("texto", c)

    def test_validation(self):
        st, e = self.call("POST", "/api/tickets", {"texto": "hi"})
        self.assertEqual(st, 400)
        st, _ = self.call("POST", "/api/tickets", {"texto": "x" * 3000})
        self.assertEqual(st, 400)

    def test_panel_token(self):
        self.cfg.web.panel_token = "secreto"
        try:
            server, port = free_server(lambda p: build_server(self.service, "127.0.0.1", p))
            base = self.base
            self.base = f"http://127.0.0.1:{port}"
            self.assertEqual(self.call("GET", "/api/cola")[0], 401)
            self.assertEqual(self.call("GET", "/api/cola", headers={"X-Panel-Token": "secreto"})[0], 200)
            self.assertEqual(self.call("POST", "/api/tickets", {"texto": "La red no funciona"})[0], 201)
            server.shutdown()
            server.server_close()
        finally:
            self.cfg.web.panel_token = ""
            self.base = base

    def test_attend_next(self):
        self.call("POST", "/api/tickets", {"texto": "La computadora no enciende"})
        st, t = self.call("POST", "/api/atender-siguiente")
        self.assertEqual(st, 200)
        self.assertEqual(t.get("estado", "atendido"), "atendido")


class DegradedTests(unittest.TestCase):
    """Sin Ollama el sistema sigue recibiendo tiquetes (revisión manual)."""

    def test_ticket_accepted_when_ollama_down(self):
        with tempdir() as tmp:
            cfg = make_config(tmp, "http://127.0.0.1:9")
            cfg.ollama.timeout_decision = 2
            cfg.ollama.timeout_llm = 2
            svc = HelpdeskService(cfg)
            svc.start()
            try:
                t = svc.submit("La computadora no enciende")
                self.assertEqual(t["estado"], "en_cola")
                self.assertTrue(t["revision_manual"])
                deadline = time.time() + 10
                while time.time() < deadline and svc.store.get(t["id"])["respuesta_estado"] != "error":
                    time.sleep(0.1)
                self.assertEqual(svc.store.get(t["id"])["respuesta_estado"], "error")
                self.assertFalse(svc.health()["listo"])
            finally:
                svc.stop()


class BenchTests(unittest.TestCase):
    def test_demo_cases_pass_against_mock(self):
        from edgeai_helpdesk import bench

        with tempdir() as tmp:
            mock, port = free_server(lambda p: serve_mock(p))
            conf = f"{tmp}/bench.conf"
            with open(conf, "w") as fh:
                fh.write(f"[ollama]\nurl = http://127.0.0.1:{port}\n[datos]\n"
                         f"db = {tmp}/t.db\ncategorias = {ROOT}/app/config/categorias.json\n"
                         f"casos = {ROOT}/app/config/casos_demo.json\n")
            try:
                self.assertEqual(bench.main(["--config", conf, "--llm", "--csv", f"{tmp}/b.csv"]), 0)
            finally:
                mock.shutdown()
                mock.server_close()


if __name__ == "__main__":
    unittest.main()
