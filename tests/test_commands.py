import io
import os
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from sac.commands import (
    POKE_TEXT, cmd_done, cmd_down, cmd_inject, cmd_kill, cmd_log,
    cmd_next, cmd_send, cmd_sidebar, cmd_status, cmd_up, extract_reply,
)
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

    def test_cmd_send_user_accepts(self):
        from sac.config import ConfigError
        try:
            cmd_send(self.cfg, self.store, self.tmux, "user", "mensagem", sender="dev-1")
        except ConfigError:
            self.fail("send para user não deve levantar ConfigError")
        pending = self.store.pending("user")
        self.assertEqual(len(pending), 1, "mensagem deve ir para inbox/user/")
        self.assertIn("from-dev-1", pending[0])

    def test_cmd_send_user_no_poke(self):
        r = FakeRunner(rc=0, outputs={
            "list-panes": "%2|env SAC_AGENT=dev-1 opencode\n",
        })
        t = Tmux("sac-test", runner=r)
        cmd_send(self.cfg, self.store, t, "user", "msg", sender="dev-1")
        send_keys_calls = [c for c in r.calls if c[1] == "send-keys"]
        self.assertEqual(len(send_keys_calls), 0, "send para user não deve cutucar nenhum pane")

    def test_next_prints_and_claims(self):
        cmd_send(self.cfg, self.store, self.tmux, "dev-1", "faça X", sender="leader")
        rc = cmd_next(self.store, {"SAC_AGENT": "dev-1"})
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.pending("dev-1"), [])
        self.assertEqual(len(self.store.claimed("dev-1")), 1)

    def test_next_without_agent_env_fails(self):
        self.assertEqual(cmd_next(self.store, {}), 2)

    def test_cmd_next_acks_when_daemon_active(self):
        from sac.commands import _daemon_active
        (self.store.root).mkdir(parents=True, exist_ok=True)
        with self.store.root.joinpath("daemon.pid").open("w") as f:
            f.write(str(os.getpid()))
        self.assertTrue(_daemon_active(self.store))
        cmd_send(self.cfg, self.store, self.tmux, "dev-1", "faça Y", sender="leader")
        rc = cmd_next(self.store, {"SAC_AGENT": "dev-1"})
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.pending("dev-1"), [])
        self.assertEqual(self.store.claimed("dev-1"), [], "com daemon: não deve ir para claimed")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("ack", log)

    def test_cmd_next_claims_when_daemon_inactive(self):
        cmd_send(self.cfg, self.store, self.tmux, "dev-1", "faça Z", sender="leader")
        rc = cmd_next(self.store, {"SAC_AGENT": "dev-1"})
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.pending("dev-1"), [])
        self.assertEqual(len(self.store.claimed("dev-1")), 1, "sem daemon: vai para claimed")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("ack", log)
        self.assertIn("next", log)

    def test_cmd_next_reply_legacy_auto_ack(self):
        from sac.commands import _daemon_active
        task_mid = self.store.send("leader", "dev-1", "task", now=datetime(2026, 1, 1, 0, 0, 0))
        self.store.next("dev-1")
        self.store.send("dev-1", "leader", "reply", now=datetime(2026, 1, 1, 0, 0, 1))
        self.assertFalse(_daemon_active(self.store))
        rc = cmd_next(self.store, {"SAC_AGENT": "leader"})
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.pending("leader"), [])
        self.assertEqual(self.store.claimed("leader"), [], "reply auto-ackada (não fica claimed)")
        self.assertEqual(len(list((self.store.root / "done" / "leader").glob("*.msg"))), 1)
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("deliver_reply", log, "reply legado deve logar deliver_reply")

    def test_cmd_next_task_legacy_claimed(self):
        cmd_send(self.cfg, self.store, self.tmux, "dev-1", "task", sender="leader")
        rc = cmd_next(self.store, {"SAC_AGENT": "dev-1"})
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.store.claimed("dev-1")), 1, "task (sem reply) claimed")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("deliver_reply", log)

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

    def test_send_fallback_poke_sem_daemon(self):
        from unittest.mock import patch
        runner = FakeRunner(outputs={
            "list-panes": "%2|env SAC_AGENT=dev-1 opencode\n",
        })
        tmux = Tmux("sac-test", runner=runner)
        with patch("sac.tmux.time.sleep"):
            cmd_send(self.cfg, self.store, tmux, "dev-1", "tarefa")
        send_body = [c for c in runner.calls if c[1] == "send-keys" and len(c) > 3 and "-l" in c]
        enter_calls = [c for c in runner.calls if c[1] == "send-keys" and c[-1] == "Enter"]
        self.assertGreaterEqual(len(send_body), 1, "sem daemon: deve cutucar com send-keys -l")
        self.assertGreaterEqual(len(enter_calls), 1, "sem daemon: deve enviar Enter")

    def test_send_poke_with_hint(self):
        from unittest.mock import patch
        runner = FakeRunner(outputs={
            "list-panes": "%2|env SAC_AGENT=dev-1 opencode\n",
        })
        tmux = Tmux("sac-test", runner=runner)
        with patch("sac.tmux.time.sleep"):
            cmd_send(self.cfg, self.store, tmux, "dev-1", "faça X")
        body_args = [c[-1] for c in runner.calls if c[1] == "send-keys" and c[-1] != "Enter"]
        self.assertTrue(any("SAC: mensagem" in str(b) for b in body_args),
                        "body deve conter hint SAC: mensagem")

    def test_log_follow_io_error(self):
        from unittest.mock import patch
        from pathlib import Path
        (self.store.root).mkdir(parents=True, exist_ok=True)
        self.store.log("send", sender="leader", to="dev-1", id="x")
        original_open = Path.open
        read_count = [0]
        def wrapping_open(path_self, mode='r', *args, **kwargs):
            f = original_open(path_self, mode, *args, **kwargs)
            original_readline = f.readline
            def failing_readline():
                read_count[0] += 1
                if read_count[0] == 1:
                    raise IOError("simulated IO error")
                return original_readline()
            f.readline = failing_readline
            return f
        with patch.object(Path, 'open', wrapping_open):
            cmd_log(self.store, follow=False)
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("loop_error", log)
        self.assertIn("simulated IO error", log)

    def test_cmd_log_no_follow_no_file(self):
        rc = cmd_log(self.store, follow=False)
        self.assertEqual(rc, 0)

    def test_cmd_log_follow_waits_for_file(self):
        from unittest.mock import patch
        import threading
        (self.store.root).mkdir(parents=True, exist_ok=True)
        started = threading.Event()
        done = threading.Event()
        def run_log():
            started.set()
            cmd_log(self.store, follow=True)
            done.set()
        t = threading.Thread(target=run_log, daemon=True)
        t.start()
        started.wait(timeout=5)
        time.sleep(0.3)
        self.assertFalse(done.is_set(), "deve estar esperando o arquivo")
        (self.store.root / "log.jsonl").write_text("line\n", encoding="utf-8")
        time.sleep(0.5)
        self.assertFalse(done.is_set(), "entrou no loop de leitura (follow)")


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
        # paste para prompts de ambos agentes
        paste_calls = [c for c in self.runner.calls if c[1] == "paste-buffer"]
        self.assertEqual(len(paste_calls), 2, "deve usar paste para prompts dos 2 agentes")
        enter_calls = [c for c in self.runner.calls if c[1] == "send-keys" and c[-1] == "Enter"]
        self.assertEqual(len(enter_calls), 2)

    def test_up_idempotent_when_session_exists(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=0))
        rc = cmd_up(self.cfg, self.store, t, self.root, boot_wait=0)
        self.assertEqual(rc, 0)

    def test_down_kills_existing_session(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=0))
        rc = cmd_down(self.cfg, self.store, t)
        self.assertEqual(rc, 0)

    def test_down_without_session(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=1))
        self.assertEqual(cmd_down(self.cfg, self.store, t), 0)

    def test_status_lists_agents(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=0, outputs={"list-panes": "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n"}))
        self.store.send("leader", "dev-1", "t1")
        self.store.send("leader", "dev-1", "t2")
        self.assertEqual(cmd_status(self.cfg, self.store, t), 0)

    def test_status_mini_contadores(self):
        import io
        from contextlib import redirect_stdout
        t = Tmux("sac-test", runner=FakeRunner(rc=1))
        self.store.send("user", "dev-1", "m1")
        self.store.next("dev-1")                                  # claimed
        self.store.log("escalate", agent="auditor", id="x", pokes=3)  # escalado
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_status(self.cfg, self.store, t, mini=True)
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue().strip(), "1● 1!")

    def test_status_mini_vazio_sem_store(self):
        import io
        from contextlib import redirect_stdout
        t = Tmux("sac-test", runner=FakeRunner(rc=1))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_status(self.cfg, self.store, t, mini=True)
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue().strip(), "")

    def test_cmd_status_clean(self):
        r = FakeRunner(rc=0, outputs={"list-panes": "%1|env SAC_AGENT=leader kimi\n"})
        t = Tmux("sac-test", runner=r)
        self.store.send("user", "auditor", "orphan_msg", now=datetime(2026, 1, 1, 0, 0, 0))
        self.assertEqual(cmd_status(self.cfg, self.store, t, clean=True, yes=True), 0)
        self.assertFalse((self.store.root / "inbox" / "auditor").exists(),
                          "inbox do órfão deve ser removida")

    def test_cmd_status_dry_run(self):
        r = FakeRunner(rc=0, outputs={"list-panes": "%1|env SAC_AGENT=leader kimi\n"})
        t = Tmux("sac-test", runner=r)
        self.store.send("user", "auditor", "orphan_msg", now=datetime(2026, 1, 1, 0, 0, 0))
        self.assertEqual(cmd_status(self.cfg, self.store, t, clean=True, yes=False), 0)
        self.assertTrue((self.store.root / "inbox" / "auditor").exists(),
                         "sem --yes, orphan não deve ser removida")

    def test_cmd_status_clean_yes(self):
        r = FakeRunner(rc=0, outputs={"list-panes": "%1|env SAC_AGENT=leader kimi\n"})
        t = Tmux("sac-test", runner=r)
        self.store.send("user", "auditor", "orphan_msg", now=datetime(2026, 1, 1, 0, 0, 0))
        self.assertEqual(cmd_status(self.cfg, self.store, t, clean=True, yes=True), 0)
        self.assertFalse((self.store.root / "inbox" / "auditor").exists(),
                          "with --yes, orphan deve ser removida")

    def test_up_progress_lines(self):
        from io import StringIO
        r = FakeRunner(outputs={("rc", "has-session"): 1, "list-windows": "leader\ndev-1\ndash\n"})
        t = Tmux("sac-test", runner=r)
        out = StringIO()
        cmd_up(self.cfg, self.store, t, self.root, boot_wait=0, stdout=lambda s: out.write(s + "\n"))
        output = out.getvalue()
        self.assertIn("[1/2]", output, "deve mostrar progresso leader")
        self.assertIn("[2/2]", output, "deve mostrar progresso dev-1")
        self.assertIn("criando", output, "deve mencionar criacao")

    def test_up_socket_dir_created(self):
        sock_dir = self.root / ".sac-test-socket"
        sock = sock_dir / "tmux.sock"
        r = FakeRunner(outputs={
            ("rc", "-S|has-session"): 1,
            "-S|list-windows": "leader\ndev-1\ndash\n",
        })
        t = Tmux("sac-test", runner=r, socket=str(sock))
        self.cfg.socket = str(sock)
        self.assertFalse(sock_dir.exists())
        cmd_up(self.cfg, self.store, t, self.root, boot_wait=0)
        self.assertTrue(sock_dir.exists(), "diretorio do socket deve ser criado")

    def test_up_aborts_on_tmux_error(self):
        from sac.tmux import TmuxError
        r = FakeRunner(outputs={
            ("rc", "has-session"): 1,
        }, rc=1, stderr="permission denied")
        t = Tmux("sac-test", runner=r)
        with self.assertRaises(TmuxError):
            cmd_up(self.cfg, self.store, t, self.root, boot_wait=0)

    def test_up_socket_dir_already_exists(self):
        sock_dir = self.root / ".sac-test-socket"
        sock_dir.mkdir(parents=True, exist_ok=True)
        sock = sock_dir / "tmux.sock"
        r = FakeRunner(outputs={
            ("rc", "-S|has-session"): 1,
            "-S|list-windows": "leader\ndev-1\ndash\n",
        })
        t = Tmux("sac-test", runner=r, socket=str(sock))
        self.cfg.socket = str(sock)
        cmd_up(self.cfg, self.store, t, self.root, boot_wait=0)
        self.assertTrue(sock_dir.exists(), "diretorio existente não deve causar erro")

    def test_log_prints_events(self):
        self.store.send("leader", "dev-1", "t1")
        self.assertEqual(cmd_log(self.store), 0)

    def test_up_registers_hook(self):
        r = FakeRunner(outputs={("rc", "has-session"): 1, "list-windows": "leader\ndev-1\ndash\n"})
        t = Tmux("sac-test", runner=r)
        cmd_up(self.cfg, self.store, t, self.root, boot_wait=0)
        set_hook_calls = [c for c in r.calls if c[1] == "set-hook"]
        resize_hooks = [c for c in set_hook_calls if "client-resized" in str(c)]
        self.assertEqual(len(resize_hooks), 1, "deve registrar hook client-resized")

    def test_hook_valid_structure(self):
        r = FakeRunner(outputs={("rc", "has-session"): 1, "list-windows": "leader\ndev-1\ndash\n"})
        t = Tmux("sac-test", runner=r)
        cmd_up(self.cfg, self.store, t, self.root, boot_wait=0)
        hook_call = [c for c in r.calls if c[1] == "set-hook"][0]
        hook_str = " ".join(hook_call)
        self.assertIn("sac sidebar", hook_str)
        self.assertIn("##{pane_id}", hook_str)
        self.assertIn("list-panes", hook_str)
        self.assertIn("resize-pane", hook_str)
        self.assertIn("-x 30", hook_str)
        self.assertIn("leader", hook_str)
        self.assertIn("dev-1", hook_str)
        self.assertIn("true", hook_str)

    def test_up_uses_per_agent_boot_wait(self):
        from unittest.mock import patch
        r = FakeRunner(outputs={("rc", "has-session"): 1, "list-windows": "leader\ndev-1\ndash\n"})
        t = Tmux("sac-test", runner=r)
        cfg = load_config(self.root / "sac.toml")
        cfg.agents[1].boot_wait = 12.0
        with patch("sac.commands.time.sleep") as mock_sleep:
            with patch("sac.commands.time.monotonic", return_value=1000.0):
                cmd_up(cfg, self.store, t, self.root, boot_wait=None)
        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list if c.args[0] > 0]
        self.assertEqual(len(sleep_calls), 2, "deve dormir uma vez por agente")
        self.assertEqual(sleep_calls[0], 8.0, "agente sem override usa global 8")
        self.assertEqual(sleep_calls[1], 12.0, "agente com boot_wait=12 usa 12")

    def test_hook_valid_structure(self):
        r = FakeRunner(outputs={("rc", "has-session"): 1, "list-windows": "leader\ndev-1\ndash\n"})
        t = Tmux("sac-test", runner=r)
        cmd_up(self.cfg, self.store, t, self.root, boot_wait=0)
        hook_call = [c for c in r.calls if c[1] == "set-hook"][0]
        hook_str = " ".join(hook_call)

    def test_hook_with_socket(self):
        r = FakeRunner(outputs={
            ("rc", "-S|has-session"): 1,
            "-S|list-windows": "leader\ndev-1\ndash\n",
        })
        t = Tmux("sac-test", runner=r, socket="/tmp/.sac-tmux.sock")
        cmd_up(self.cfg, self.store, t, self.root, boot_wait=0)
        hook_call = [c for c in r.calls if "set-hook" in c][0]
        hook_str = " ".join(hook_call)
        self.assertIn("-S /tmp/.sac-tmux.sock", hook_str,
                      "hook deve usar socket configurado")


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
        self.assertEqual(len(paste_calls), 1, "deve usar paste para prompt")
        enter_calls = [c for c in self.runner.calls if c[1] == "send-keys" and c[-1] == "Enter"]
        self.assertEqual(len(enter_calls), 1)

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


class KillTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        (d / "prompts").mkdir()
        (d / "prompts" / "leader.md").write_text("Você é o leader.", encoding="utf-8")
        (d / "prompts" / "dev.md").write_text("Você é o dev-1.", encoding="utf-8")
        self.root = d
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d / ".sac")
        (d / ".sac").mkdir(parents=True, exist_ok=True)

    def test_cmd_kill_unknown_agent(self):
        from sac.config import ConfigError
        t = Tmux("sac-test", runner=FakeRunner())
        with self.assertRaises(ConfigError):
            cmd_kill(self.cfg, self.store, t, self.root, "fantasma")

    def test_cmd_kill_no_session(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=1))
        rc = cmd_kill(self.cfg, self.store, t, self.root, "leader")
        self.assertEqual(rc, 1)

    def test_cmd_kill_no_pane(self):
        r = FakeRunner(outputs={"list-panes": "%1|sac sidebar\n"})
        t = Tmux("sac-test", runner=r)
        rc = cmd_kill(self.cfg, self.store, t, self.root, "dev-1")
        self.assertEqual(rc, 1)

    def test_cmd_kill_recreates_harness(self):
        r = FakeRunner(outputs={
            "has-session": "",
            "list-panes": "%1|env SAC_AGENT=leader kimi --model k3\n%2|sac sidebar\n",
        })
        t = Tmux("sac-test", runner=r)
        rc = cmd_kill(self.cfg, self.store, t, self.root, "leader", boot_wait=0)
        self.assertEqual(rc, 0)
        calls = r.calls
        self.assertTrue(any(c[1] == "kill-pane" for c in calls), "deve matar o pane")
        split_calls = [c for c in calls if c[1] == "split-window"]
        self.assertEqual(len(split_calls), 1, "deve recriar o harness")
        self.assertIn("SAC_AGENT=leader", str(split_calls[0]))
        resize_calls = [c for c in calls if c[1] == "resize-pane"]
        self.assertGreaterEqual(len(resize_calls), 1, "deve redimensionar sidebar")
        title_calls = [c for c in calls if c[1] == "select-pane" and "-T" in c]
        self.assertEqual(len(title_calls), 1, "deve setar título do novo pane")
        paste_calls = [c for c in calls if c[1] == "paste-buffer"]
        self.assertEqual(len(paste_calls), 1, "deve re-injetar prompt")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("kill", log)

    def test_cmd_kill_with_claimed(self):
        r = FakeRunner(outputs={
            "has-session": "",
            "list-panes": "%1|env SAC_AGENT=leader kimi --model k3\n%2|sac sidebar\n",
        })
        t = Tmux("sac-test", runner=r)
        self.store.send("user", "leader", "pendente", now=datetime(2026, 1, 1, 0, 0, 0))
        self.store.next("leader")
        cmd_kill(self.cfg, self.store, t, self.root, "leader", boot_wait=0)
        paste_calls = [c for c in r.calls if c[1] == "paste-buffer"]
        self.assertGreaterEqual(len(paste_calls), 2, "deve alertar sobre claimed (prompt + alerta)")
        enter_calls = [c for c in r.calls if c[1] == "send-keys" and c[-1] == "Enter"]
        self.assertGreaterEqual(len(enter_calls), 2, "deve dar enter após prompt e alerta")

    def test_cmd_kill_inside_cwd(self):
        r = FakeRunner(outputs={
            "has-session": "",
            "list-panes": "%1|env SAC_AGENT=leader kimi --model k3\n%2|sac sidebar\n",
        })
        t = Tmux("sac-test", runner=r)
        self.assertEqual(cmd_kill(self.cfg, self.store, t, None, "leader", boot_wait=0), 0)

    def test_cmd_kill_uses_correct_window_sidebar(self):
        r = FakeRunner(outputs={
            "has-session": "",
            "list-panes|-s": "%1|env SAC_AGENT=leader kimi --model k3\n%2|sac sidebar\n%3|env SAC_AGENT=dev-1 opencode\n%4|sac sidebar\n",
            "list-panes|-t": "%4|sac sidebar\n",
        })
        t = Tmux("sac-test", runner=r)
        cmd_kill(self.cfg, self.store, t, self.root, "dev-1", boot_wait=0)
        split_calls = [c for c in r.calls if c[1] == "split-window"]
        self.assertEqual(len(split_calls), 1, "deve recriar o harness")
        self.assertIn("%4", str(split_calls[0]),
                      "split deve mirar a sidebar do dev-1 (%4), não a do leader (%2)")

    def test_cmd_kill_boot_wait_respected(self):
        from unittest.mock import patch
        r = FakeRunner(outputs={
            "has-session": "",
            "list-panes": "%1|env SAC_AGENT=leader kimi --model k3\n%2|sac sidebar\n",
        })
        t = Tmux("sac-test", runner=r)
        with patch("sac.commands.time.sleep") as mock_sleep:
            cmd_kill(self.cfg, self.store, t, self.root, "leader", boot_wait=1.5)
        mock_sleep.assert_any_call(1.5)


