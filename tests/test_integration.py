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
        out = subprocess.run(["tmux", "list-windows", "-t", "sac-itest",
                              "-F", "#{window_name}"],
                             capture_output=True, text=True).stdout.split()
        self.assertIn("leader", out)
        self.assertIn("dev-1", out)
        self.assertEqual(main(["--config", self.cfg, "send", "dev-1", "echo oi"]), 0)
        time.sleep(1)
        pane = subprocess.run(["tmux", "capture-pane", "-p", "-t", "sac-itest:dev-1"],
                              capture_output=True, text=True).stdout
        self.assertIn("sac next", pane)
        self.assertEqual(main(["--config", self.cfg, "down"]), 0)


if __name__ == "__main__":
    unittest.main()
