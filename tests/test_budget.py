"""Testes da v23e: budgets por run (tarefas, mensagens, wall time).

Contadores derivados do journal da run; enforce no `sac send` (criação) e no
daemon (entrega); grace period de 30s para wall time; overrides inline só na
criação da run.
"""
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from sac.budget import GRACE_PERIOD, BudgetTracker
from sac.commands import cmd_send
from sac.config import load_config
from sac.store import Store, StoreError
from sac.tmux import Tmux
from tests.test_tmux import FakeRunner

T0 = datetime(2026, 7, 24, 10, 0, 0)

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


class BudgetSendTest(unittest.TestCase):
    """Enforce no `sac send` + contadores derivados do journal."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.store = Store(self.root)
        self.sac = self.store.root
        (self.root / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(self.root / "sac.toml")
        self.runner = FakeRunner(rc=0, outputs={
            "list-panes": "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n",
        })
        self.tmux = Tmux("sac-test", runner=self.runner)

    def _cfg(self, extra: str):
        text = VALID.replace('name = "sac-test"', f'name = "sac-test"\n{extra}')
        (self.root / "sac.toml").write_text(text, encoding="utf-8")
        return load_config(self.root / "sac.toml")

    def _entries(self, run="r1") -> list[dict]:
        path = self.sac / "runs" / run / "journal.jsonl"
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]

    def _log(self) -> list[dict]:
        return [json.loads(l) for l in
                (self.sac / "log.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_budget_task_exceeded(self):
        cfg = self._cfg("max_tasks_per_run = 3")
        for i in range(3):
            cmd_send(cfg, self.store, self.tmux, "dev-1", f"tarefa {i}",
                     sender="leader", run="r1")
        with self.assertRaises(StoreError) as ctx:
            cmd_send(cfg, self.store, self.tmux, "dev-1", "tarefa 4",
                     sender="leader", run="r1")
        self.assertIn("limite de tarefas da run excedido (3)", str(ctx.exception))
        self.assertEqual(len(self.store.pending("dev-1")), 3,
                         "4ª mensagem não pode ser criada")

    def test_budget_message_exceeded(self):
        cfg = self._cfg("max_messages_per_run = 5")
        cmd_send(cfg, self.store, self.tmux, "dev-1", "t1", sender="leader", run="r1")
        self.store.next("dev-1")
        cmd_send(cfg, self.store, self.tmux, "leader", "resp1", sender="dev-1")
        self.store.next("leader")
        cmd_send(cfg, self.store, self.tmux, "dev-1", "t2", sender="leader", run="r1")
        self.store.next("dev-1")
        cmd_send(cfg, self.store, self.tmux, "leader", "resp2", sender="dev-1")
        self.store.next("leader")
        cmd_send(cfg, self.store, self.tmux, "dev-1", "t3", sender="leader", run="r1")
        self.store.next("dev-1")
        # 5 mensagens sob o run_id (3 tarefas + 2 replies): a 6ª é rejeitada
        with self.assertRaises(StoreError) as ctx:
            cmd_send(cfg, self.store, self.tmux, "leader", "resp3", sender="dev-1")
        self.assertIn("limite de mensagens da run excedido (5)", str(ctx.exception))
        exceeded = [e for e in self._entries() if e["event"] == "budget_exceeded"]
        self.assertEqual(exceeded[-1]["budget"], "messages")
        self.assertEqual(exceeded[-1]["limit"], 5)

    def test_budget_wall_time_exceeded(self):
        # run criada em T0 (passado) com teto de 10s: elapsed real >> 10s
        self.store.send("leader", "dev-1", "t1", now=T0, run="r1",
                        run_budgets={"budgets": {"max_tasks": 0, "max_messages": 0,
                                                 "max_wall_time": 10}})
        with self.assertRaises(StoreError) as ctx:
            cmd_send(self.cfg, self.store, self.tmux, "dev-1", "t2",
                     sender="leader", run="r1")
        self.assertIn("limite de tempo da run excedido (10)", str(ctx.exception))
        exceeded = [e for e in self._entries() if e["event"] == "budget_exceeded"]
        self.assertEqual(exceeded[-1]["budget"], "wall_time")
        self.assertEqual(exceeded[-1]["limit"], 10)

    def test_budget_unlimited_default(self):
        # sem campos de budget: comportamento livre, journal registra unlimited
        for i in range(5):
            cmd_send(self.cfg, self.store, self.tmux, "dev-1", f"tarefa {i}",
                     sender="leader", run="r1")
        self.assertEqual(len(self.store.pending("dev-1")), 5)
        starts = [e for e in self._entries() if e["event"] == "run_start"]
        self.assertEqual(starts[0]["budgets"], "unlimited")
        exceeded = [e for e in self._entries() if e["event"] == "budget_exceeded"]
        self.assertEqual(exceeded, [])

    def test_budget_grace_period(self):
        # wall time excedido mas dentro do grace: tracker não bloqueia com grace
        self.store.send("leader", "dev-1", "t1", now=T0, run="r1",
                        run_budgets={"budgets": {"max_tasks": 0, "max_messages": 0,
                                                 "max_wall_time": 10}})
        tracker = BudgetTracker(self.sac, "r1")
        dentro_do_grace = T0 + timedelta(seconds=15)
        self.assertEqual(tracker.exceeded(now=dentro_do_grace), "wall_time")
        self.assertIsNone(tracker.exceeded(now=dentro_do_grace, grace=True),
                          "grace de 30s permite claimed em andamento concluir")
        apos_grace = T0 + timedelta(seconds=10 + GRACE_PERIOD + 1)
        self.assertEqual(tracker.exceeded(now=apos_grace, grace=True), "wall_time",
                         "após o grace a run é bloqueada de vez")

    def test_budget_contadores_do_journal(self):
        # contadores reconstruídos do journal (sobrevivem a crash/restart)
        cfg = self._cfg("max_tasks_per_run = 3")
        for i in range(3):
            cmd_send(cfg, self.store, self.tmux, "dev-1", f"tarefa {i}",
                     sender="leader", run="r1")
        # "restart": nova instância do tracker, sem estado em memória
        tracker = BudgetTracker(self.sac, "r1")
        self.assertEqual(tracker.counts()["tasks"], 3,
                         "contador reconstruído do journal, não resetado")
        self.assertEqual(tracker.exceeded(), "tasks")

    def test_budget_snapshot_no_journal(self):
        cfg = self._cfg("max_tasks_per_run = 2")
        for i in range(2):
            cmd_send(cfg, self.store, self.tmux, "dev-1", f"tarefa {i}",
                     sender="leader", run="r1")
        with self.assertRaises(StoreError):
            cmd_send(cfg, self.store, self.tmux, "dev-1", "tarefa 3",
                     sender="leader", run="r1")
        exceeded = [e for e in self._entries() if e["event"] == "budget_exceeded"]
        self.assertEqual(len(exceeded), 1)
        self.assertEqual(exceeded[0]["budget"], "tasks")
        self.assertEqual(exceeded[0]["limit"], 2)
        self.assertIn("ts", exceeded[0])
        # e também no log.jsonl
        log_exc = [e for e in self._log() if e["event"] == "budget_exceeded"]
        self.assertEqual(len(log_exc), 1)
        self.assertEqual(log_exc[0]["budget"], "tasks")
        self.assertEqual(log_exc[0]["limit"], 2)

    def test_budget_override_inline_na_criacao(self):
        cfg = self._cfg("max_tasks_per_run = 50\nmax_wall_time_per_run = 3600")
        cmd_send(cfg, self.store, self.tmux, "dev-1", "t1",
                 sender="leader", run="r1", max_tasks=2, max_wall_time=600)
        starts = [e for e in self._entries() if e["event"] == "run_start"]
        self.assertEqual(starts[0]["budgets"],
                         {"max_tasks": 2, "max_messages": 0, "max_wall_time": 600},
                         "overrides inline sobrescrevem o sac.toml na criação")
        cmd_send(cfg, self.store, self.tmux, "dev-1", "t2", sender="leader", run="r1")
        with self.assertRaises(StoreError) as ctx:
            cmd_send(cfg, self.store, self.tmux, "dev-1", "t3",
                     sender="leader", run="r1")
        self.assertIn("limite de tarefas da run excedido (2)", str(ctx.exception),
                      "vale o override (2), não o sac.toml (50)")

    def test_budget_override_inline_ignorado_em_run_existente(self):
        cmd_send(self.cfg, self.store, self.tmux, "dev-1", "t1",
                 sender="leader", run="r1", max_tasks=3)
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            cmd_send(self.cfg, self.store, self.tmux, "dev-1", "t2",
                     sender="leader", run="r1", max_tasks=1)
        self.assertIn("criação da run", err.getvalue(),
                      "flags em run existente devem avisar que são ignoradas")
        starts = [e for e in self._entries() if e["event"] == "run_start"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0]["budgets"]["max_tasks"], 3,
                         "budgets da run não são alterados por mensagem seguinte")

    def test_budget_flags_sem_run(self):
        with self.assertRaises(StoreError) as ctx:
            cmd_send(self.cfg, self.store, self.tmux, "dev-1", "tarefa",
                     sender="leader", max_tasks=10)
        self.assertIn("flags de budget exigem --run", str(ctx.exception))

    def test_reply_herda_run_e_conta_mensagem(self):
        mid = self.store.send("leader", "dev-1", "t1", now=T0, run="r1")
        self.store.next("dev-1")
        rid = self.store.send("dev-1", "leader", "resp", now=T0)
        msg = self.store.find("leader", rid)
        self.assertEqual(msg.run, "r1", "reply correlacionada herda o run_id")
        events = [e["event"] for e in self._entries()]
        self.assertEqual(events, ["run_start", "task_sent", "reply_sent"])
        tracker = BudgetTracker(self.sac, "r1")
        self.assertEqual(tracker.counts(), {"tasks": 1, "messages": 2})


class BudgetDaemonTest(unittest.TestCase):
    """Enforce no daemon: bloqueio de entrega de run suspensa + grace period."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.store = Store(self.root)
        self.sac = self.store.root
        (self.root / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(self.root / "sac.toml")
        self.runner = FakeRunner(rc=0, outputs={
            "list-panes": "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n",
        })
        self.tmux = Tmux("sac-test", runner=self.runner)

    def _daemon(self):
        from sac.daemon import Daemon
        return Daemon(self.cfg, self.store, self.tmux)

    def _log_text(self):
        return (self.sac / "log.jsonl").read_text(encoding="utf-8")

    def _send_keys(self):
        return [c for c in self.runner.calls
                if c[1] == "send-keys" and len(c) > 3 and "-l" in c]

    def test_daemon_bloqueia_entrega_run_suspensa(self):
        # teto de tarefas atingido entre o send e a entrega (remetente pulou o gate)
        self.store.send("leader", "dev-1", "t1", run="r1",
                        run_budgets={"budgets": {"max_tasks": 1, "max_messages": 0,
                                                 "max_wall_time": 0}})
        self.store.send("user", "dev-1", "t2", run="r1")
        d = self._daemon()
        with mock.patch("sac.tmux.time.sleep"):
            d._deliver_next("dev-1")
        self.assertEqual(len(self.store.pending("dev-1")), 2,
                         "mensagens de run suspensa ficam na inbox")
        self.assertEqual(self._send_keys(), [], "nada é entregue")
        log = self._log_text()
        self.assertIn('"budget_exceeded"', log)
        self.assertIn('"budget_blocked"', log)

    def test_daemon_bloqueia_wall_time_apos_grace(self):
        # run criada há 60s com teto de 10s: grace (30s) esgotado → bloqueia
        old = datetime.now() - timedelta(seconds=60)
        self.store.send("leader", "dev-1", "t1", now=old, run="r1",
                        run_budgets={"budgets": {"max_tasks": 0, "max_messages": 0,
                                                 "max_wall_time": 10}})
        d = self._daemon()
        with mock.patch("sac.tmux.time.sleep"):
            d._deliver_next("dev-1")
        self.assertEqual(self._send_keys(), [])
        self.assertIn('"budget": "wall_time"', self._log_text())

    def test_daemon_entrega_durante_grace(self):
        # teto de 10s excedido há 15s (< grace de 30s): claimed pode concluir
        old = datetime.now() - timedelta(seconds=15)
        self.store.send("leader", "dev-1", "t1", now=old, run="r1",
                        run_budgets={"budgets": {"max_tasks": 0, "max_messages": 0,
                                                 "max_wall_time": 10}})
        d = self._daemon()
        with mock.patch("sac.tmux.time.sleep"):
            d._deliver_next("dev-1")
        self.assertEqual(len(self._send_keys()), 1,
                         "dentro do grace a entrega segue (claimed pode concluir)")

    def test_daemon_sem_budget_comportamento_inalterado(self):
        self.store.send("leader", "dev-1", "t1", run="r1")
        d = self._daemon()
        with mock.patch("sac.tmux.time.sleep"):
            d._deliver_next("dev-1")
        self.assertEqual(len(self._send_keys()), 1,
                         "run sem tetos (unlimited) entrega normalmente")
        self.assertNotIn("budget_exceeded", self._log_text())


if __name__ == "__main__":
    unittest.main()
