import subprocess
import unittest
from pathlib import Path

from sac.tmux import Tmux


class FakeRunner:
    def __init__(self, outputs=None, rc=0):
        self.calls = []
        self.outputs = outputs or {}
        self.rc = rc

    def __call__(self, *args):
        self.calls.append(args)
        key = args[1] if len(args) > 1 else ""
        out = self.outputs.get(key, "")
        rc = self.outputs.get(("rc", key), self.rc)
        return subprocess.CompletedProcess(args, rc, stdout=out, stderr="")


class TmuxTest(unittest.TestCase):
    def test_has_session_true(self):
        t = Tmux("sac", runner=FakeRunner(rc=0))
        self.assertTrue(t.has_session())

    def test_has_session_false(self):
        t = Tmux("sac", runner=FakeRunner(rc=1))
        self.assertFalse(t.has_session())

    def test_new_session_command(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.new_session("leader", ["kimi", "--model", "k3"])
        self.assertEqual(r.calls[0], ("tmux", "new-session", "-d", "-s", "sac", "-n", "leader", "kimi --model k3"))

    def test_new_session_with_env_prefix(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.new_session("leader", ["kimi", "--model", "k3"], env={"SAC_AGENT": "leader"})
        self.assertEqual(
            r.calls[0],
            ("tmux", "new-session", "-d", "-s", "sac", "-n", "leader", "env SAC_AGENT=leader kimi --model k3"),
        )

    def test_new_window_with_env_prefix(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.new_window("dev-1", ["opencode", "-m", "x/y"], env={"SAC_AGENT": "dev-1"})
        self.assertEqual(
            r.calls[0],
            ("tmux", "new-window", "-t", "sac", "-n", "dev-1", "env SAC_AGENT=dev-1 opencode -m x/y"),
        )

    def test_send_keys_literal_then_enter(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.send_keys("dev-1", "SAC: mensagem nova — rode `sac next`")
        self.assertEqual(r.calls[0], ("tmux", "send-keys", "-t", "sac:dev-1", "-l", "--", "SAC: mensagem nova — rode `sac next`"))
        self.assertEqual(r.calls[1], ("tmux", "send-keys", "-t", "sac:dev-1", "Enter"))

    def test_capture_pane(self):
        r = FakeRunner(outputs={"capture-pane": "linha1\nlinha2\n"})
        t = Tmux("sac", runner=r)
        self.assertEqual(t.capture_pane("dev-1", 50), "linha1\nlinha2\n")
        self.assertEqual(r.calls[0], ("tmux", "capture-pane", "-p", "-t", "sac:dev-1", "-S", "-50"))

    def test_has_window(self):
        r = FakeRunner(outputs={"list-windows": "leader\ndev-1\n"})
        t = Tmux("sac", runner=r)
        self.assertTrue(t.has_window("dev-1"))
        self.assertFalse(t.has_window("fantasma"))

    def test_kill_session(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.kill_session()
        self.assertEqual(r.calls[0], ("tmux", "kill-session", "-t", "sac"))

    def test_paste_uses_load_buffer_then_paste_buffer(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.paste("dev-1", "linha1\nlinha2\n")
        self.assertEqual(r.calls[0][1], "load-buffer")
        self.assertEqual(r.calls[1], ("tmux", "paste-buffer", "-p", "-t", "sac:dev-1"))
        # O arquivo temporário foi criado e removido
        path = r.calls[0][2]
        self.assertFalse(Path(path).exists(), f"temp file {path} deve ter sido removido")


if __name__ == "__main__":
    unittest.main()
