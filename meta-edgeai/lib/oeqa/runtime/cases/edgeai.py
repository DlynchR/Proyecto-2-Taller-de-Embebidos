import json
import shlex
import time

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase


class EdgeAITest(OERuntimeTestCase):
    def command(self, command, timeout=120):
        status, output = self.target.run(command, timeout=timeout)
        self.assertEqual(status, 0, output)
        return output

    @OETestDepends(["ssh.SSHTest.test_ssh"])
    def test_services(self):
        self.command("systemctl start ollama edgeai-helpdesk edgeai-provision", timeout=300)
        self.command("systemctl is-active ollama edgeai-helpdesk edgeai-provision")
        self.command("test -f /etc/edgeai-qemu-testing")
        self.command("test ! -f /etc/wpa_supplicant/wpa_supplicant-wlan0.conf")
        self.command("edgeai-admin autoprueba", timeout=300)
        for path in ("/", "/panel", "/api/health"):
            self.command("curl -fsS http://127.0.0.1" + path)

    @OETestDepends(["edgeai.EdgeAITest.test_services"])
    def test_ticket_survives_reboot(self):
        payload = json.dumps({"texto": "La computadora no enciende", "nombre": "QEMU"})
        output = self.command(
            "curl -fsS -H 'Content-Type: application/json' --data "
            + shlex.quote(payload) + " http://127.0.0.1/api/tickets"
        )
        ticket = json.loads(output)
        self.assertEqual(ticket["modelo_decision"], "tev1:0.8b")
        self.assertGreater(ticket["id"], 0)
        self.command("sync")
        boot_id = self.command("cat /proc/sys/kernel/random/boot_id").strip()
        self.target.run("systemctl reboot --no-block", timeout=30, ignore_ssh_fails=True)
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            status, current_id = self.target.run(
                "cat /proc/sys/kernel/random/boot_id", timeout=20, ignore_ssh_fails=True
            )
            if status == 0 and current_id.strip() != boot_id:
                break
            time.sleep(5)
        else:
            self.fail("QEMU no completo el reinicio en 600 segundos")
        self.command("systemctl start edgeai-helpdesk", timeout=300)
        query = f"http://127.0.0.1/api/consulta/{ticket['id']}?clave={ticket['clave']}"
        saved = json.loads(self.command("curl -fsS " + shlex.quote(query)))
        self.assertEqual(saved["id"], ticket["id"])

    @OETestDepends(["edgeai.EdgeAITest.test_ticket_survives_reboot"])
    def test_benchmark(self):
        self.command("edgeai-bench --llm --csv /tmp/edgeai-bench.csv", timeout=600)