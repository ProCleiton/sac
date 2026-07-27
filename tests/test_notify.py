import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sac.commands import cmd_notify, cmd_recv, notify_sweep
from sac.config import load_config
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
"""

NOW = datetime.now()


class NotifyTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d)
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

    def test_sweep_pula_lider(self):
        old = NOW - timedelta(seconds=300)
        self.store.send("dev-1", "leader", "velha", now=old)
        self.store.next("leader")
        result = notify_sweep(self.cfg, self.store, self.tmux)
        self.assertEqual(result, {}, "líder não deve ser re-cutucado")
        poke_calls = [c for c in self.runner.calls if "aguardando" in c[-1]]
        self.assertEqual(poke_calls, [], "nenhum poke no pane do líder")

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

    def test_notify_sweep_exception_logged(self):
        from unittest.mock import patch
        self.store.send("leader", "dev-1", "test", now=NOW)
        original_stale = self.store.stale
        call_count = [0]
        def failing_stale(agent, seconds, now=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("simulated stale failure")
            return original_stale(agent, seconds, now)
        with patch.object(self.store, 'stale', failing_stale):
            cmd_notify(self.cfg, self.store, self.tmux, once=True)
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("loop_error", log)
        self.assertIn("simulated stale failure", log)

    def test_notify_sweep_recheck_before_poke(self):
        old = NOW - timedelta(seconds=300)
        self.store.send("leader", "dev-1", "velha", now=old)
        self.store.next("dev-1")
        self.store.done("dev-1", self.store.claimed("dev-1")[0], "done", now=NOW)
        result = notify_sweep(self.cfg, self.store, self.tmux)
        self.assertEqual(result, {}, "mensagem recém-done não deve gerar poke")

    def test_notify_sweep_backoff(self):
        old = NOW - timedelta(seconds=300)
        self.store.send("leader", "dev-1", "velha", now=old)
        self.store.next("dev-1")
        mid = self.store.claimed("dev-1")[0]
        poke_state = {"dev-1": {mid: time.monotonic()}}
        result = notify_sweep(self.cfg, self.store, self.tmux, poke_state=poke_state)
        self.assertEqual(result, {}, "com backoff, poke não deve ser enviado (tempo insuficiente)")

    def test_notify_backoff_wired_via_cmd_notify(self):
        old = NOW - timedelta(seconds=300)
        self.store.send("leader", "dev-1", "velha", now=old)
        self.store.next("dev-1")
        poke_state: dict = {}
        from unittest.mock import patch
        with patch("sac.commands.time.sleep"):
            r1 = notify_sweep(self.cfg, self.store, self.tmux, poke_state=poke_state)
        self.assertIn("dev-1", r1, "1ª chamada: poke enviado")
        with patch("sac.commands.time.sleep"):
            r2 = notify_sweep(self.cfg, self.store, self.tmux, poke_state=poke_state)
        self.assertEqual(r2, {}, "2ª chamada com mesmo poke_state: backoff respeitado")

    def test_notify_sweep_recheck_before_poke(self):
        old = NOW - timedelta(seconds=300)
        self.store.send("leader", "dev-1", "velha", now=old)
        self.store.next("dev-1")
        self.store.done("dev-1", self.store.claimed("dev-1")[0], "done", now=NOW)
        result = notify_sweep(self.cfg, self.store, self.tmux)
        self.assertEqual(result, {}, "mensagem recém-done não deve gerar poke")


if __name__ == "__main__":
    unittest.main()