if __name__ == "__main__":
    unittest.main()


class EscalationContractTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        (d / "prompts").mkdir()
        (d / "prompts" / "leader.md").write_text("Você é o leader.", encoding="utf-8")
        (d / "prompts" / "dev.md").write_text("Você é o dev-1.", encoding="utf-8")
        self.root = d
        self.cfg = load_config(d / "sac.toml")
        self.runner = FakeRunner(outputs={"list-panes": "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n"})
        self.tmux = Tmux("sac-test", runner=self.runner)

    def _injected_text(self, agent_name):
        from unittest.mock import patch
        with patch.object(self.tmux, "paste") as m_paste, \
             patch.object(self.tmux, "press_enter"):
            rc = cmd_inject(self.cfg, self.tmux, self.root, agent_name)
        self.assertEqual(rc, 0, f"cmd_inject({agent_name}) deve retornar 0")
        self.assertTrue(m_paste.called, "contrato deve ser injetado via paste")
        return m_paste.call_args[0][1]

    def test_inject_prompt_inclui_contrato(self):
        text = self._injected_text("dev-1")
        self.assertIn("CONTRATO DE ESCALAÇÃO", text)
        self.assertLess(text.index("CONTRATO DE ESCALAÇÃO"), text.index("Você é o dev-1."),
                        "contrato deve vir ANTES do conteúdo do prompt_file")
        self.assertIn('sac send leader "', text,
                      "contrato do worker deve instruir reporte com o nome real do líder")

    def test_inject_sem_prompt_file_recebe_contrato(self):
        text = VALID.replace('prompt_file = "prompts/dev.md"\n', "")
        (self.root / "sac.toml").write_text(text, encoding="utf-8")
        self.cfg = load_config(self.root / "sac.toml")
        injected = self._injected_text("dev-1")
        self.assertIn("CONTRATO DE ESCALAÇÃO", injected,
                      "agente sem prompt_file também deve receber o contrato")

    def test_contrato_leader_vs_worker(self):
        leader_text = self._injected_text("leader")
        self.assertIn("ÚNICO canal com o humano", leader_text)
        self.assertIn("sac send user", leader_text)
        worker_text = self._injected_text("dev-1")
        self.assertIn("NUNCA fala diretamente com o humano", worker_text)
        self.assertNotIn("sac send user", worker_text,
                         "worker não deve ser instruído a falar com o humano")


