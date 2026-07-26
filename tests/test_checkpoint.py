import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from sac.commands import cmd_approve, cmd_respond, cmd_send
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


class MsgTypeTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.store = Store(self.root)
        self.sac = self.store.root

    def test_msg_header_com_type_approval(self):
        mid = self.store.send("leader", "user", "Podemos fazer deploy?", now=T0,
                              msg_type="approval_request", state="pending")
        path = self.sac / "inbox" / "user" / f"{mid}.msg"
        text = path.read_text(encoding="utf-8")
        self.assertIn("type: approval_request", text)
        self.assertIn("state: pending", text)
        msg = self.store._parse(path)
        self.assertEqual(msg.type, "approval_request")
        self.assertEqual(msg.state, "pending")
        self.assertEqual(msg.sender, "leader")
        self.assertEqual(msg.recipient, "user")
        self.assertEqual(msg.body, "Podemos fazer deploy?")
        log = (self.sac / "log.jsonl").read_text(encoding="utf-8")
        ev = json.loads(log.strip().splitlines()[-1])
        self.assertEqual(ev["event"], "send")
        self.assertEqual(ev["type"], "approval_request")

    def test_msg_sem_type_continua_funcionando(self):
        mid = self.store.send("leader", "dev-1", "faça X", now=T0)
        path = self.sac / "inbox" / "dev-1" / f"{mid}.msg"
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("type:", text)
        self.assertNotIn("state:", text)
        msg = self.store._parse(path)
        self.assertIsNone(msg.type)
        self.assertIsNone(msg.state)
        self.assertEqual(msg.body, "faça X")
        self.assertEqual(self.store.next("dev-1").id, mid,
                         "fluxo legado (next/claimed) intacto")

    def test_approval_state_machine(self):
        mid = self.store.send("leader", "user", "deploy?", now=T0,
                              msg_type="approval_request", state="pending")
        self.assertTrue(self.store.is_approval_request("user", mid))
        msg = self.store.set_approval_state("user", mid, "approved")
        self.assertEqual(msg.state, "approved")
        self.assertEqual(self.store.pending("user"), [])
        done = self.sac / "done" / "user" / f"{mid}.msg"
        self.assertTrue(done.is_file())
        self.assertIn("state: approved", done.read_text(encoding="utf-8"))

        mid2 = self.store.send("leader", "user", "outro pedido?", now=T0,
                               msg_type="approval_request", state="pending")
        msg2 = self.store.set_approval_state("user", mid2, "rejected",
                                             motivo="fora do escopo")
        self.assertEqual(msg2.state, "rejected")
        evs = [json.loads(l) for l in
               (self.sac / "log.jsonl").read_text(encoding="utf-8").strip().splitlines()]
        approvals = [e for e in evs if e["event"] == "approval"]
        self.assertEqual(len(approvals), 2)
        self.assertEqual(approvals[0]["state"], "approved")
        self.assertEqual(approvals[1]["state"], "rejected")
        self.assertEqual(approvals[1]["motivo"], "fora do escopo")

    def test_approval_duplicada_rejeitada(self):
        mid = self.store.send("leader", "user", "deploy?", now=T0,
                              msg_type="approval_request", state="pending")
        self.store.set_approval_state("user", mid, "approved")
        with self.assertRaises(StoreError):
            self.store.set_approval_state("user", mid, "approved")
        with self.assertRaises(StoreError):
            self.store.set_approval_state("user", mid, "rejected")


class ApprovalCommandsTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d / ".sac")
        self.sac = self.store.root
        self.runner = FakeRunner(rc=0, outputs={
            "list-panes": "%1|env SAC_AGENT=leader kimi\n%2|env SAC_AGENT=dev-1 opencode\n",
        })
        self.tmux = Tmux("sac-test", runner=self.runner)

    def _approval(self, body="Podemos fazer deploy?") -> str:
        return self.store.send("leader", "user", body,
                               msg_type="approval_request", state="pending")

    def _reply_para_leader(self):
        pend = self.store.pending("leader")
        self.assertEqual(len(pend), 1, "líder deve receber exatamente 1 reply automática")
        path = self.sac / "inbox" / "leader" / f"{pend[0]}.msg"
        return self.store._parse(path)

    def test_cmd_approve_sucesso(self):
        mid = self._approval()
        rc = cmd_approve(self.store, mid)
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.pending("user"), [])
        done = self.sac / "done" / "user" / f"{mid}.msg"
        self.assertIn("state: approved", done.read_text(encoding="utf-8"))
        reply = self._reply_para_leader()
        self.assertEqual(reply.sender, "user")
        self.assertEqual(reply.reply_to, mid)
        self.assertIn("APROVADO", reply.body)
        log = (self.sac / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn('"approval"', log)

    def test_cmd_approve_nao_approval_request(self):
        mid = self.store.send("leader", "user", "mensagem comum")
        rc = cmd_approve(self.store, mid)
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.store.pending("user"), [mid],
                         "mensagem comum não deve sair da inbox")
        self.assertEqual(self.store.pending("leader"), [],
                         "sem reply automática para mensagem comum")

    def test_cmd_respond_approved(self):
        mid = self._approval()
        rc = cmd_respond(self.store, mid, "APPROVED")
        self.assertEqual(rc, 0)
        done = self.sac / "done" / "user" / f"{mid}.msg"
        self.assertIn("state: approved", done.read_text(encoding="utf-8"))
        reply = self._reply_para_leader()
        self.assertIn("APROVADO", reply.body)

    def test_cmd_respond_rejected_com_motivo(self):
        mid = self._approval()
        rc = cmd_respond(self.store, mid, "REJECTED", "Fora do escopo da sprint")
        self.assertEqual(rc, 0)
        done = self.sac / "done" / "user" / f"{mid}.msg"
        self.assertIn("state: rejected", done.read_text(encoding="utf-8"))
        reply = self._reply_para_leader()
        self.assertIn("REJEITADO", reply.body)
        self.assertIn("Fora do escopo da sprint", reply.body)

    def test_cmd_respond_veredito_invalido(self):
        mid = self._approval()
        rc = cmd_respond(self.store, mid, "TALVEZ")
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.store.pending("user"), [mid],
                         "veredito inválido não altera a mensagem")
        self.assertEqual(self.store.pending("leader"), [],
                         "sem reply automática com veredito inválido")

    def test_cmd_send_approval_leader(self):
        mid = cmd_send(self.cfg, self.store, self.tmux, "user",
                       "Podemos fazer deploy?", sender="leader", approval=True)
        path = self.sac / "inbox" / "user" / f"{mid}.msg"
        text = path.read_text(encoding="utf-8")
        self.assertIn("type: approval_request", text)
        self.assertIn("state: pending", text)

    def test_cmd_send_approval_aux_rejeitado(self):
        with self.assertRaises(StoreError):
            cmd_send(self.cfg, self.store, self.tmux, "user", "deploy?",
                     sender="dev-1", approval=True)
        self.assertEqual(self.store.pending("user"), [])

    def test_cmd_send_approval_humano_rejeitado(self):
        with self.assertRaises(StoreError):
            cmd_send(self.cfg, self.store, self.tmux, "user", "deploy?",
                     sender="user", approval=True)
        self.assertEqual(self.store.pending("user"), [])


class DaemonApprovalTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d / ".sac")
        self.sac = self.store.root
        self.runner = FakeRunner(rc=0, outputs={
            "list-panes": "%1|env SAC_AGENT=leader kimi\n",
        })
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_daemon_renderiza_approval_no_pane_do_leader(self):
        from sac.daemon import Daemon
        d = Daemon(self.cfg, self.store, self.tmux)
        mid = self.store.send("leader", "user", "Podemos fazer deploy?",
                              msg_type="approval_request", state="pending")
        with mock.patch("sac.tmux.time.sleep"):
            d._process_user_approvals()
        send_body = [c for c in self.runner.calls
                     if c[1] == "send-keys" and len(c) > 3 and "-l" in c]
        self.assertEqual(len(send_body), 1,
                         "pedido deve ser renderizado no pane do líder")
        alvo = send_body[0][send_body[0].index("-t") + 1]
        self.assertEqual(alvo, "%1", "render vai para o pane do líder (user não tem pane)")
        self.assertIn(mid, str(send_body[0]), "render deve conter o id da mensagem")
        self.assertIn("Podemos fazer deploy?", str(send_body[0]),
                      "render deve conter o texto do pedido")
        self.assertIn("sac approve", str(send_body[0]),
                      "render deve conter a instrução de resposta")
        self.assertEqual(self.store.pending("user"), [mid],
                         "mensagem permanece na inbox até ser respondida")
        log = (self.sac / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("approval_prompt", log)
        with mock.patch("sac.tmux.time.sleep"):
            d._process_user_approvals()
        send_body = [c for c in self.runner.calls
                     if c[1] == "send-keys" and len(c) > 3 and "-l" in c]
        self.assertEqual(len(send_body), 1,
                         "não deve renderizar de novo no próximo poll")

    def test_daemon_sem_pane_do_leader_nao_renderiza(self):
        from sac.daemon import Daemon
        self.runner.outputs["list-panes"] = "%9|some other process\n"
        d = Daemon(self.cfg, self.store, self.tmux)
        mid = self.store.send("leader", "user", "Podemos fazer deploy?",
                              msg_type="approval_request", state="pending")
        d._process_user_approvals()
        send_body = [c for c in self.runner.calls
                     if c[1] == "send-keys" and len(c) > 3 and "-l" in c]
        self.assertEqual(len(send_body), 0, "sem pane do líder, sem render")
        self.assertEqual(self.store.pending("user"), [mid],
                         "mensagem permanece na inbox")
        log_path = self.sac / "log.jsonl"
        log = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
        self.assertNotIn("approval_prompt", log)


if __name__ == "__main__":
    unittest.main()
