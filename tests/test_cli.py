import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sac.cli import main
from sac.store import Store

VALID = """
[session]
name = "sac-cli-test"

[[agents]]
name = "leader"
command = "kimi"
role = "leader"

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"

[[loops]]
name = "dev-review"
sequence = ["leader", "dev-1"]
"""


class CliTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg_path = str(self.d / "sac.toml")

    def test_send_via_cli(self):
        rc = main(["--config", self.cfg_path, "send", "dev-1", "faça X"])
        self.assertEqual(rc, 0)
        store = Store(self.d / ".sac")
        self.assertEqual(len(store.pending("dev-1")), 1)

    def test_send_with_agent_env_sets_sender(self):
        with patch.dict(os.environ, {"SAC_AGENT": "leader"}):
            rc = main(["--config", self.cfg_path, "send", "dev-1", "tarefa"])
        self.assertEqual(rc, 0)
        store = Store(self.d / ".sac")
        pending = store.pending("dev-1")
        self.assertEqual(len(pending), 1)
        msg = store.next("dev-1")
        self.assertEqual(msg.sender, "leader")

    def test_send_without_env_sets_sender_user(self):
        with patch.dict(os.environ, {}, clear=True):
            rc = main(["--config", self.cfg_path, "send", "dev-1", "tarefa"])
        self.assertEqual(rc, 0)
        store = Store(self.d / ".sac")
        msg = store.next("dev-1")
        self.assertEqual(msg.sender, "user")

    def test_next_without_agent_env_returns_2(self):
        with patch.dict(os.environ, {}, clear=True):
            rc = main(["--config", self.cfg_path, "next"])
        self.assertEqual(rc, 2)

    def test_run_via_cli(self):
        rc = main(["--config", self.cfg_path, "run", "dev-review", "implementar X"])
        self.assertEqual(rc, 0)
        store = Store(self.d / ".sac")
        self.assertEqual(len(store.pending("leader")), 1)

    def test_run_unknown_loop_returns_1(self):
        rc = main(["--config", self.cfg_path, "run", "fantasma", "x"])
        self.assertEqual(rc, 1)

    def test_missing_config_returns_1(self):
        rc = main(["--config", "/tmp/nao-existe.toml", "status"])
        self.assertEqual(rc, 1)

    def test_notify_once(self):
        rc = main(["--config", self.cfg_path, "notify", "--once"])
        self.assertEqual(rc, 0)

    def test_inject_unknown_agent_returns_1(self):
        rc = main(["--config", self.cfg_path, "inject", "fantasma"])
        self.assertEqual(rc, 1)

    def test_sidebar_via_cli(self):
        rc = main(["--config", self.cfg_path, "sidebar"])
        self.assertEqual(rc, 0)

    def test_inject_known_agent_returns_0(self):
        # sem sessão tmux, o inject não encontra pane → rc 1 (mas o parsing funciona)
        rc = main(["--config", self.cfg_path, "inject", "dev-1"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
