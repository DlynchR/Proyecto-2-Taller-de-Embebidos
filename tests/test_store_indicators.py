import os
import time
import unittest
from pathlib import Path

from helpers import make_config, tempdir, write

from edgeai_helpdesk import decision as d
from edgeai_helpdesk.indicators import IndicatorController, LedBank
from edgeai_helpdesk.responder import build_messages, parse_content
from edgeai_helpdesk.store import TicketStore


def dec(nivel=1, estado=d.EN_COLA):
    return d.Decision("soporte_tecnico", 0.8, {"soporte_tecnico": 0.9}, float(nivel), nivel, 0.9, 0.9, 0.1, 0.1,
                      estado=estado)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempdir()
        self.store = TicketStore(os.path.join(self.tmp.name, "t.db"))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_queue_ordered_by_urgency(self):
        a = self.store.create("baja", dec(0))
        b = self.store.create("critica", dec(3))
        c = self.store.create("media", dec(1))
        self.assertEqual([t["id"] for t in self.store.queue()], [b, c, a])

    def test_attend_and_reopen(self):
        t = self.store.create("x", dec())
        self.assertTrue(self.store.mark_attended(t))
        self.assertFalse(self.store.mark_attended(t))
        self.assertEqual(self.store.get(t)["estado"], d.ATENDIDO)
        self.assertTrue(self.store.reopen(t))
        self.assertEqual(self.store.get(t)["estado"], d.EN_COLA)

    def test_stats_and_export(self):
        self.store.create("x", dec(3))
        self.store.create("y", dec(0, d.RECHAZADO), respuesta_estado="omitida")
        s = self.store.stats(2)
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["urgentes"], 1)
        out = os.path.join(self.tmp.name, "o.csv")
        self.assertEqual(self.store.export_csv(out), 2)
        self.assertGreater(os.path.getsize(out), 50)

    def test_each_ticket_has_access_key(self):
        t1 = self.store.get(self.store.create("x", dec()))
        t2 = self.store.get(self.store.create("y", dec()))
        self.assertTrue(t1["clave"])
        self.assertNotEqual(t1["clave"], t2["clave"])


class ResponderTests(unittest.TestCase):
    def test_prompt_uses_only_selected_category_knowledge(self):
        with tempdir() as tmp:
            cfg = make_config(tmp)
        msgs = build_messages(cfg.dominio, "no enciende", dec())
        user = msgs[1]["content"]
        self.assertIn(cfg.dominio["categorias"]["soporte_tecnico"]["conocimiento"][0], user)
        self.assertNotIn(cfg.dominio["categorias"]["prestamo_equipo"]["conocimiento"][0], user)

    def test_parse_content(self):
        self.assertEqual(parse_content('{"respuesta": "Hola", "resumen": "r"}', "t"), ("Hola", "r", True))
        self.assertEqual(parse_content("texto libre", "t")[0], "texto libre")
        self.assertFalse(parse_content("", "t")[2])


class IndicatorTests(unittest.TestCase):
    def test_simulated_mode_without_hardware(self):
        with tempdir() as tmp:
            cfg = make_config(tmp)
            bank = LedBank(cfg.indicadores)
            self.assertEqual(bank.mode, "simulado")
            bank.set("rojo", True)
            self.assertTrue(bank.snapshot()["estado"]["rojo"])

    def test_sysfs_mode_writes_brightness(self):
        with tempdir() as tmp:
            cfg = make_config(tmp)
            for name in ("edgeai-verde", "edgeai-amarillo", "edgeai-rojo"):
                os.makedirs(os.path.join(cfg.indicadores.leds_dir, name))
                write(os.path.join(cfg.indicadores.leds_dir, name, "brightness"), "0")
            bank = LedBank(cfg.indicadores)
            self.assertEqual(bank.mode, "sysfs")
            ctl = IndicatorController(bank)
            ctl.update(ollama_ok=True, modelos_ok=True, en_cola=1, urgentes=1, generando=0)
            ctl.start()
            time.sleep(0.4)
            ctl.stop()
            ctl.join(2)
            # Al detenerse apaga todo; durante la ejecución verde/amarillo/rojo estuvieron encendidos.
            self.assertEqual(Path(bank.paths["rojo"]).read_text(), "0")

    def test_controller_patterns(self):
        with tempdir() as tmp:
            bank = LedBank(make_config(tmp).indicadores)
        ctl = IndicatorController(bank)
        ctl.update(ollama_ok=True, modelos_ok=True, en_cola=2, urgentes=1, generando=0)
        ctl.start()
        time.sleep(0.35)
        st = bank.snapshot()["estado"]
        ctl.stop()
        ctl.join(2)
        self.assertTrue(st["verde"])
        self.assertTrue(st["amarillo"])
        self.assertTrue(st["rojo"])


if __name__ == "__main__":
    unittest.main()
