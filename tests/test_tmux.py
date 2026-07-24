import subprocess
import unittest
from pathlib import Path

from sac.tmux import Tmux


class FakeRunner:
    def __init__(self, outputs=None, rc=0):
        self.calls = []
        self.outputs = outputs or {}
        self.rc = rc
        self._seq = 0

    def __call__(self, *args):
        self.calls.append(args)
        key = args[1] if len(args) > 1 else ""
        sub_key = f"{key}|{args[2]}" if len(args) > 2 and key == "list-panes" else None
        out = self.outputs.get(key, "")
        if sub_key and not out:
            out = self.outputs.get(sub_key, "")
        if not out and "#{pane_id}" in str(args):
            self._seq += 1
            out = f"%{self._seq}"
        rc = self.outputs.get(("rc", key), self.rc)
        return subprocess.CompletedProcess(args, rc, stdout=out, stderr="")


class TmuxTest(unittest.TestCase):
    def test_has_session_true(self):
        t = Tmux("sac", runner=FakeRunner(rc=0))
        self.assertTrue(t.has_session())

    def test_has_session_false(self):
        t = Tmux("sac", runner=FakeRunner(rc=1))
        self.assertFalse(t.has_session())

    def test_new_session_returns_pane_id(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        pid = t.new_session("leader", ["kimi", "--model", "k3"])
        self.assertEqual(pid, "%1")
        self.assertEqual(r.calls[0],
            ("tmux", "new-session", "-d", "-s", "sac", "-n", "leader", "-P", "-F", "#{pane_id}", "kimi --model k3"))

    def test_new_session_with_env_prefix(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.new_session("leader", ["kimi", "--model", "k3"], env={"SAC_AGENT": "leader"})
        self.assertEqual(
            r.calls[0],
            ("tmux", "new-session", "-d", "-s", "sac", "-n", "leader", "-P", "-F", "#{pane_id}", "env SAC_AGENT=leader kimi --model k3"),
        )

    def test_new_window_returns_pane_id(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        pid = t.new_window("dev-1", ["opencode", "-m", "x/y"], env={"SAC_AGENT": "dev-1"})
        self.assertEqual(pid, "%1")
        self.assertEqual(
            r.calls[0],
            ("tmux", "new-window", "-t", "sac", "-n", "dev-1", "-P", "-F", "#{pane_id}", "env SAC_AGENT=dev-1 opencode -m x/y"),
        )

    def test_send_keys_with_session_prefix(self):
        from unittest.mock import patch
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        with patch("sac.tmux.time.sleep") as mock_sleep:
            t.send_keys("dev-1", "SAC: mensagem nova — rode `sac next`")
        self.assertEqual(r.calls[0], ("tmux", "send-keys", "-t", "sac:dev-1", "-l", "--", "SAC: mensagem nova — rode `sac next`"))
        self.assertEqual(r.calls[1], ("tmux", "send-keys", "-t", "sac:dev-1", "Enter"))
        mock_sleep.assert_called_once_with(0.5)

    def test_send_keys_with_pane_id_passes_raw(self):
        from unittest.mock import patch
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        with patch("sac.tmux.time.sleep"):
            t.send_keys("%1", "msg")
        self.assertEqual(r.calls[0], ("tmux", "send-keys", "-t", "%1", "-l", "--", "msg"))

    def test_send_keys_sleeps_between_text_and_enter(self):
        from unittest.mock import patch
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        with patch("sac.tmux.time.sleep") as mock_sleep:
            t.send_keys("%1", "ping")
        self.assertEqual(len(r.calls), 2)
        self.assertEqual(r.calls[0][-1], "ping")
        self.assertEqual(r.calls[1][-1], "Enter")
        mock_sleep.assert_called_once_with(0.5)

    def test_capture_pane(self):
        r = FakeRunner(outputs={"capture-pane": "linha1\nlinha2\n"})
        t = Tmux("sac", runner=r)
        self.assertEqual(t.capture_pane("dev-1", 50), "linha1\nlinha2\n")
        self.assertEqual(r.calls[0], ("tmux", "capture-pane", "-p", "-t", "sac:dev-1", "-S", "-50"))

    def test_capture_pane_with_pane_id_passes_raw(self):
        r = FakeRunner(outputs={"capture-pane": "conteudo\n"})
        t = Tmux("sac", runner=r)
        self.assertEqual(t.capture_pane("%2", 50), "conteudo\n")
        self.assertEqual(r.calls[0], ("tmux", "capture-pane", "-p", "-t", "%2", "-S", "-50"))

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

    def test_paste_with_window_prefixes_session(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.paste("dev-1", "linha1\nlinha2\n")
        self.assertEqual(r.calls[0][1], "load-buffer")
        self.assertEqual(r.calls[1], ("tmux", "paste-buffer", "-p", "-t", "sac:dev-1"))
        path = r.calls[0][2]
        self.assertFalse(Path(path).exists(), f"temp file {path} deve ter sido removido")

    def test_paste_with_pane_id_passes_raw(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.paste("%5", "texto")
        self.assertEqual(r.calls[1], ("tmux", "paste-buffer", "-p", "-t", "%5"))

    def test_press_enter_with_window(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.press_enter("dev-1")
        self.assertEqual(r.calls[0], ("tmux", "send-keys", "-t", "sac:dev-1", "Enter"))

    def test_press_enter_with_pane_id(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.press_enter("%1")
        self.assertEqual(r.calls[0], ("tmux", "send-keys", "-t", "%1", "Enter"))


if __name__ == "__main__":
    unittest.main()


class TmuxSocketTest(unittest.TestCase):
    def test_socket_prefixes_all_commands(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r, socket="/home/dev/.sac/tmux.sock")
        t.has_session()
        t.send_keys("dev-1", "oi")
        self.assertEqual(r.calls[0][:4], ("tmux", "-S", "/home/dev/.sac/tmux.sock", "has-session"))
        self.assertEqual(r.calls[1][:3], ("tmux", "-S", "/home/dev/.sac/tmux.sock"))


class TmuxSplitTest(unittest.TestCase):
    def test_split_window_returns_pane_id(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        pid = t.split_window("agents", ["sac", "log", "-f"])
        self.assertEqual(pid, "%1")
        self.assertEqual(r.calls[0],
            ("tmux", "split-window", "-t", "sac:agents", "-h", "-P", "-F", "#{pane_id}", "sac log -f"))

    def test_split_window_vertical(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        pid = t.split_window("%1", ["sac", "notify"], vertical=True)
        self.assertEqual(pid, "%1")
        self.assertEqual(r.calls[0],
            ("tmux", "split-window", "-t", "%1", "-v", "-P", "-F", "#{pane_id}", "sac notify"))

    def test_split_window_with_env_prefix(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.split_window("agents", ["opencode", "-m", "x/y"], env={"SAC_AGENT": "dev-1"})
        self.assertEqual(
            r.calls[0],
            ("tmux", "split-window", "-t", "sac:agents", "-h", "-P", "-F", "#{pane_id}", "env SAC_AGENT=dev-1 opencode -m x/y"),
        )

    def test_split_quotes_compound_command(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.split_window("dash.0", ["sh", "-c", "while true; do clear; done"])
        self.assertIn("'while true; do clear; done'", r.calls[0][-1])

    def test_resize_pane_with_id(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.resize_pane("%10", 34)
        self.assertEqual(r.calls[0], ("tmux", "resize-pane", "-t", "%10", "-x", "34"))

    def test_select_layout(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.select_layout("agents", "tiled")
        self.assertEqual(r.calls[0], ("tmux", "select-layout", "-t", "sac:agents", "tiled"))

    def test_select_window(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.select_window("agents")
        self.assertEqual(r.calls[0], ("tmux", "select-window", "-t", "sac:agents"))

    def test_select_pane_with_id(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.select_pane("%1")
        self.assertEqual(r.calls[0], ("tmux", "select-pane", "-t", "%1"))

    def test_set_pane_title(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.set_pane_title("%1", "dev-1")
        self.assertEqual(r.calls[0], ("tmux", "select-pane", "-t", "%1", "-T", "dev-1"))

    def test_kill_pane(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.kill_pane("%2")
        self.assertEqual(r.calls[0], ("tmux", "kill-pane", "-t", "%2"))

    def test_kill_pane_unknown(self):
        r = FakeRunner(rc=1)
        t = Tmux("sac", runner=r)
        t.kill_pane("fantasma")
        self.assertEqual(r.calls[0], ("tmux", "kill-pane", "-t", "sac:fantasma"))

    def test_find_pane_by_command(self):
        r = FakeRunner(outputs={
            "list-panes|-s": "%1|env SAC_AGENT=leader kimi\n%2|sac sidebar\n%3|env SAC_AGENT=dev-1 opencode\n%4|sac sidebar\n",
        })
        t = Tmux("sac", runner=r)
        self.assertEqual(t.find_pane_by_command("sac sidebar"), "%2",
                         "sem window, retorna primeiro da sessao")

    def test_find_pane_by_command_window_scoped(self):
        r = FakeRunner(outputs={
            "list-panes|-t": "%4|sac sidebar\n",
        })
        t = Tmux("sac", runner=r)
        self.assertEqual(t.find_pane_by_command("sac sidebar", window="dev-1"), "%4")
        call = r.calls[0]
        self.assertIn("-t", call, "deve usar -t (target window)")
        self.assertIn("sac:dev-1", call, "deve mirar janela dev-1")

    def test_find_pane_id_by_start_command(self):
        r = FakeRunner(outputs={
            "list-panes": "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n"
        })
        t = Tmux("sac", runner=r)
        self.assertTrue(t.has_pane("dev-1"))
        self.assertFalse(t.has_pane("fantasma"))
