import io
import json
import tempfile
import time
import unittest
from contextlib import redirect_stderr
from datetime import datetime
from pathlib import Path

from sac.commands import cmd_fanout
from sac.config import load_config
from sac.fanout import FanOutCollector, FanOutManager
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

[[agents]]
name = "auditor"
command = "opencode"
role = "aux"

[[agents]]
name = "secops"
command = "opencode"
role = "aux"
"""


class FanOutBase(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(self.d / "sac.toml")
        self.store = Store(self.d / ".sac")

    def _inbox(self, agent):
        return [self.store._parse(p)
                for p in sorted((self.store.root / "inbox" / agent).glob("*.msg"))]

    def _eventos(self, nome):
        path = self.store.root / "log.jsonl"
        if not path.is_file():
            return []
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
                if json.loads(l).get("event") == nome]


class FanOutDisparoTest(FanOutBase):
    def setUp(self):
        super().setUp()
        self.runner = FakeRunner(rc=1)  # sem sessão tmux
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_fanout_cria_mensagens_para_cada_target(self):
        rc = cmd_fanout(self.cfg, self.store, self.tmux, "Revise src/",
                        ["dev-1", "auditor", "secops"], sender="leader")
        self.assertEqual(rc, 0)
        ids = set()
        for target in ("dev-1", "auditor", "secops"):
            msgs = self._inbox(target)
            self.assertEqual(len(msgs), 1, f"{target} deve ter 1 mensagem")
            self.assertEqual(msgs[0].body, "Revise src/")
            self.assertIsNotNone(msgs[0].fanout_id)
            ids.add(msgs[0].fanout_id)
            raw = (self.store.root / "inbox" / target / f"{msgs[0].id}.msg").read_text(
                encoding="utf-8")
            self.assertIn(f"fanout_group: {msgs[0].fanout_id}", raw,
                          "cabeçalho fanout_group deve acompanhar o fanout_id")
        self.assertEqual(len(ids), 1, "todas as mensagens devem ter o mesmo fanout_id")

    def test_fanout_template_vazio_rejeitado(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = cmd_fanout(self.cfg, self.store, self.tmux, "", ["dev-1"],
                            sender="leader")
        self.assertNotEqual(rc, 0)
        self.assertIn("template não pode ser vazio", err.getvalue())
        self.assertEqual(self._inbox("dev-1"), [], "nenhuma mensagem deve ser criada")

    def test_fanout_sem_targets_rejeitado(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = cmd_fanout(self.cfg, self.store, self.tmux, "mensagem", [],
                            sender="leader")
        self.assertNotEqual(rc, 0)
        self.assertIn("pelo menos um target é necessário", err.getvalue())

    def test_fanout_target_desconhecido_rejeitado(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = cmd_fanout(self.cfg, self.store, self.tmux, "msg", ["ghost"],
                            sender="leader")
        self.assertNotEqual(rc, 0)
        self.assertEqual(self._inbox("dev-1"), [])

    def test_fanout_com_timeout_flag(self):
        rc = cmd_fanout(self.cfg, self.store, self.tmux, "tarefa", ["dev-1"],
                        timeout=120, sender="leader")
        self.assertEqual(rc, 0)
        fid = self._inbox("dev-1")[0].fanout_id
        state = json.loads((self.store.root / "fanout" / f"{fid}.partial.json")
                           .read_text(encoding="utf-8"))
        self.assertEqual(state["timeout"], 120)

    def test_fanout_timeout_default(self):
        rc = cmd_fanout(self.cfg, self.store, self.tmux, "tarefa", ["dev-1"],
                        sender="leader")
        self.assertEqual(rc, 0)
        fid = self._inbox("dev-1")[0].fanout_id
        state = json.loads((self.store.root / "fanout" / f"{fid}.partial.json")
                           .read_text(encoding="utf-8"))
        self.assertEqual(state["timeout"], 600, "timeout default deve ser 600s")

    def test_fanout_evento_logged(self):
        cmd_fanout(self.cfg, self.store, self.tmux, "tarefa",
                   ["dev-1", "auditor", "secops"], sender="leader")
        eventos = self._eventos("fanout")
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["targets"], 3,
                         "evento fanout deve registrar a contagem de targets")

    def test_fanout_daemon_morto_sem_coleta(self):
        """Sem daemon, fan-out cria as mensagens mas nada coleta (coleta manual)."""
        fid_msgs = cmd_fanout(self.cfg, self.store, self.tmux, "tarefa",
                              ["dev-1", "auditor"], sender="leader")
        self.assertEqual(fid_msgs, 0)
        fid = self._inbox("dev-1")[0].fanout_id
        self.store.next("dev-1")
        self.store.send("dev-1", "leader", "resp dev")
        self.assertEqual(len(self._inbox("leader")), 1,
                         "sem daemon, a reply fica na inbox do solicitante")
        self.assertFalse((self.store.root / "fanout" / f"{fid}.json").exists(),
                         "sem daemon, nenhum agregado é gerado")
        self.assertEqual(self._eventos("fanout_complete"), [])


class FanOutColetaTest(FanOutBase):
    def setUp(self):
        super().setUp()
        self.runner = FakeRunner()
        self.runner.outputs["list-panes"] = (
            "%1|env SAC_AGENT=leader kimi\n"
            "%2|env SAC_AGENT=dev-1 opencode\n"
            "%3|env SAC_AGENT=auditor opencode\n"
        )
        self.tmux = Tmux("sac-test", runner=self.runner)

    def _daemon(self):
        from sac.daemon import Daemon
        return Daemon(self.cfg, self.store, self.tmux)

    def _disparar(self, targets=("dev-1", "auditor"), timeout=300):
        mgr = FanOutManager(self.store)
        return mgr.disparar("leader", "Revise o PR", list(targets), timeout=timeout)

    def _responder(self, agent, body):
        self.store.next(agent)  # agente clama a tarefa do fan-out
        self.store.send(agent, "leader", body)

    def _final_path(self, fid):
        return self.store.root / "fanout" / f"{fid}.json"

    def _partial_path(self, fid):
        return self.store.root / "fanout" / f"{fid}.partial.json"

    def test_fanout_reply_com_fanout_id_incluido(self):
        fid = self._disparar()
        self._responder("dev-1", "ok dev")
        reply = self._inbox("leader")[0]
        self.assertEqual(reply.reply_to_fanout, fid,
                         "reply deve propagar reply_to_fanout da mensagem original")

    def test_fanout_coleta_todas_replies(self):
        fid = self._disparar(("dev-1", "auditor"))
        d = self._daemon()
        d._scan_fanouts()
        self.assertIn(fid, d._fanout_timers, "daemon deve agendar o timeout do fan-out")
        self._responder("dev-1", "resp dev")
        d._deliver_next("leader")
        self.assertFalse(self._final_path(fid).exists(),
                         "agregado não deve fechar com reply parcial")
        parcial = json.loads(self._partial_path(fid).read_text(encoding="utf-8"))
        self.assertEqual(parcial["replies"], {"dev-1": "resp dev"},
                         "parcial deve persistir a reply recebida (crash-safe)")
        self._responder("auditor", "resp auditor")
        d._deliver_next("leader")
        agregado = json.loads(self._final_path(fid).read_text(encoding="utf-8"))
        self.assertEqual(agregado, {"dev-1": "resp dev", "auditor": "resp auditor"})
        self.assertFalse(self._partial_path(fid).exists(),
                         "parcial deve ser removido ao completar")
        self.assertNotIn(fid, d._fanout_timers, "timer deve ser cancelado ao completar")
        completes = self._eventos("fanout_complete")
        self.assertEqual(len(completes), 1)
        self.assertEqual(completes[0]["received"], 2)
        self.assertEqual(self.store.claimed("leader"), [],
                         "replies do fan-out devem ser auto-ackadas")

    def test_fanout_agregado_entregue_ao_solicitante(self):
        fid = self._disparar(("dev-1", "auditor"))
        d = self._daemon()
        self._responder("dev-1", "resp dev")
        self._responder("auditor", "resp auditor")
        d._deliver_next("leader")
        d._deliver_next("leader")
        msgs = self._inbox("leader")
        agregados = [m for m in msgs if m.sender == "daemon"]
        self.assertEqual(len(agregados), 1,
                         "solicitante deve receber o agregado como mensagem única")
        self.assertIn(fid, agregados[0].body)
        corpo = json.loads(agregados[0].body.split("\n", 1)[1])
        self.assertEqual(corpo, {"dev-1": "resp dev", "auditor": "resp auditor"})

    def test_fanout_coleta_parcial_timeout(self):
        fid = self._disparar(("dev-1", "auditor"), timeout=300)
        d = self._daemon()
        self._responder("dev-1", "resp dev")
        d._deliver_next("leader")
        FanOutCollector(self.store).expirar(fid)
        agregado = json.loads(self._final_path(fid).read_text(encoding="utf-8"))
        self.assertEqual(agregado, {"dev-1": "resp dev", "auditor": "TIMEOUT"},
                         "ausentes devem constar como TIMEOUT")
        self.assertEqual(len(self._eventos("fanout_timeout")), 1)

    def test_fanout_sem_replies_timeout(self):
        fid = self._disparar(("dev-1", "auditor"), timeout=300)
        FanOutCollector(self.store).expirar(fid)
        agregado = json.loads(self._final_path(fid).read_text(encoding="utf-8"))
        self.assertEqual(agregado, {"dev-1": "TIMEOUT", "auditor": "TIMEOUT"})

    def test_fanout_reply_tardia_ignorada(self):
        """Reply que chega após o fechamento é ackada sem reabrir o agregado."""
        fid = self._disparar(("dev-1",), timeout=300)
        d = self._daemon()
        self._responder("dev-1", "resp dev")
        d._deliver_next("leader")
        antes = self._final_path(fid).read_text(encoding="utf-8")
        task_id = self.store.claimed("dev-1")[0]
        self.store.send("dev-1", "leader", "tarde demais", reply_to=task_id)
        d._deliver_next("leader")  # entrega o agregado
        d._deliver_next("leader")  # ack da reply tardia
        self.assertEqual(self._final_path(fid).read_text(encoding="utf-8"), antes,
                         "agregado fechado não deve ser alterado por reply tardia")
        self.assertEqual(self.store.pending("leader"), [],
                         "reply tardia deve ser ackada (não entregue)")

    def test_fanout_crash_resume(self):
        """Daemon novo retoma fan-out pendente: replies preservadas, novo timeout."""
        fid = self._disparar(("dev-1", "auditor"), timeout=1)
        d = self._daemon()
        self._responder("dev-1", "resp dev")
        d._deliver_next("leader")
        # crash do daemon: um novo sobe e retoma os pendentes
        d2 = self._daemon()
        d2._retomar_fanouts()
        self.assertIn(fid, d2._fanout_timers,
                      "fan-out pendente deve ser retomado com novo timeout")
        time.sleep(1.5)
        self.assertTrue(self._final_path(fid).exists(),
                        "timeout retomado deve fechar o agregado")
        agregado = json.loads(self._final_path(fid).read_text(encoding="utf-8"))
        self.assertEqual(agregado["dev-1"], "resp dev",
                         "reply coletada antes do crash deve ser preservada")
        self.assertEqual(agregado["auditor"], "TIMEOUT")

    def test_daemon_coleta_reply_fanout_do_user(self):
        """Solicitante 'user' (sem pane): daemon coleta da inbox do user."""
        mgr = FanOutManager(self.store)
        fid = mgr.disparar("user", "Revise o PR", ["dev-1"], timeout=300)
        self.store.next("dev-1")
        self.store.send("dev-1", "user", "resp dev")
        d = self._daemon()
        d._process_user_fanout()
        agregado = json.loads(self._final_path(fid).read_text(encoding="utf-8"))
        self.assertEqual(agregado, {"dev-1": "resp dev"})


if __name__ == "__main__":
    unittest.main()
