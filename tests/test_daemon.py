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

    def test_deliver_next_uses_send_keys_with_hint(self):
        from sac.daemon import Daemon
        from unittest.mock import patch
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%2|env SAC_AGENT=dev-1 opencode\n"
        d = Daemon(self.cfg, self.store, tmux)
        mid = self.store.send("user", "dev-1", "execute task X")
        with patch("sac.tmux.time.sleep"):
            d._deliver_next("dev-1")
        send_body = [c for c in runner.calls if c[1] == "send-keys" and len(c) > 3 and "-l" in c]
        self.assertEqual(len(send_body), 1, "deve usar send-keys -l")
        enter_calls = [c for c in runner.calls if c[1] == "send-keys" and c[-1] == "Enter"]
        self.assertEqual(len(enter_calls), 1, "deve dar enter separado")
        self.assertIn("SAC: mensagem", str(send_body[0]),
                      "body deve conter hint")
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
        send_body = [c for c in runner.calls if c[1] == "send-keys" and len(c) > 3 and "-l" in c]
        self.assertEqual(len(send_body), 0, "sem pendentes, sem send-keys")

    def test_process_agent_delivers_pending(self):
        from sac.daemon import Daemon
        from unittest.mock import patch
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%2|env SAC_AGENT=dev-1 opencode\n"
        d = Daemon(self.cfg, self.store, tmux)
        self.store.send("user", "dev-1", "new task")
        with patch("sac.tmux.time.sleep"):
            d._process_agent("dev-1")
        send_body = [c for c in runner.calls if c[1] == "send-keys" and len(c) > 3 and "-l" in c]
        self.assertEqual(len(send_body), 1, "deve entregar pendente via send-keys")

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

    def test_process_agent_lider_sem_poke_stale(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%1|env SAC_AGENT=leader kimi\n"
        d = Daemon(self.cfg, self.store, tmux)
        old = datetime.now() - timedelta(seconds=300)
        self.store.send("user", "leader", "old task", now=old)
        self.store.next("leader")
        d._process_agent("leader")
        stale_calls = [c for c in runner.calls if "pendente" in str(c)]
        self.assertEqual(stale_calls, [], "líder NÃO deve ser re-cutucado")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertNotIn('"poke"', log, "nenhum evento poke para o líder")

    def test_process_agent_lider_claimed_ainda_entrega_reply(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n"
        d = Daemon(self.cfg, self.store, tmux)
        old = datetime.now() - timedelta(seconds=300)
        self.store.send("user", "leader", "old task", now=old)
        self.store.next("leader")
        self.store.send("leader", "dev-1", "faça X", now=datetime.now())
        self.store.next("dev-1")
        self.store.send("dev-1", "leader", "pronto", now=datetime.now())
        d._process_agent("leader")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("deliver_reply", log, "reply do worker deve furar a fila do líder")
        stale_calls = [c for c in runner.calls if "pendente" in str(c)]
        self.assertEqual(stale_calls, [], "sem poke de stale no líder")

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

    def test_daemon_deliver_reply(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%1|env SAC_AGENT=leader kimi\n"
        d = Daemon(self.cfg, self.store, tmux)
        task_mid = self.store.send("leader", "dev-1", "faça X", now=datetime.now())
        self.store.next("dev-1")
        self.store.send("dev-1", "leader", "pronto", now=datetime.now())
        d._deliver_next("leader")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("deliver_reply", log)
        self.assertEqual(len(self.store.claimed("leader")), 0, "reply auto-ackada")

    def test_daemon_deliver_task_no_reply(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%2|env SAC_AGENT=dev-1 opencode\n"
        d = Daemon(self.cfg, self.store, tmux)
        self.store.send("leader", "dev-1", "task", now=datetime.now())
        d._deliver_next("dev-1")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("deliver", log)
        self.assertNotIn("deliver_reply", log)
        self.assertEqual(len(self.store.claimed("dev-1")), 1,
                         "tarefa sem reply_to permanece em claimed")

    def test_daemon_delivers_reply_with_claimed(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%1|env SAC_AGENT=leader kimi\n"
        d = Daemon(self.cfg, self.store, tmux)
        self.store.send("leader", "dev-1", "existing task", now=datetime.now())
        self.store.next("dev-1")
        self.store.send("dev-1", "leader", "reply", now=datetime.now())
        d._process_agent("leader")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("deliver_reply", log,
                      "reply deve ser entregue mesmo com claimed em andamento")

    def test_daemon_skips_task_with_claimed(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%2|env SAC_AGENT=dev-1 opencode\n"
        d = Daemon(self.cfg, self.store, tmux)
        self.store.send("leader", "dev-1", "old task", now=datetime.now() - timedelta(seconds=300))
        self.store.next("dev-1")
        self.store.send("user", "dev-1", "new task", now=datetime.now())
        d._process_agent("dev-1")
        deliveries = [c for c in runner.calls if c[1] == "paste-buffer"]
        self.assertEqual(len(deliveries), 0,
                         "tarefa sem reply não deve furar fila com claimed pendente")

    def test_daemon_delivers_reply_even_when_throttled(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%1|env SAC_AGENT=leader kimi\n"
        d = Daemon(self.cfg, self.store, tmux)
        self.store.send("user", "leader", "old task", now=datetime.now() - timedelta(seconds=1000))
        self.store.next("leader")
        mid = self.store.claimed("leader")[0]
        d._poke_state.setdefault("leader", {})[mid] = time.monotonic()
        d._poke_count.setdefault("leader", {})[mid] = 10
        self.store.send("leader", "dev-1", "dummy", now=datetime.now() - timedelta(seconds=100))
        self.store.next("dev-1")
        self.store.send("dev-1", "leader", "reply", now=datetime.now())
        d._process_agent("leader")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("deliver", log,
                      "reply deve ser entregue mesmo com throttled")

    def test_daemon_backoff_doubles_interval(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%2|env SAC_AGENT=dev-1 opencode\n"
        d = Daemon(self.cfg, self.store, tmux)
        old = datetime.now() - timedelta(seconds=1000)
        self.store.send("user", "dev-1", "old task", now=old)
        self.store.next("dev-1")
        mid = self.store.claimed("dev-1")[0]
        interval_before = d._poke_interval(mid)
        self.assertEqual(interval_before, 0.0, "sem pokes: intervalo zero (poke imediato)")
        d._poke_state.setdefault("dev-1", {})[mid] = time.monotonic()
        d._poke_count.setdefault("dev-1", {})[mid] = 1
        interval_after = d._poke_interval(mid)
        self.assertEqual(interval_after, 240.0, "1 poke: base 120 * 2**1 = 240")
        d._poke_count["dev-1"][mid] = 2
        interval_third = d._poke_interval(mid)
        self.assertEqual(interval_third, 480.0, "2 pokes: base 120 * 2**2 = 480")

    def test_daemon_backoff_per_message(self):
        from sac.daemon import Daemon
        d = Daemon(self.cfg, self.store, Tmux("sac-test"))
        d._poke_state.setdefault("dev-1", {})["msg-a"] = time.monotonic()
        int_a = d._poke_interval("msg-b")
        int_a_poked = d._poke_interval("msg-a")
        self.assertGreater(int_a_poked, int_a,
                           "msg-a com 1 poke deve ter intervalo maior que msg-b sem pokes")

    def test_deliver_reply_unknown_agent(self):
        from sac.daemon import Daemon
        from sac.config import ConfigError
        from unittest.mock import patch
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%1|env SAC_AGENT=leader kimi\n"
        d = Daemon(self.cfg, self.store, tmux)
        self.store.send("leader", "dev-1", "task", now=datetime.now())
        self.store.next("dev-1")
        self.store.send("dev-1", "leader", "reply", now=datetime.now())
        with patch.object(self.cfg, 'agent', side_effect=ConfigError("unknown")):
            d._process_agent("leader")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("loop_error", log, "cfg.agent falhando deve logar loop_error")

    def test_deliver_reply_pane_not_found(self):
        from sac.daemon import Daemon
        runner = FakeRunner(outputs={"list-panes": "%1|some other process\n"})
        tmux = Tmux("sac-test", runner=runner)
        d = Daemon(self.cfg, self.store, tmux)
        mid = self.store.send("user", "dev-1", "task", now=datetime.now())
        d._deliver_next("dev-1")
        self.assertEqual(self.store.pending("dev-1"), [mid],
                         "sem pane: msg não deve ser removida da inbox")
        log = (self.store.root / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("deliver_skip", log,
                      "sem pane: deve logar deliver_skip")

    def test_daemon_deliver_with_forced_enter(self):
        from sac.daemon import Daemon
        from unittest.mock import patch
        runner = FakeRunner()
        tmux = Tmux("sac-test", runner=runner)
        runner.outputs["list-panes"] = "%2|env SAC_AGENT=dev-1 opencode\n"
        d = Daemon(self.cfg, self.store, tmux)
        self.store.send("leader", "dev-1", "task body", now=datetime.now())
        with patch("sac.tmux.time.sleep"):
            d._deliver_next("dev-1")
        send_body = [c for c in runner.calls if c[1] == "send-keys" and len(c) > 3 and "-l" in c]
        enter_calls = [c for c in runner.calls if c[1] == "send-keys" and c[-1] == "Enter"]
        self.assertEqual(len(send_body), 1, "deve enviar body com send-keys -l")
        self.assertEqual(len(enter_calls), 1, "deve enviar Enter separado")
        self.assertIn("SAC: mensagem", str(runner.calls),
                      "body deve conter hint SAC: mensagem")

    def test_daemon_backoff_caps_at_600s(self):
        from sac.daemon import Daemon
        d = Daemon(self.cfg, self.store, Tmux("sac-test"))
        mid = "some-msg"
        state = d._poke_state.setdefault("dev-1", {})
        for _ in range(10):
            state[mid] = time.monotonic()
        interval = d._poke_interval(mid)
        self.assertLessEqual(interval, 600, "backoff não deve ultrapassar 600s")


if __name__ == "__main__":
    unittest.main()


class EscalationTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(self.d / "sac.toml")
        self.store = Store(self.d / ".sac")

    def _make_daemon(self):
        from sac.daemon import Daemon
        runner = FakeRunner()
        runner.outputs["list-panes"] = "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n"
        tmux = Tmux("sac-test", runner=runner)
        return Daemon(self.cfg, self.store, tmux), runner

    def _stale_claim(self):
        old = datetime.now() - timedelta(seconds=300)
        mid = self.store.send("user", "dev-1", "old task", now=old)
        self.store.next("dev-1")
        return mid

    def _poke(self, d):
        d._poke_state.clear()  # zera o throttle para forçar o próximo poke
        d._process_agent("dev-1")

    def _log_text(self):
        return (self.store.root / "log.jsonl").read_text(encoding="utf-8")

    def test_poke_text_instrui_reporte(self):
        d, runner = self._make_daemon()
        self._stale_claim()
        d._process_agent("dev-1")
        poke_calls = [c for c in runner.calls if "pendente" in str(c)]
        self.assertEqual(len(poke_calls), 1, "deve cutucar tarefa stale")
        body = str(poke_calls[0])
        self.assertIn("reporte AGORA", body, "poke deve instruir reporte imediato")
        self.assertIn("sac send leader", body, "poke deve citar o nome real do líder")

    def test_poke_text_instrui_reenvio(self):
        d, runner = self._make_daemon()
        self._stale_claim()
        d._process_agent("dev-1")
        poke_calls = [c for c in runner.calls if "pendente" in str(c)]
        self.assertEqual(len(poke_calls), 1, "deve cutucar tarefa stale")
        body = str(poke_calls[0])
        self.assertIn("REENVIE", body, "poke deve instruir reenvio do resultado")
        self.assertIn("mesmo que já tenha enviado", body,
                      "reenvio vale mesmo se já enviou (entrega pode ter falhado)")
        self.assertIn("sac send leader", body, "reenvio usa o nome real do líder")
        self.assertLess(body.index("REENVIE"), body.index("sac done"),
                        "instrução de reenvio deve preceder a de `sac done`")

    def test_daemon_escalate_apos_n_pokes(self):
        d, runner = self._make_daemon()
        mid = self._stale_claim()
        for _ in range(3):
            self._poke(d)
        log = self._log_text()
        self.assertIn('"escalate"', log, "3º poke sem done deve logar escalate")
        leader_pending = self.store.pending("leader")
        self.assertEqual(len(leader_pending), 1, "líder deve receber 1 mensagem de escalonamento")
        self.assertTrue(leader_pending[0].endswith("-from-daemon"),
                        "escalonamento deve ter sender 'daemon'")
        msg_file = next((self.store.root / "inbox" / "leader").glob("*.msg"))
        content = msg_file.read_text(encoding="utf-8")
        self.assertIn("sem progresso", content)
        self.assertIn(mid, content)

    def test_lider_nunca_autoescalado(self):
        d, runner = self._make_daemon()
        old = datetime.now() - timedelta(seconds=300)
        self.store.send("user", "leader", "old task", now=old)
        self.store.next("leader")
        for _ in range(5):
            d._poke_state.clear()  # zera o throttle para forçar o próximo poke
            d._process_agent("leader")
        log = self._log_text()
        self.assertNotIn('"escalate"', log, "líder nunca deve ser escalado")
        inbox = self.store.root / "inbox" / "leader"
        daemon_msgs = list(inbox.glob("*-from-daemon")) if inbox.is_dir() else []
        self.assertEqual(daemon_msgs, [], "nenhuma auto-escalação na inbox do líder")

    def test_daemon_escalate_uma_vez(self):
        d, runner = self._make_daemon()
        self._stale_claim()
        for _ in range(4):
            self._poke(d)
        log = self._log_text()
        self.assertEqual(log.count('"escalate"'), 1,
                         "4º poke na mesma mensagem NÃO deve escalar de novo")
        self.assertEqual(len(self.store.pending("leader")), 1,
                         "apenas 1 mensagem de escalonamento ao líder")


SCHEMA_VEREDITO = {
    "type": "object",
    "properties": {"veredito": {"enum": ["APROVADO", "REPROVADO"]}},
    "required": ["veredito"],
}


class ReplySchemaDaemonTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(self.d / "sac.toml")
        self.store = Store(self.d / ".sac")
        self.runner = FakeRunner()
        self.runner.outputs["list-panes"] = "%1|env SAC_AGENT=leader kimi\n"
        self.tmux = Tmux("sac-test", runner=self.runner)

    def _daemon(self):
        from sac.daemon import Daemon
        return Daemon(self.cfg, self.store, self.tmux)

    def _setup_reply(self, body: str):
        """Líder envia tarefa com reply_schema; dev-1 clama e responde."""
        self.store.send("leader", "dev-1", "valide X",
                        reply_schema=SCHEMA_VEREDITO, now=datetime.now())
        self.store.next("dev-1")
        self.store.send("dev-1", "leader", body, now=datetime.now())

    def _log_text(self):
        return (self.store.root / "log.jsonl").read_text(encoding="utf-8")

    def test_daemon_valida_reply_com_schema(self):
        from unittest.mock import patch
        d = self._daemon()
        self._setup_reply('{"veredito": "APROVADO"}')
        with patch("sac.tmux.time.sleep"):
            d._deliver_next("leader")
        log = self._log_text()
        self.assertIn('"validation": "ok"', log,
                      "reply válida deve registrar validation ok no deliver")
        send_body = [c for c in self.runner.calls
                     if c[1] == "send-keys" and len(c) > 3 and "-l" in c]
        self.assertEqual(len(send_body), 1, "reply válida deve ser entregue")
        self.assertIn("APROVADO", str(send_body[0]))
        self.assertEqual(self.store.claimed("leader"), [], "reply auto-ackada")

    def test_daemon_rejeita_reply_invalida(self):
        from unittest.mock import patch
        d = self._daemon()
        self._setup_reply('{"veredito": "INVALIDO"}')
        with patch("sac.tmux.time.sleep"):
            d._deliver_next("leader")
        send_body = [c for c in self.runner.calls
                     if c[1] == "send-keys" and len(c) > 3 and "-l" in c]
        self.assertEqual(len(send_body), 0,
                         "reply inválida NÃO deve ser entregue ao remetente")
        self.assertEqual(self.store.pending("leader"), [],
                         "reply rejeitada não fica na inbox do destinatário")
        self.assertEqual(self.store.claimed("leader"), [],
                         "reply rejeitada vai para done (não entra em loop)")
        erros = [self.store._parse(p).body
                 for p in (self.store.root / "inbox" / "dev-1").glob("*.msg")]
        self.assertEqual(len(erros), 1, "daemon deve devolver erro ao agente")
        self.assertIn("reply rejeitada", erros[0])
        self.assertIn("INVALIDO", erros[0], "erro deve detalhar a violação")

    def test_daemon_validation_error_logged(self):
        from unittest.mock import patch
        d = self._daemon()
        self._setup_reply('{"veredito": "INVALIDO"}')
        with patch("sac.tmux.time.sleep"):
            d._deliver_next("leader")
        self.assertIn('"validation_error"', self._log_text(),
                      "reply inválida deve registrar validation_error no log")

    def test_daemon_reply_sem_schema_nao_valida(self):
        from unittest.mock import patch
        d = self._daemon()
        self.store.send("leader", "dev-1", "faça X", now=datetime.now())
        self.store.next("dev-1")
        self.store.send("dev-1", "leader", "pronto, texto livre", now=datetime.now())
        with patch("sac.tmux.time.sleep"):
            d._deliver_next("leader")
        send_body = [c for c in self.runner.calls
                     if c[1] == "send-keys" and len(c) > 3 and "-l" in c]
        self.assertEqual(len(send_body), 1,
                         "sem schema, reply é entregue sem validação (compat)")
        self.assertNotIn("validation_error", self._log_text())
