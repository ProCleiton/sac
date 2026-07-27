"""Testes da v23c: runs (agrupador nomeado), journal append-only, `sac runs` e `sac resume`."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from sac.commands import cmd_resume, cmd_runs, cmd_send
from sac.config import load_config
from sac.run import RunError, RunJournal
from sac.store import Store
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
prompt_file = "prompts/leader.md"

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"
prompt_file = "prompts/dev.md"
"""


def _journal_entries(sac_root: Path, run_id: str) -> list[dict]:
    path = sac_root / "runs" / run_id / "journal.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def _log_events(sac_root: Path) -> list[dict]:
    path = sac_root / "log.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


class RunJournalTest(unittest.TestCase):
    """Seção 1 — run como agrupador via run_id + journal (store/send/done)."""

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

    def test_send_com_run_cria_run_implicitamente(self):
        mid = cmd_send(self.cfg, self.store, self.tmux, "dev-1", "tarefa A",
                       sender="leader", run="sprint-42")
        journal = self.sac / "runs" / "sprint-42" / "journal.jsonl"
        self.assertTrue(journal.is_file())
        entries = _journal_entries(self.sac, "sprint-42")
        self.assertEqual(entries[0]["event"], "run_start")
        self.assertEqual(entries[0]["run"], "sprint-42")
        self.assertEqual(entries[1]["event"], "task_sent")
        self.assertEqual(entries[1]["msg_id"], mid)
        text = (self.sac / "inbox" / "dev-1" / f"{mid}.msg").read_text(encoding="utf-8")
        self.assertIn("run: sprint-42", text)

    def test_send_com_run_existente_nao_recria(self):
        cmd_send(self.cfg, self.store, self.tmux, "dev-1", "tarefa A",
                 sender="leader", run="sprint-42")
        mid2 = cmd_send(self.cfg, self.store, self.tmux, "dev-1", "tarefa B",
                        sender="leader", run="sprint-42")
        entries = _journal_entries(self.sac, "sprint-42")
        starts = [e for e in entries if e["event"] == "run_start"]
        self.assertEqual(len(starts), 1, "run_start não pode ser duplicado")
        sents = [e for e in entries if e["event"] == "task_sent"]
        self.assertEqual(len(sents), 2)
        self.assertEqual(sents[-1]["msg_id"], mid2)

    def test_msg_header_com_run_id(self):
        mid = self.store.send("leader", "dev-1", "tarefa", now=T0, run="sprint-42")
        msg = self.store.find("dev-1", mid)
        self.assertEqual(msg.run, "sprint-42")
        # legado: mensagem sem run segue inalterada
        mid2 = self.store.send("leader", "dev-1", "tarefa legada", now=T0)
        msg2 = self.store.find("dev-1", mid2)
        self.assertIsNone(msg2.run)
        text = (self.sac / "inbox" / "dev-1" / f"{mid2}.msg").read_text(encoding="utf-8")
        self.assertNotIn("run:", text)

    def test_send_sem_run_nao_toca_journal(self):
        cmd_send(self.cfg, self.store, self.tmux, "dev-1", "tarefa", sender="leader")
        self.assertFalse((self.sac / "runs").exists())

    def test_run_journal_append_task_done(self):
        mid = self.store.send("leader", "dev-1", "tarefa", now=T0, run="sprint-42")
        self.store.next("dev-1")
        self.assertTrue(self.store.done("dev-1", mid, "feito", now=T0))
        entries = _journal_entries(self.sac, "sprint-42")
        dones = [e for e in entries if e["event"] == "task_done"]
        self.assertEqual(len(dones), 1)
        self.assertEqual(dones[0]["msg_id"], mid)
        self.assertEqual(dones[0]["result_summary"], "feito")
        # ordem: run_start, task_sent, task_done
        self.assertEqual([e["event"] for e in entries],
                         ["run_start", "task_sent", "task_done"])

    def test_done_sem_run_nao_toca_journal(self):
        mid = self.store.send("leader", "dev-1", "tarefa", now=T0)
        self.store.next("dev-1")
        self.assertTrue(self.store.done("dev-1", mid, "feito", now=T0))
        self.assertFalse((self.sac / "runs").exists())

    def test_done_journal_falha_nao_desfaz_conclusao(self):
        mid = self.store.send("leader", "dev-1", "tarefa", now=T0, run="sprint-42")
        self.store.next("dev-1")
        with mock.patch("sac.store.RunJournal.log_entry",
                        side_effect=OSError("disco cheio")):
            ok = self.store.done("dev-1", mid, "feito", now=T0)
        self.assertTrue(ok, "falha no journal não pode desfazer a conclusão")
        self.assertTrue((self.sac / "done" / "dev-1" / f"{mid}.msg").is_file())
        events = _log_events(self.sac)
        erros = [e for e in events if e["event"] == "loop_error"
                 and "run_journal_write_failed" in e.get("error", "")]
        self.assertEqual(len(erros), 1)

    def test_run_journal_fsync(self):
        j = RunJournal(self.sac, "sprint-42")
        with mock.patch("sac.run.os.fsync") as m_fsync:
            j.ensure(now=T0)
            j.log_entry("task_sent", now=T0, msg_id="m1", to="dev-1")
        self.assertEqual(m_fsync.call_count, 2, "cada entrada deve ser fsync'd")

    def test_run_journal_truncado(self):
        j = RunJournal(self.sac, "sprint-42")
        j.ensure(now=T0)
        j.log_entry("task_sent", now=T0, msg_id="m1", to="dev-1")
        # simula crash durante append: linha final incompleta
        with j.path.open("a", encoding="utf-8") as f:
            f.write('{"ts": "2026-07-24T10:00:01", "event": "task_do')
        entries = j.read_entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[-1]["event"], "task_sent",
                         "última entrada válida prevalece como checkpoint")

    def test_run_id_invalido(self):
        with self.assertRaises(RunError):
            RunJournal(self.sac, "../etc")
        with self.assertRaises(RunError):
            RunJournal(self.sac, "com espaço")


