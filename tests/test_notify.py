import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sac.commands import cmd_recv, cmd_run, notify_sweep
from sac.config import ConfigError, load_config
from sac.store import Store
from sac.tmux import Tmux
from tests.test_tmux import FakeRunner

VALID = """
[session]
name = "sac-test"
poke_stale_after = 120

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
max_iterations = 3
"""

NOW = datetime.now()


class NotifyTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d / ".sac")
        self.runner = FakeRunner(outputs={
            "list-panes": "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n",
        })
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_sweep_pokes_only_stale(self):
        old = NOW - timedelta(seconds=300)
        self.store.send("leader", "dev-1", "velha", now=old)
        self.store.send("leader", "dev-1", "nova", now=NOW)
        result = notify_sweep(self.cfg, self.store, self.tmux)
        self.assertEqual(result, {"dev-1": 1})
        poke_calls = [c for c in self.runner.calls if "aguardando" in c[-1]]
        self.assertEqual(len(poke_calls), 1)
        self.assertIn("1 mensagem", poke_calls[0][-1])

    def test_sweep_no_stale_no_poke(self):
        self.store.send("leader", "dev-1", "nova", now=NOW)
        result = notify_sweep(self.cfg, self.store, self.tmux)
        self.assertEqual(result, {})
        self.assertEqual([c for c in self.runner.calls if "send-keys" in c], [])

    def test_recv_finished(self):
        r = FakeRunner(outputs={
            "list-panes": "%2|env SAC_AGENT=dev-1 opencode\n",
            "capture-pane": "resposta completa\nSAC_DONE\n",
        })
        t = Tmux("sac-test", runner=r)
        self.assertEqual(cmd_recv(self.cfg, t, "dev-1"), 0)

    def test_recv_in_progress(self):
        r = FakeRunner(outputs={
            "list-panes": "%2|env SAC_AGENT=dev-1 opencode\n",
            "capture-pane": "trabalhando...\n",
        })
        t = Tmux("sac-test", runner=r)
        self.assertEqual(cmd_recv(self.cfg, t, "dev-1"), 1)

    def test_run_kicks_loop(self):
        mid = cmd_run(self.cfg, self.store, self.tmux, "dev-review", "implementar X")
        self.assertIn("from-user", mid)
        pending = self.store.pending("leader")
        self.assertEqual(len(pending), 1)

    def test_run_unknown_loop_fails(self):
        with self.assertRaises(ConfigError):
            cmd_run(self.cfg, self.store, self.tmux, "fantasma", "x")


if __name__ == "__main__":
    unittest.main()
