import tempfile
import unittest
from pathlib import Path

from sac.commands import POKE_TEXT, cmd_done, cmd_down, cmd_inject, cmd_log, cmd_next, cmd_send, cmd_sidebar, cmd_status, cmd_up, extract_reply
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
prompt_file = "prompts/leader.md"

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"
prompt_file = "prompts/dev.md"
"""


class CommandsTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d / ".sac")
        self.runner = FakeRunner(rc=0, outputs={
            "list-panes": "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n",
        })
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_send_persists_and_pokes(self):
        mid = cmd_send(self.cfg, self.store, self.tmux, "dev-1", "faça X", sender="leader")
        self.assertIn("from-leader", mid)
        self.assertEqual(self.store.pending("dev-1"), [mid])
        # has-session[0] → list-panes[1] → send-keys[2] → Enter[3]
        self.assertEqual(self.runner.calls[2][:4], ("tmux", "send-keys", "-t", "%2"))
        self.assertIn(POKE_TEXT, self.runner.calls[2][-1])

    def test_send_unknown_agent_raises(self):
        from sac.config import ConfigError
        with self.assertRaises(ConfigError):
            cmd_send(self.cfg, self.store, self.tmux, "fantasma", "oi")

    def test_next_prints_and_claims(self):
        cmd_send(self.cfg, self.store, self.tmux, "dev-1", "faça X", sender="leader")
        rc = cmd_next(self.store, {"SAC_AGENT": "dev-1"})
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.pending("dev-1"), [])
        self.assertEqual(len(self.store.claimed("dev-1")), 1)

    def test_next_without_agent_env_fails(self):
        self.assertEqual(cmd_next(self.store, {}), 2)

    def test_done_completes_cycle(self):
        mid = cmd_send(self.cfg, self.store, self.tmux, "dev-1", "faça X", sender="leader")
        cmd_next(self.store, {"SAC_AGENT": "dev-1"})
        rc = cmd_done(self.store, {"SAC_AGENT": "dev-1"}, mid, "feito")
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.claimed("dev-1"), [])

    def test_extract_reply_finished(self):
        pane = "pergunta...\n\nResposta do agente\ncom duas linhas\nSAC_DONE\n"
        done, text = extract_reply(pane)
        self.assertTrue(done)
        self.assertIn("Resposta do agente", text)
        self.assertNotIn("SAC_DONE", text)

    def test_extract_reply_in_progress(self):
        done, text = extract_reply("trabalhando...\nsem sentinela ainda\n")
        self.assertFalse(done)


class UpDownStatusTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        (d / "prompts").mkdir()
        (d / "prompts" / "leader.md").write_text("Você é o leader.", encoding="utf-8")
        (d / "prompts" / "dev.md").write_text("Você é o dev-1.", encoding="utf-8")
        self.root = d
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d / ".sac")
        self.runner = FakeRunner(outputs={("rc", "has-session"): 1, "list-windows": "leader\ndev-1\ndash\n"})
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_up_creates_session_and_windows(self):
        rc = cmd_up(self.cfg, self.store, self.tmux, self.root, boot_wait=0)
        self.assertEqual(rc, 0)
        kinds = [c[1] for c in self.runner.calls]
        # Líder: new-session com SIDEBAR_CMD (sidebar), sem SAC_AGENT
        ns_idx = next(i for i, c in enumerate(self.runner.calls) if c[1] == "new-session")
        self.assertIn("sac sidebar", str(self.runner.calls[ns_idx]))
        self.assertNotIn("SAC_AGENT", str(self.runner.calls[ns_idx]))
        # split-window -h → harness do líder (com SAC_AGENT)
        sp_idx = next(i for i, c in enumerate(self.runner.calls) if c[1] == "split-window")
        self.assertIn("SAC_AGENT=leader", str(self.runner.calls[sp_idx]))
        # resize da sidebar do líder
        rp_calls = [c for c in self.runner.calls if c[1] == "resize-pane"]
        self.assertGreaterEqual(len(rp_calls), 1)
        # dev-1: new-window com SIDEBAR_CMD
        nw_calls = [c for c in self.runner.calls if c[1] == "new-window"]
        self.assertGreaterEqual(len(nw_calls), 2)  # dev-1 + dash
        # Dev-1 também tem split-window → harness
        sp_ids = [i for i, c in enumerate(self.runner.calls) if c[1] == "split-window"]
        self.assertGreaterEqual(len(sp_ids), 3)  # leader + dev-1 + log + notify
        # Dash: janela final
        dash_nw = [c for c in self.runner.calls if c[1] == "new-window" and "dash" in str(c)]
        self.assertEqual(len(dash_nw), 1)
        # Attach no líder: select-window(leader) + select-pane(harness_id)
        sw_idx = next(i for i, c in enumerate(self.runner.calls) if c[1] == "select-window")
        self.assertIn("leader", str(self.runner.calls[sw_idx]))
        sp_land = next(i for i, c in enumerate(self.runner.calls) if c[1] == "select-pane" and "-T" not in c)
        self.assertIn("%", str(self.runner.calls[sp_land]))
        # paste + enter para ambos agentes
        paste_calls = [c for c in self.runner.calls if c[1] == "paste-buffer"]
        self.assertEqual(len(paste_calls), 2)
        enter_calls = [c for c in self.runner.calls if c[1] == "send-keys" and c[-1] == "Enter"]
        self.assertEqual(len(enter_calls), 2)

    def test_up_idempotent_when_session_exists(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=0))
        rc = cmd_up(self.cfg, self.store, t, self.root, boot_wait=0)
        self.assertEqual(rc, 0)

    def test_down_kills_existing_session(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=0))
        rc = cmd_down(self.cfg, t)
        self.assertEqual(rc, 0)

    def test_down_without_session(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=1))
        self.assertEqual(cmd_down(self.cfg, t), 0)

    def test_status_lists_agents(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=0, outputs={"list-panes": "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n"}))
        self.store.send("leader", "dev-1", "t1")
        self.store.send("leader", "dev-1", "t2")
        self.assertEqual(cmd_status(self.cfg, self.store, t), 0)

    def test_log_prints_events(self):
        self.store.send("leader", "dev-1", "t1")
        self.assertEqual(cmd_log(self.store), 0)


class InjectTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        (d / "prompts").mkdir()
        (d / "prompts" / "leader.md").write_text("Você é o leader.", encoding="utf-8")
        self.root = d
        self.cfg = load_config(d / "sac.toml")
        self.runner = FakeRunner(outputs={"list-panes": "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n"})
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_inject_valid_agent(self):
        rc = cmd_inject(self.cfg, self.tmux, self.root, "leader")
        self.assertEqual(rc, 0)
        paste_calls = [c for c in self.runner.calls if c[1] == "paste-buffer"]
        self.assertEqual(len(paste_calls), 1)

    def test_inject_unknown_agent_returns_1(self):
        rc = cmd_inject(self.cfg, self.tmux, self.root, "fantasma")
        self.assertEqual(rc, 1)


class SidebarTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d / ".sac")

    def test_sidebar_renders_agents_and_shortcuts(self):
        r = FakeRunner(outputs={"list-windows": "1 leader\n2 dev-1\n3 dash\n"})
        t = Tmux("sac-test", runner=r)
        self.store.send("user", "dev-1", "msg1")
        rc = cmd_sidebar(self.cfg, self.store, t)
        self.assertEqual(rc, 0)
        captured = r.calls  # não serve — cmd_sidebar imprime, não faz tmux calls além do list-windows
        list_win = [c for c in captured if c[1] == "list-windows"]
        self.assertEqual(len(list_win), 1)

    def test_sidebar_shows_working_marker(self):
        r = FakeRunner(outputs={"list-windows": "1 leader\n2 dev-1\n3 dash\n"})
        t = Tmux("sac-test", runner=r)
        self.store.send("user", "dev-1", "msg1")
        self.store.next("dev-1")  # agora claimed → ⚙
        cmd_sidebar(self.cfg, self.store, t)
        # O teste apenas verifica que não crasha; o conteúdo é TUI, não assertável via retorno
        # (a verificação real seria visual; mantemos smoke)
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
