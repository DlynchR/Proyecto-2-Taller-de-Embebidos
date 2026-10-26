import unittest

from helpers import make_config, tempdir

from edgeai_helpdesk import decision as d
from edgeai_helpdesk.config import validate_domain


def answers(cat="soporte_tecnico", conf=0.8, score=1.0, alcance=0.9, apropiado=0.95, sensible=0.1, auto=0.2):
    return {
        "categoria": {"type": "choice", "choice": cat, "probabilities": {cat: 0.9, "otro": 0.1}, "confidence": conf},
        "urgencia": {"type": "score", "score": score, "probabilities": {}, "confidence": 0.5},
        "en_alcance": {"type": "noul", "noul": alcance},
        "apropiado": {"type": "noul", "noul": apropiado},
        "datos_sensibles": {"type": "noul", "noul": sensible},
        "autoservicio": {"type": "noul", "noul": auto},
    }


class DecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempdir()
        cls.cfg = make_config(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def decide(self, **kw):
        return d.apply_policy(d.parse_answers(answers(**kw), self.cfg.dominio), self.cfg)

    def test_questions_match_jev_api(self):
        q = d.build_questions(self.cfg.dominio)
        self.assertEqual(set(q), {"categoria", "urgencia", "en_alcance", "apropiado", "datos_sensibles", "autoservicio"})
        self.assertEqual(q["categoria"]["type"], "choice")
        self.assertIsInstance(q["categoria"]["criteria"], dict)
        self.assertEqual(q["urgencia"]["type"], "score")
        self.assertIsInstance(q["urgencia"]["criteria"], list)
        self.assertTrue(2 <= len(q["urgencia"]["criteria"]) <= 10)
        for k in ("en_alcance", "apropiado", "datos_sensibles", "autoservicio"):
            self.assertEqual(q[k]["type"], "noul")
        self.assertEqual(set(q["apropiado"]["criteria"]), {"true", "false"})

    def test_normal_ticket_goes_to_queue(self):
        r = self.decide()
        self.assertEqual(r.estado, d.EN_COLA)
        self.assertTrue(r.usar_llm)
        self.assertFalse(r.revision_manual)

    def test_offensive_is_rejected_without_llm(self):
        r = self.decide(apropiado=0.1)
        self.assertEqual(r.estado, d.RECHAZADO)
        self.assertFalse(r.usar_llm)

    def test_out_of_scope(self):
        r = self.decide(alcance=0.1)
        self.assertEqual(r.estado, d.FUERA_ALCANCE)
        self.assertFalse(r.usar_llm)

    def test_self_service_when_not_urgent(self):
        self.assertEqual(self.decide(auto=0.9, score=0.2).estado, d.AUTOSERVICIO)

    def test_urgent_never_self_service(self):
        r = self.decide(auto=0.95, score=2.6)
        self.assertEqual(r.estado, d.EN_COLA)
        self.assertEqual(r.urgencia_nivel, 3)

    def test_low_confidence_needs_manual_review(self):
        r = self.decide(conf=0.05, auto=0.9)
        self.assertTrue(r.revision_manual)
        self.assertEqual(r.estado, d.EN_COLA)

    def test_unknown_category_is_unclassified(self):
        r = self.decide(cat="inventada")
        self.assertEqual(r.categoria, d.SIN_CLASIFICAR)
        self.assertTrue(r.revision_manual)

    def test_score_is_clamped(self):
        r = self.decide(score=9)
        self.assertEqual(r.urgencia_nivel, len(self.cfg.dominio["urgencia"]) - 1)

    def test_fallback_keeps_ticket(self):
        r = d.fallback_decision("sin red", self.cfg.dominio)
        self.assertEqual(r.estado, d.EN_COLA)
        self.assertTrue(r.revision_manual)
        self.assertTrue(r.usar_llm)

    def test_domain_validation(self):
        bad = dict(self.cfg.dominio)
        bad["categorias"] = {"solo": {"descripcion": "una"}}
        with self.assertRaises(ValueError):
            validate_domain(bad)


if __name__ == "__main__":
    unittest.main()