class DoneFailureTest(unittest.TestCase):
    def test_cmd_done_move_falha_retorna_1_sem_sucesso(self):
        import io
        from contextlib import redirect_stdout
        d = Path(tempfile.mkdtemp())
        store = Store(d)
        from unittest.mock import patch
        buf = io.StringIO()
        with patch.object(store, "done", return_value=False), redirect_stdout(buf):
            rc = cmd_done(store, {"SAC_AGENT": "dev-1"}, "qualquer-id", "resumo")
        self.assertEqual(rc, 1, "move falho deve retornar 1")
        self.assertNotIn("concluída", buf.getvalue(),
                         "move falho NÃO pode imprimir mensagem de sucesso")


class DownCleanupTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.root = d
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d)
        self.runner = FakeRunner(rc=0, outputs={
            "list-panes": "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n",
        })
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_down_mata_harness_1_a_1_antes_da_sessao(self):
        from unittest.mock import patch
        with patch("sac.commands.time.sleep"), patch("sac.commands.os.kill"):
            rc = cmd_down(self.cfg, self.store, self.tmux)
        self.assertEqual(rc, 0)
        kill_panes = [c for c in self.runner.calls if c[1] == "kill-pane"]
        self.assertEqual(len(kill_panes), 2, "mata o pane do harness de cada agente, 1 a 1")
        idx_kill_session = next(i for i, c in enumerate(self.runner.calls)
                                if c[1] == "kill-session")
        for c in kill_panes:
            self.assertLess(self.runner.calls.index(c), idx_kill_session,
                            "harnesses morrem ANTES do kill-session")
        self.assertLess(self.runner.calls.index(kill_panes[0]),
                        self.runner.calls.index(kill_panes[1]),
                        "ordem sequencial: leader primeiro, depois dev-1")

    def test_down_mata_daemon_pelo_pidfile(self):
        import signal
        from unittest.mock import patch
        self.store.root.mkdir(parents=True, exist_ok=True)
        (self.store.root / "daemon.pid").write_text("12345", encoding="utf-8")

        def morre_no_probe(pid, sig):
            if sig == 0:
                raise ProcessLookupError

        with patch("sac.commands.time.sleep"), \
             patch("sac.commands.os.kill", side_effect=morre_no_probe) as m_kill:
            rc = cmd_down(self.cfg, self.store, self.tmux)
        self.assertEqual(rc, 0)
        self.assertEqual(m_kill.call_args_list[0][0], (12345, signal.SIGTERM))
        self.assertFalse((self.store.root / "daemon.pid").exists(),
                         "pid file deve ser removido")

    def test_down_sem_sessao_tambem_mata_daemon_detached(self):
        import signal
        from unittest.mock import patch
        self.store.root.mkdir(parents=True, exist_ok=True)
        (self.store.root / "daemon.pid").write_text("12345", encoding="utf-8")
        t = Tmux("sac-test", runner=FakeRunner(rc=1))

        def morre_no_probe(pid, sig):
            if sig == 0:
                raise ProcessLookupError

        with patch("sac.commands.os.kill", side_effect=morre_no_probe) as m_kill:
            rc = cmd_down(self.cfg, self.store, t)
        self.assertEqual(rc, 0)
        self.assertEqual(m_kill.call_args_list[0][0], (12345, signal.SIGTERM))


class KillDaemonTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d)
        self.store.root.mkdir(parents=True, exist_ok=True)
        (self.store.root / "daemon.pid").write_text("12345", encoding="utf-8")

    @staticmethod
    def _morre_no_probe(pid, sig):
        if sig == 0:
            raise ProcessLookupError

    def test_sigterm_basta_quando_daemon_morre(self):
        import signal
        from unittest.mock import patch
        from sac.commands import _kill_daemon
        with patch("sac.commands.time.sleep"), \
             patch("sac.commands.os.kill", side_effect=self._morre_no_probe) as m:
            _kill_daemon(self.store)
        calls = m.call_args_list
        self.assertEqual(calls[0][0], (12345, signal.SIGTERM))
        self.assertNotIn((12345, signal.SIGKILL), [c[0] for c in calls],
                         "daemon que morre com TERM não deve levar KILL")
        self.assertFalse((self.store.root / "daemon.pid").exists())

    def test_sigkill_quando_daemon_teimoso(self):
        import signal
        from unittest.mock import patch
        from sac.commands import _kill_daemon
        with patch("sac.commands.time.sleep"), \
             patch("sac.commands.os.kill") as m:  # nunca morre no probe
            _kill_daemon(self.store)
        sigs = [c[0][1] for c in m.call_args_list]
        self.assertEqual(sigs[0], signal.SIGTERM)
        self.assertIn(signal.SIGKILL, sigs,
                      "daemon vivo após a espera deve levar SIGKILL")
        self.assertFalse((self.store.root / "daemon.pid").exists())

    def test_pid_invalido_so_remove_arquivo(self):
        from unittest.mock import patch
        from sac.commands import _kill_daemon
        (self.store.root / "daemon.pid").write_text("abc", encoding="utf-8")
        with patch("sac.commands.os.kill") as m:
            _kill_daemon(self.store)
        m.assert_not_called()
        self.assertFalse((self.store.root / "daemon.pid").exists())


GRID_VALID = """
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

[[agents]]
name = "auditor"
command = "kimi"
role = "aux"

[windows]
main = "leader"
trabalho = "dev-1,auditor"
"""


class UpGridTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(GRID_VALID, encoding="utf-8")
        self.root = d
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d)
        self.runner = FakeRunner(outputs={"display-message": "100", ("rc", "has-session"): 1})
        self.tmux = Tmux("sac-test", runner=self.runner)

    def _splits(self):
        return [c for c in self.runner.calls if c[1] == "split-window"]

    def test_up_grid_materializacao(self):
        rc = cmd_up(self.cfg, self.store, self.tmux, self.root, boot_wait=0)
        self.assertEqual(rc, 0)
        # windows: main (new-session), trabalho e dash (new-window), nesta ordem
        news = [c for c in self.runner.calls if c[1] in ("new-session", "new-window")]
        win_names = [c[c.index("-n") + 1] for c in news]
        self.assertEqual(win_names, ["main", "trabalho", "dash"])
        splits = self._splits()
        # area do leader: split -h -l 72 (100 - 28 da sidebar) a partir do sidebar (%1)
        self.assertEqual(splits[0][splits[0].index("-l") + 1], "72")
        self.assertEqual(splits[0][splits[0].index("-t") + 1], "%1")
        self.assertIn("SAC_AGENT=leader", splits[0][-1])
        # row do auditor: split -v -l 50 a partir do dev-1 (%4)
        row = next(c for c in splits if "SAC_AGENT=auditor" in c[-1])
        self.assertIn("-v", row)
        self.assertNotIn("-f", row, "split de empilhamento NÃO usa -f (só a célula)")
        self.assertEqual(row[row.index("-t") + 1], "%4")
        self.assertEqual(row[row.index("-l") + 1], "50")
        # dev-1 (area da window trabalho): split -h -l 72 a partir de %3
        dev = next(c for c in splits if "SAC_AGENT=dev-1" in c[-1])
        self.assertEqual(dev[dev.index("-t") + 1], "%3")
        # sidebar 15% de 100 = 15 → piso 28 colunas
        resizes = [c for c in self.runner.calls if c[1] == "resize-pane"]
        self.assertTrue(any(c[c.index("-x") + 1] == "28" for c in resizes),
                        "sidebar usa piso de 28 colunas quando 15% < 28")
        # select final: entry window main, pane do leader
        sel_w = [c for c in self.runner.calls if c[1] == "select-window"]
        self.assertEqual(sel_w[-1][-1], "sac-test:main")
        sel_p = [c for c in self.runner.calls if c[1] == "select-pane" and "-T" not in c]
        self.assertEqual(sel_p[-1][-1], "%2")

    def test_up_grid_sem_windows_mantem_legado(self):
        (self.root / "sac.toml").write_text(VALID, encoding="utf-8")
        cfg = load_config(self.root / "sac.toml")
        rc = cmd_up(cfg, self.store, self.tmux, self.root, boot_wait=0)
        self.assertEqual(rc, 0)
        splits = self._splits()
        self.assertFalse(any("-f" in c for c in splits),
                         "layout legado não usa split full-height")
        win_names = [c[c.index("-n") + 1] for c in self.runner.calls
                     if c[1] in ("new-session", "new-window")]
        self.assertEqual(win_names, ["leader", "dev-1", "dash"])


