import os
import signal
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sac.commands import _daemon_active, cmd_send
from sac.config import load_config
from sac.store import Store
from sac.tmux import Tmux
from tests.test_tmux import FakeRunner

VALID = """
[session]
name = "sac-test"

[[agents]]
name = "leader"
command = "kimi"
role = "leader"

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"
"""


class DaemonFlagTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(self.d / "sac.toml")
        self.store = Store(self.d / ".sac")

    def _create_pid(self, pid=None):
        self.store.root.mkdir(parents=True, exist_ok=True)
        (self.store.root / "daemon.pid").write_text(str(pid or os.getpid()), encoding="utf-8")

    def test_daemon_not_active_by_default(self):
        self.assertFalse(_daemon_active(self.store))

    def test_daemon_active_when_pid_exists(self):
        self._create_pid()
        self.assertTrue(_daemon_active(self.store))

    def test_daemon_inactive_when_pid_orphan(self):
        self._create_pid(999999999)
        self.assertFalse(_daemon_active(self.store))
        self.assertFalse((self.store.root / "daemon.pid").exists(),
                         "pid órfão deve ser removido")

    def test_daemon_inactive_when_pid_non_numeric(self):
        p = self.store.root / "daemon.pid"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("abc", encoding="utf-8")
        self.assertFalse(_daemon_active(self.store))
        self.assertFalse(p.exists(), "pid inválido deve ser removido")

    def test_cmd_send_skips_poke_when_daemon_active(self):
        self._create_pid()
        runner = FakeRunner(outputs={
            "list-panes": "%2|env SAC_AGENT=dev-1 opencode\n",
        })
        tmux = Tmux("sac-test", runner=runner)
        cmd_send(self.cfg, self.store, tmux, "dev-1", "tarefa")
        send_keys_calls = [c for c in runner.calls if c[1] == "send-keys"]
        self.assertEqual(len(send_keys_calls), 0,
                         "daemon ativo: não deve cutucar")

    def test_cmd_send_pokes_without_daemon(self):
        runner = FakeRunner(outputs={
            "list-panes": "%2|env SAC_AGENT=dev-1 opencode\n",
        })
        tmux = Tmux("sac-test", runner=runner)
        cmd_send(self.cfg, self.store, tmux, "dev-1", "tarefa")
        send_keys_calls = [c for c in runner.calls if c[1] == "send-keys"]
        self.assertGreaterEqual(len(send_keys_calls), 1,
                                "sem daemon: deve cutucar")

    def test_daemon_pid_removed_on_exit(self):
        from sac.daemon import Daemon
        d = Daemon(self.cfg, self.store, Tmux("sac-test"))
        self.assertFalse(d._pid_path().exists())
        d._write_pid()
        self.assertTrue(d._pid_path().exists())
        d._remove_pid()
        self.assertFalse(d._pid_path().exists())

    def test_deliver_next_uses_paste_and_header(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%2|env SAC_AGENT=dev-1 opencode\n"
        d = Daemon(self.cfg, self.store, tmux)
        mid = self.store.send("user", "dev-1", "execute task X")
        d._deliver_next("dev-1")
        paste_calls = [c for c in runner.calls if c[1] == "paste-buffer"]
        self.assertEqual(len(paste_calls), 1, "deve usar paste")
        enter_calls = [c for c in runner.calls if c[1] == "send-keys" and c[-1] == "Enter"]
        self.assertEqual(len(enter_calls), 1, "deve dar enter após paste")
        self.assertEqual(len(self.store.pending("dev-1")), 0, "msg deve ser claimed")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("deliver", log)

    def test_deliver_next_no_pane_does_not_claim(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        runner.outputs["list-panes"] = "%1|some other process\n"
        tmux = Tmux("sac-test", runner=runner)
        d = Daemon(self.cfg, self.store, tmux)
        mid = self.store.send("user", "dev-1", "task")
        d._deliver_next("dev-1")
        self.assertEqual(len(self.store.pending("dev-1")), 1,
                         "msg não deve ser claimed sem pane")

    def test_deliver_next_no_pending(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        runner.outputs["list-panes"] = "%1|some other process\n"
        tmux = Tmux("sac-test", runner=runner)
        d = Daemon(self.cfg, self.store, tmux)
        d._deliver_next("dev-1")
        paste_calls = [c for c in runner.calls if c[1] == "paste-buffer"]
        self.assertEqual(len(paste_calls), 0, "sem pendentes, sem paste")

    def test_process_agent_delivers_pending(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%2|env SAC_AGENT=dev-1 opencode\n"
        d = Daemon(self.cfg, self.store, tmux)
        self.store.send("user", "dev-1", "new task")
        d._process_agent("dev-1")
        paste_calls = [c for c in runner.calls if c[1] == "paste-buffer"]
        self.assertEqual(len(paste_calls), 1, "deve entregar pendente via paste")

    def test_process_agent_stale_poke(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%2|env SAC_AGENT=dev-1 opencode\n"
        d = Daemon(self.cfg, self.store, tmux)
        old = datetime.now() - timedelta(seconds=300)
        mid = self.store.send("user", "dev-1", "old task", now=old)
        self.store.next("dev-1")
        d._process_agent("dev-1")
        stale_calls = [c for c in runner.calls if "pendente" in str(c)]
        self.assertEqual(len(stale_calls), 1, "deve cutucar tarefa stale")

    def test_process_agent_throttle(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%2|env SAC_AGENT=dev-1 opencode\n"
        d = Daemon(self.cfg, self.store, tmux)
        old = datetime.now() - timedelta(seconds=300)
        self.store.send("user", "dev-1", "old task", now=old)
        self.store.next("dev-1")
        d._process_agent("dev-1")
        d._process_agent("dev-1")
        stale_calls = [c for c in runner.calls if "pendente" in str(c)]
        self.assertEqual(len(stale_calls), 1, "segunda chamada não deve cutucar (throttle)")

    def test_run_writes_and_removes_pid(self):
        from sac.daemon import Daemon
        d = Daemon(self.cfg, self.store, Tmux("sac-test"))
        saved_loop = d._loop
        d._loop = lambda: None
        try:
            d.run()
            self.assertFalse(d._pid_path().exists(), "pid deve ser limpo ao final")
        finally:
            d._loop = saved_loop


if __name__ == "__main__":
    unittest.main()
