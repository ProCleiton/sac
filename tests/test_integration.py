import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from sac.cli import main

TMUX = shutil.which("tmux")

VALID = """
[session]
name = "sac-itest"

[[agents]]
name = "leader"
command = "bash"
role = "leader"

[[agents]]
name = "dev-1"
command = "bash"
role = "aux"
"""


@unittest.skipUnless(TMUX, "tmux não disponível")
class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = str(self.d / "sac.toml")
        subprocess.run(["tmux", "kill-session", "-t", "sac-itest"],
                       capture_output=True)

    def tearDown(self):
        subprocess.run(["tmux", "kill-session", "-t", "sac-itest"],
                       capture_output=True)

    def test_up_send_capture_down(self):
        self.assertEqual(main(["--config", self.cfg, "up"]), 0)
        time.sleep(1)
        # Janelas: leader + dev-1 + dash
        out = subprocess.run(["tmux", "list-windows", "-t", "sac-itest",
                              "-F", "#{window_name}"],
                             capture_output=True, text=True).stdout.split()
        self.assertIn("leader", out, f"janela leader ausente: {out}")
        self.assertIn("dev-1", out, f"janela dev-1 ausente: {out}")
        self.assertIn("dash", out)
        # Cada janela de agente tem sidebar (sac sidebar) + harness pane
        for w in ("leader", "dev-1"):
            cmds = subprocess.run(["tmux", "list-panes", "-t", f"sac-itest:{w}",
                                   "-F", "#{pane_start_command}"],
                                  capture_output=True, text=True).stdout
            self.assertIn("sac sidebar", cmds, f"sidebar faltando na janela {w}: {cmds}")
        # Dash tem 3 panes, um roda sac log -f
        panes = subprocess.run(["tmux", "list-panes", "-t", "sac-itest:dash",
                                "-F", "#{pane_start_command}"],
                               capture_output=True, text=True).stdout
        lines = [l.strip() for l in panes.splitlines() if l.strip()]
        self.assertGreaterEqual(len(lines), 2, f"dash deve ter 2+ panes, veio: {lines}")
        self.assertTrue(any("sac log -f" in l for l in lines),
                        f"deve conter 'sac log -f', veio: {lines}")
        # select-pane por id não falha
        pane_ids = subprocess.run(["tmux", "list-panes", "-t", "sac-itest:dash",
                                   "-F", "#{pane_id}"],
                                  capture_output=True, text=True).stdout.split()
        if pane_ids:
            pid = pane_ids[0]
            r = subprocess.run(["tmux", "select-pane", "-t", pid],
                               capture_output=True)
            self.assertEqual(r.returncode, 0, f"select-pane -t {pid} falhou")
        # send persiste mensagem e cutuca o pane com "sac next"
        self.assertEqual(main(["--config", self.cfg, "send", "dev-1", "echo oi"]), 0)
        from sac.store import Store
        store = Store(self.d / ".sac")
        self.assertEqual(len(store.pending("dev-1")), 1)
        time.sleep(1)
        # Captura o pane do dev-1 via SAC_AGENT
        dev1_out = subprocess.run(["tmux", "list-panes", "-s", "-t", "sac-itest",
                                   "-F", "#{pane_id}|#{pane_start_command}"],
                                  capture_output=True, text=True).stdout
        dev1_pid = ""
        for line in dev1_out.splitlines():
            if "SAC_AGENT=dev-1" in line:
                dev1_pid = line.split("|")[0]
                break
        self.assertNotEqual(dev1_pid, "", "deve encontrar pane do dev-1")
        pane = subprocess.run(["tmux", "capture-pane", "-p", "-t", dev1_pid],
                              capture_output=True, text=True).stdout
        self.assertIn("sac next", pane, f"poke 'sac next' deve estar visível no pane, veio: {pane[-200:]}")
        # Attach cai no leader: última janela ativa é a do leader
        active = subprocess.run(["tmux", "display-message", "-p", "-t", "sac-itest",
                                 "#{window_name}"],
                                capture_output=True, text=True).stdout.strip()
        self.assertEqual(active, "leader", f"janela ativa deve ser leader, veio: {active}")
        self.assertEqual(main(["--config", self.cfg, "down"]), 0)


if __name__ == "__main__":
    unittest.main()