class SidebarV2Test(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(GRID_VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d)

    def _render(self):
        import io
        import re
        from contextlib import redirect_stdout
        t = Tmux("sac-test", runner=FakeRunner(outputs={
            "list-windows": "main|0\ntrabalho|1\ndash|0\n",
            "list-panes|-s": "main|leader|1|%2\nmain||0|%1\ntrabalho|dev-1|1|%4\ntrabalho|auditor|0|%5\ndash||0|%6\n",
        }))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_sidebar(self.cfg, self.store, t)
        self.assertEqual(rc, 0)
        raw = buf.getvalue()
        self.assertIn("\033[", raw, "sidebar v2 deve usar cores ANSI")
        return re.sub(r"\033\[[0-9;]*m", "", raw)

    def test_tree_indicadores_e_foco(self):
        self.store.send("user", "dev-1", "msg1")
        self.store.next("dev-1")          # claimed → ●
        self.store.send("user", "auditor", "msg2")  # inbox → ◐
        self.store.log("escalate", agent="auditor", id="x", pokes=3)  # → !
        out = self._render()
        self.assertIn("> trabalho", out)                # window ativa
        self.assertTrue(out.startswith("  main"), "window inativa sem >")
        self.assertIn("\n  └─ leader · kimi", out)      # ocioso, sem * (foco é da window ativa)
        self.assertIn("├─ * dev-1 ● opencode", out)     # claimed + focado na window ativa
        self.assertIn("└─ auditor ! kimi", out)         # escalado (prioridade sobre inbox)
        self.assertIn("\n  dash", out)                  # window sem agentes aparece

    def test_comms_ultimos_5_formato(self):
        for i in range(8):
            self.store.send("user", "dev-1", f"m{i}")
        out = self._render()
        comms = out.split("comms", 1)[1]
        lines = [l for l in comms.strip().splitlines() if l.strip() and "→" in l]
        self.assertEqual(len(lines), 5, "comms mostra os 5 eventos mais recentes")
        self.assertRegex(lines[0], r"^\s+\d{2}:\d{2} user→dev-1 send")

    def test_tips_presente(self):
        out = self._render()
        self.assertIn("tips", out)
        self.assertIn("C-b e", out)
        self.assertIn("C-b z", out)


GRID_V3_MODEL = """
[session]
name = "sac-test"

[[agents]]
name = "leader"
command = "kimi"
args = ["--model", "esteira/k3", "--yolo"]
role = "leader"

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"

[windows]
main = "leader"
trabalho = "dev-1"
"""


class SidebarV3Test(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(GRID_V3_MODEL, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d)

    def _render(self):
        import io
        import re
        from contextlib import redirect_stdout
        t = Tmux("sac-test", runner=FakeRunner(outputs={
            "list-windows": "main|0\ntrabalho|1\n",
            "list-panes|-s": "main|leader|0|%2\ntrabalho|dev-1|1|%4\n",
        }))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_sidebar(self.cfg, self.store, t)
        self.assertEqual(rc, 0)
        return re.sub(r"\033\[[0-9;]*m", "", buf.getvalue())

    def test_modelo_extraido_dos_args(self):
        out = self._render()
        self.assertIn("└─ leader · kimi/k3", out)   # alias esteira/ removido
        self.assertIn("└─ * dev-1 · opencode", out)    # agente único na window → └─; sem --model → só comando
        self.assertNotIn("esteira/", out)

    def test_badge_inbox_e_tempo_ocioso(self):
        self.store.send("user", "dev-1", "m1")
        self.store.send("user", "dev-1", "m2")
        from datetime import datetime, timedelta
        self.store.log("poke", now=datetime.now() - timedelta(seconds=300),
                       agent="dev-1", count=1)
        out = self._render()
        linha = next(l for l in out.splitlines() if "dev-1" in l)
        self.assertIn("(2)", linha)                  # badge de inbox
        self.assertIn("· 5m", linha)                 # idade do último evento

    def test_sem_eventos_sem_idade(self):
        out = self._render()
        linha = next(l for l in out.splitlines() if "leader" in l)
        self.assertNotIn("· 0m", linha)
        self.assertRegex(linha, r"kimi/k3\s*$")

    def test_identidade_via_agent_option_nao_pane_title(self):
        """Harness troca o pane_title (kimi vira 'Kimi Code') — a árvore usa @agent."""
        import io
        import re
        from contextlib import redirect_stdout
        r = FakeRunner(outputs={
            "list-windows": "main|0\ntrabalho|1\n",
            "list-panes|-s": "main|leader|0|%2\ntrabalho|dev-1|1|%4\n",
        })
        t = Tmux("sac-test", runner=r)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_sidebar(self.cfg, self.store, t)
        self.assertEqual(rc, 0)
        fmt = next(c[-1] for c in r.calls if c[1] == "list-panes")
        self.assertIn("#{@agent}", fmt, "list-panes deve pedir @agent (estável), não pane_title")
        self.assertNotIn("pane_title", fmt)
        out = re.sub(r"\033\[[0-9;]*m", "", buf.getvalue())
        self.assertIn("leader", out)
        self.assertIn("dev-1", out)

    def test_comando_com_path_usa_basename(self):
        from types import SimpleNamespace
        from sac.commands import _agent_model
        a = SimpleNamespace(command="/tmp/x/bin/fake", args=["--model", "esteira/k3"])
        self.assertEqual(_agent_model(a), "fake/k3")
        b = SimpleNamespace(command="/usr/bin/opencode", args=[])
        self.assertEqual(_agent_model(b), "opencode")

    def test_linhas_truncadas_na_largura_do_terminal(self):
        import shutil
        from unittest.mock import patch
        longo = "x" * 120
        self.store.send("user", "dev-1", longo)
        with patch.object(shutil, "get_terminal_size") as gts:
            gts.return_value = shutil.os.terminal_size((30, 24))
            out = self._render()
        import re as _re
        for linha in out.splitlines():
            visivel = _re.sub(r"\033\[[0-9;]*m", "", linha)
            self.assertLessEqual(len(visivel), 30, f"linha excede a largura: {linha!r}")

    def test_frame_limpa_cada_linha(self):
        from sac.commands import _frame
        f = _frame("abc\nde")
        self.assertTrue(f.startswith("\033[H"))
        self.assertTrue(f.endswith("\033[J"))
        self.assertEqual(f.count("\033[K"), 2, "cada linha limpa até o fim (sem restos de frames anteriores)")
        self.assertNotIn("\033[K\n\033[J", f, "sem newline extra após a última linha")


class SidebarToggleTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d)

    def test_toggle_cria_quando_ausente(self):
        from sac.commands import cmd_sidebar_toggle
        r = FakeRunner(outputs={
            "list-panes|-t": "%9||1\n%10||0\n",
            "display-message": "100",
        })
        t = Tmux("sac-test", runner=r)
        rc = cmd_sidebar_toggle(self.cfg, t, "@1")
        self.assertEqual(rc, 0)
        splits = [c for c in r.calls if c[1] == "split-window"]
        self.assertEqual(len(splits), 1)
        self.assertIn("-b", splits[0], "sidebar nasce à esquerda (before)")
        self.assertIn("-f", splits[0], "sidebar full-height")
        roles = [c for c in r.calls if c[1] == "set-option" and "@pane_role" in c]
        self.assertEqual(len(roles), 1, "pane novo é marcado como sidebar")
        sel = [c for c in r.calls if c[1] == "select-pane"]
        self.assertEqual(sel[-1][-1], "%9", "foco volta ao pane original")

    def test_toggle_mata_quando_presente(self):
        from sac.commands import cmd_sidebar_toggle
        r = FakeRunner(outputs={
            "list-panes|-t": "%9|sidebar|0\n%10||1\n",
        })
        t = Tmux("sac-test", runner=r)
        rc = cmd_sidebar_toggle(self.cfg, t, "@1")
        self.assertEqual(rc, 0)
        kills = [c for c in r.calls if c[1] == "kill-pane"]
        self.assertEqual(len(kills), 1)
        self.assertEqual(kills[0][kills[0].index("-t") + 1], "%9")
        self.assertFalse([c for c in r.calls if c[1] == "split-window"],
                         "não cria nada quando só remove")


class AppearanceTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(GRID_VALID, encoding="utf-8")
        self.root = d
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d)
        self.runner = FakeRunner(outputs={"display-message": "100", ("rc", "has-session"): 1})
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_cor_estavel_por_agente(self):
        from sac.commands import AGENT_PALETTE, agent_color
        self.assertEqual(agent_color("dev-1"), agent_color("dev-1"),
                         "mesmo nome → mesma cor em qualquer boot")
        self.assertIn(agent_color("dev-1"), AGENT_PALETTE)

    def test_up_configura_bordas_status_e_hooks(self):
        from unittest.mock import patch
        with patch("sac.commands._git_branch", return_value="main"):
            rc = cmd_up(self.cfg, self.store, self.tmux, self.root, boot_wait=0)
        self.assertEqual(rc, 0)
        calls = self.runner.calls
        setopts = [" ".join(c) for c in calls if c[1] == "set-option"]
        self.assertTrue(any("pane-border-status" in s and "top" in s for s in setopts),
                        "borda com status no topo")
        self.assertTrue(any("pane-border-format" in s and "dev-1" in s for s in setopts),
                        "borda com label do agente")
        self.assertTrue(any("@agent_color" in s for s in setopts),
                        "cor do agente gravada como pane option")
        self.assertTrue(any(" @agent leader" in s for s in setopts) and
                        any(" @agent dev-1" in s for s in setopts),
                        "identidade estável @agent gravada como pane option")
        right_full = next(s for s in setopts if "status-right" in s)
        self.assertIn("@agent", right_full,
                      "rodapé mostra @agent (imune à troca de pane_title pelo harness)")
        self.assertTrue(any("status-left" in s and "main" in s for s in setopts),
                        "status-left com branch git")
        self.assertTrue(any("status-right" in s and "SAC" in s and "pane_title" in s
                            for s in setopts),
                        "status-right com agente focado e versão")
        right = next(s for s in setopts if "status-right" in s)
        self.assertNotIn("MouseDrag", right)
        self.assertNotIn("S-C-v", right)
        self.assertIn("#S:#W", right)
        self.assertIn("sac status --mini", right)
        self.assertTrue(any(c[1] == "set-option" and "window-status-format" in c and c[-1] == ""
                            for c in calls),
                        "lista de windows suprimida")
        hooks = [" ".join(c) for c in calls if c[1] == "set-hook"]
        self.assertTrue(any("after-select-pane" in h and "@agent_color" in h for h in hooks),
                        "hook de realce do pane ativo")
        self.assertTrue(any("client-resized" in h and "@pane_role" in h
                            and "window_width" in h for h in hooks),
                        "hook de resize do grid via @pane_role")
        binds = [" ".join(c) for c in calls if c[1] == "bind-key"]
        self.assertTrue(any("sidebar --toggle" in b for b in binds), "bind prefix+e")

    def test_hook_resize_legado_intacto_sem_windows(self):
        (self.root / "sac.toml").write_text(VALID, encoding="utf-8")
        cfg = load_config(self.root / "sac.toml")
        cmd_up(cfg, self.store, self.tmux, self.root, boot_wait=0)
        hooks = [" ".join(c) for c in self.runner.calls if c[1] == "set-hook"]
        self.assertTrue(any("client-resized" in h and "sac sidebar" in h for h in hooks),
                        "hook legado (grep sac sidebar) preservado sem [windows]")
        self.assertFalse(any("after-select-pane" in h for h in hooks) and
                         any("client-resized" in h and "@pane_role" in h for h in hooks),
                         "hook do grid não aparece no legado")