class RunsResumeTest(unittest.TestCase):
    """Seção 2 — `sac runs` (listagem) e `sac resume` (reconciliação)."""

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

    def _send_run(self, body="tarefa", run="sprint-42", now=T0, agent="dev-1"):
        return self.store.send("leader", agent, body, now=now, run=run)

    def test_cmd_runs_lista(self):
        m1 = self._send_run("t1")
        self._send_run("t2", now=T0 + timedelta(seconds=1))
        self.store.next("dev-1")
        self.store.done("dev-1", m1, "feito", now=T0 + timedelta(seconds=2))
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            rc = cmd_runs(self.store)
        self.assertEqual(rc, 0)
        text = buf.getvalue()
        self.assertIn("sprint-42", text)
        self.assertIn("sent=2", text)
        self.assertIn("done=1", text)
        self.assertIn("pending=1", text)

    def test_cmd_runs_sem_runs(self):
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            rc = cmd_runs(self.store)
        self.assertEqual(rc, 0)
        self.assertIn("nenhuma run", buf.getvalue())

    def test_cmd_resume_reentrega_pending(self):
        mid = self._send_run("tarefa pendente")
        rc = cmd_resume(self.cfg, self.store, self.tmux, "sprint-42")
        self.assertEqual(rc, 0)
        # mensagem continua na inbox e o pane foi re-cutucado
        self.assertEqual(self.store.pending("dev-1"), [mid])
        pokes = [c for c in self.runner.calls if "send-keys" in c]
        self.assertTrue(any("sac next" in str(c) for c in pokes),
                        "resume deve re-cutucar o pane do agente")
        events = _log_events(self.sac)
        resumes = [e for e in events if e["event"] == "resume"]
        self.assertEqual(len(resumes), 1)
        self.assertEqual(resumes[0]["id"], mid)
        self.assertEqual(resumes[0]["agent"], "dev-1")

    def test_cmd_resume_reenfileira_claimed_orfa(self):
        mid = self._send_run("tarefa órfã")  # id com ts de T0 → stale (> poke_stale_after)
        self.store.next("dev-1")
        self.assertEqual(self.store.claimed("dev-1"), [mid])
        rc = cmd_resume(self.cfg, self.store, self.tmux, "sprint-42")
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.claimed("dev-1"), [])
        self.assertEqual(self.store.pending("dev-1"), [mid],
                         "claimed órfã deve voltar para a inbox")
        events = _log_events(self.sac)
        requeues = [e for e in events if e["event"] == "requeue"]
        self.assertEqual(len(requeues), 1)
        self.assertEqual(requeues[0]["id"], mid)

    def test_cmd_resume_nao_toca_claimed_recente(self):
        # claimed há poucos segundos (agente legítimo trabalhando) não é reenfileirada
        mid = self.store.send("leader", "dev-1", "tarefa", run="sprint-42")
        self.store.next("dev-1")
        rc = cmd_resume(self.cfg, self.store, self.tmux, "sprint-42")
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.claimed("dev-1"), [mid])
        self.assertEqual(self.store.pending("dev-1"), [])
        events = _log_events(self.sac)
        self.assertEqual([e for e in events if e["event"] == "requeue"], [])

    def test_cmd_resume_nao_toca_done(self):
        m1 = self._send_run("t1")
        m2 = self._send_run("t2", now=T0 + timedelta(seconds=1))
        m3 = self._send_run("t3", now=T0 + timedelta(seconds=2))
        for m in (m1, m2, m3):
            self.store.next("dev-1")
            self.store.done("dev-1", m, "feito", now=T0 + timedelta(seconds=3))
        rc = cmd_resume(self.cfg, self.store, self.tmux, "sprint-42")
        self.assertEqual(rc, 0)
        for m in (m1, m2, m3):
            self.assertTrue((self.sac / "done" / "dev-1" / f"{m}.msg").is_file())
            self.assertFalse((self.sac / "inbox" / "dev-1" / f"{m}.msg").exists())
        events = _log_events(self.sac)
        self.assertEqual([e for e in events if e["event"] in ("resume", "requeue")], [])

    def test_cmd_resume_run_completa(self):
        m1 = self._send_run("t1")
        self.store.next("dev-1")
        self.store.done("dev-1", m1, "feito", now=T0 + timedelta(seconds=1))
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            rc = cmd_resume(self.cfg, self.store, self.tmux, "sprint-42")
        self.assertEqual(rc, 0)
        self.assertIn("concluída", buf.getvalue())

    def test_cmd_resume_inexistente(self):
        import io
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            rc = cmd_resume(self.cfg, self.store, self.tmux, "run-fantasma")
        self.assertEqual(rc, 1)
        self.assertIn("run não encontrada", err.getvalue())


if __name__ == "__main__":
    unittest.main()