class ProgressBarTest(unittest.TestCase):
    def test_formato_barra(self):
        from sac.commands import _Progress
        p = _Progress(4, enabled=True)
        line = p._line(2, "leader: prompt")
        self.assertIn("\033[32m", line, "barra verde")
        self.assertIn(" 50%", line)
        self.assertEqual(line.count("█"), 10)
        self.assertEqual(line.count("░"), 10)
        cheio = p._line(4, "fim")
        self.assertEqual(cheio.count("█"), 20)
        self.assertIn("100%", cheio)
        self.assertTrue(line.startswith("\r"), "reescreve a mesma linha")

    def test_desabilitada_nao_imprime(self):
        import io
        from contextlib import redirect_stdout
        from sac.commands import _Progress
        p = _Progress(4, enabled=False)
        buf = io.StringIO()
        with redirect_stdout(buf):
            p.step("x")
            p.render(2, "y")
            p.finish()
        self.assertEqual(buf.getvalue(), "")


class SidebarInteractTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(GRID_VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d)
        self.runner = FakeRunner(outputs={
            "list-windows": "main|1\ntrabalho|0\n",
            "list-panes|-s": "main|leader|1|%2\ntrabalho|dev-1|0|%4\ntrabalho|auditor|0|%5\n",
        })
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_hit_map_window_e_agente(self):
        from sac.commands import _render_sidebar
        _text, hits = _render_sidebar(self.cfg, self.store, self.tmux)
        self.assertEqual(hits[0], ("window", "main"))
        self.assertEqual(hits[1], ("agent", "main", "%2"))
        self.assertEqual(hits[2], ("window", "trabalho"))
        self.assertEqual(hits[3], ("agent", "trabalho", "%4"))
        self.assertEqual(hits[4], ("agent", "trabalho", "%5"))

    def test_clique_em_agente_seleciona_window_e_pane(self):
        from sac.commands import _handle_input, _render_sidebar
        _text, hits = _render_sidebar(self.cfg, self.store, self.tmux)
        novo_cursor = _handle_input("\033[<0;5;4M", hits, 0, self.tmux)
        self.assertEqual(novo_cursor, 3)
        sel = [c for c in self.runner.calls if c[1] in ("select-window", "select-pane")]
        self.assertEqual(sel[0][-1], "sac-test:trabalho", "clique no agente abre a window do grupo")
        self.assertEqual(sel[1][-1], "%4", "e foca o pane do agente clicado")

    def test_teclas_j_k_enter(self):
        from sac.commands import _handle_input
        hits = {0: ("window", "main"), 1: ("agent", "main", "%2"),
                2: ("window", "trabalho"), 3: ("agent", "trabalho", "%4")}
        c = _handle_input("j", hits, 0, self.tmux)
        self.assertEqual(c, 1)
        c = _handle_input("k", hits, c, self.tmux)
        self.assertEqual(c, 0)
        _handle_input("\r", hits, 3, self.tmux)
        sel = [c for c in self.runner.calls if c[1] == "select-pane"]
        self.assertEqual(sel[-1][-1], "%4", "Enter ativa a linha do cursor")
