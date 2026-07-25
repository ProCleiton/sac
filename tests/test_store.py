import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from sac.store import Store, StoreError

T0 = datetime(2026, 7, 24, 10, 0, 0)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.store = Store(self.root)
        self.sac = self.store.root

    def test_send_creates_file_and_returns_id(self):
        mid = self.store.send("leader", "dev-1", "faça X", now=T0)
        self.assertEqual(mid, "20260724-100000-001-from-leader")
        files = list((self.sac / "inbox" / "dev-1").glob("*.msg"))
        self.assertEqual(len(files), 1)
        text = files[0].read_text(encoding="utf-8")
        self.assertIn("from: leader", text)
        self.assertTrue(text.endswith("faça X"))

    def test_seq_increments_within_same_second(self):
        a = self.store.send("leader", "dev-1", "m1", now=T0)
        b = self.store.send("leader", "dev-1", "m2", now=T0)
        self.assertTrue(a.endswith("-001-from-leader"))
        self.assertTrue(b.endswith("-002-from-leader"))

    def test_next_fifo_moves_to_claimed(self):
        self.store.send("leader", "dev-1", "primeira", now=T0)
        self.store.send("leader", "dev-1", "segunda", now=T0 + timedelta(seconds=1))
        msg = self.store.next("dev-1")
        self.assertEqual(msg.body, "primeira")
        self.assertEqual(msg.sender, "leader")
        self.assertEqual(msg.recipient, "dev-1")
        self.assertEqual(self.store.pending("dev-1"), ["20260724-100001-001-from-leader"])
        self.assertEqual(self.store.claimed("dev-1"), [msg.id])

    def test_next_empty_returns_none(self):
        self.assertIsNone(self.store.next("dev-1"))

    def test_done_moves_claimed_to_done(self):
        mid = self.store.send("leader", "dev-1", "faça X", now=T0)
        self.store.next("dev-1")
        self.store.done("dev-1", mid, "feito", now=T0)
        self.assertEqual(self.store.claimed("dev-1"), [])
        done_files = list((self.sac / "done" / "dev-1").glob("*.msg"))
        self.assertEqual(len(done_files), 1)

    def test_done_without_claim_fails(self):
        mid = self.store.send("leader", "dev-1", "faça X", now=T0)
        with self.assertRaises(StoreError):
            self.store.done("dev-1", mid, "feito", now=T0)

    def test_stale_finds_old_messages(self):
        old = self.store.send("leader", "dev-1", "velha", now=T0)
        new = self.store.send("leader", "dev-1", "nova", now=T0 + timedelta(seconds=300))
        stale = self.store.stale("dev-1", 120, now=T0 + timedelta(seconds=300))
        self.assertEqual(stale, [old])
        self.assertNotIn(new, stale)

    def test_log_appends_jsonl(self):
        self.store.log("send", now=T0, sender="leader", to="dev-1", id="x")
        self.store.log("poke", now=T0, agent="dev-1", count=2)
        lines = (self.sac / "log.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        self.assertEqual(first["event"], "send")
        self.assertEqual(first["ts"], "2026-07-24T10:00:00")
        self.assertEqual(first["to"], "dev-1")

    def test_inbox_count(self):
        self.assertEqual(self.store.inbox_count("dev-1"), 0)
        self.store.send("user", "dev-1", "m1", now=T0)
        self.store.send("user", "dev-1", "m2", now=T0)
        self.assertEqual(self.store.inbox_count("dev-1"), 2)
        self.store.next("dev-1")
        self.assertEqual(self.store.inbox_count("dev-1"), 1)

    def test_last_event_age(self):
        now = T0 + timedelta(seconds=300)
        self.assertIsNone(self.store.last_event_age("dev-1", now=now))
        self.store.log("poke", now=T0, agent="dev-1", count=1)
        self.store.log("send", now=T0 + timedelta(seconds=60), sender="dev-1", to="leader", id="x")
        self.assertEqual(self.store.last_event_age("dev-1", now=now), 240)
        self.assertIsNone(self.store.last_event_age("auditor", now=now))

    def test_clean_orphans_removes_inbox(self):
        self.store.send("user", "auditor", "msg1", now=T0)
        self.store.send("user", "leader", "msg2", now=T0)
        self.store.send("user", "dev-1", "msg3", now=T0)
        self.store.next("auditor")
        done_dir = self.sac / "done" / "leader"
        done_dir.mkdir(parents=True, exist_ok=True)
        (done_dir / "some-msg.msg").write_text("done msg", encoding="utf-8")
        stats = self.store.clean_orphans(["leader", "dev-1"])
        self.assertIn("inbox_files", stats)
        self.assertIn("claimed_files", stats)
        self.assertFalse((self.sac / "inbox" / "auditor").exists(),
                          "inbox de agente removido deve ser limpa")
        self.assertFalse((self.sac / "claimed" / "auditor").exists(),
                          "claimed de agente removido deve ser limpa")
        self.assertTrue(done_dir.exists(),
                         "done/ não deve ser tocado")
        self.assertEqual(len(list((self.sac / "inbox" / "leader").glob("*.msg"))), 1,
                         "inbox de agente válido preservado")

    def test_clean_orphans_logs_event(self):
        self.store.send("user", "auditor", "msg1", now=T0)
        self.store.clean_orphans(["leader"])
        log = (self.sac / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("clean", log)
        self.assertIn("auditor", log)

    def test_clean_orphans_no_orphans(self):
        self.store.send("user", "leader", "msg1", now=T0)
        stats = self.store.clean_orphans(["leader"])
        self.assertEqual(stats["inbox_files"], 0)
        self.assertEqual(stats["claimed_files"], 0)

    def test_store_ack_moves_to_done(self):
        mid = self.store.send("leader", "dev-1", "ack task", now=T0)
        msg = self.store.ack("dev-1")
        self.assertIsNotNone(msg)
        self.assertEqual(msg.body, "ack task")
        self.assertEqual(msg.sender, "leader")
        self.assertEqual(self.store.pending("dev-1"), [])
        self.assertEqual(self.store.claimed("dev-1"), [])
        done_files = list((self.sac / "done" / "dev-1").glob("*.msg"))
        self.assertEqual(len(done_files), 1)
        log = (self.sac / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("ack", log)

    def test_store_ack_empty_returns_none(self):
        self.assertIsNone(self.store.ack("dev-1"))

    def test_parse_message_with_reply_to(self):
        d = self.sac / "inbox" / "dev-1"
        d.mkdir(parents=True, exist_ok=True)
        (d / "test.msg").write_text(
            "id: 20260724-100000-001-from-leader\n"
            "from: leader\n"
            "to: dev-1\n"
            "ts: 2026-07-24T10:00:00\n"
            "reply_to: 20260724-095959-001-from-user\n\nbody", encoding="utf-8")
        msg = self.store._parse(d / "test.msg")
        self.assertEqual(msg.reply_to, "20260724-095959-001-from-user")

    def test_parse_message_without_reply_to(self):
        d = self.sac / "inbox" / "dev-1"
        d.mkdir(parents=True, exist_ok=True)
        (d / "test.msg").write_text(
            "id: x\nfrom: leader\nto: dev-1\nts: 2026-07-24T10:00:00\n\nbody", encoding="utf-8")
        msg = self.store._parse(d / "test.msg")
        self.assertIsNone(msg.reply_to)

    def test_store_send_no_claimed_no_reply(self):
        mid = self.store.send("leader", "dev-1", "task", now=T0)
        msg = self.store._parse(self.sac / "inbox" / "dev-1" / f"{mid}.msg")
        self.assertIsNone(msg.reply_to, "sem claimed, sem reply_to")

    def test_store_send_multi_claimed_different_senders_uses_match(self):
        self.store.send("leader", "dev-1", "task1", now=T0)
        self.store.send("auditor", "dev-1", "task2", now=T0 + timedelta(seconds=1))
        self.store.next("dev-1")
        self.store.next("dev-1")
        mid = self.store.send("dev-1", "leader", "resposta", now=T0 + timedelta(seconds=2))
        msg = self.store._parse(self.sac / "inbox" / "leader" / f"{mid}.msg")
        task1_id = self.store._ids("claimed", "dev-1")[0]
        self.assertEqual(msg.reply_to, task1_id,
                         "deve encontrar a claimed cujo sender coincide com recipient")

    def test_store_send_reply_marked(self):
        task_mid = self.store.send("leader", "dev-1", "faça X", now=T0)
        self.store.next("dev-1")
        mid = self.store.send("dev-1", "leader", "pronto", now=T0 + timedelta(seconds=1))
        msg = self.store._parse(self.sac / "inbox" / "leader" / f"{mid}.msg")
        self.assertEqual(msg.reply_to, task_mid)

    def test_store_send_multi_claimed_uses_most_recent(self):
        self.store.send("leader", "dev-1", "t1", now=T0)
        self.store.send("leader", "dev-1", "t2", now=T0 + timedelta(seconds=1))
        self.store.next("dev-1")
        self.store.next("dev-1")
        mid = self.store.send("dev-1", "leader", "resposta", now=T0 + timedelta(seconds=2))
        msg = self.store._parse(self.sac / "inbox" / "leader" / f"{mid}.msg")
        task_ids = self.store._ids("claimed", "dev-1")
        self.assertIsNotNone(msg.reply_to, "com 2 claimed, deve inferir a mais recente")
        self.assertEqual(msg.reply_to, task_ids[-1], "deve usar a última (mais recente) claimed")

    def test_finish_reply_moves_to_done(self):
        mid = self.store.send("leader", "dev-1", "task", now=T0)
        self.store.next("dev-1")
        self.store.finish_reply("dev-1", mid)
        self.assertEqual(self.store.claimed("dev-1"), [], "reply não fica em claimed")
        done_files = list((self.sac / "done" / "dev-1").glob("*.msg"))
        self.assertEqual(len(done_files), 1)
        log = (self.sac / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("deliver_reply", log)

    def test_finish_reply_unknown_fails(self):
        with self.assertRaises(StoreError):
            self.store.finish_reply("dev-1", "nao-existe")

    def test_peek_next_returns_reply(self):
        mid = self.store.send("leader", "dev-1", "task", now=T0)
        self.store.next("dev-1")
        self.store.send("dev-1", "leader", "reply", now=T0 + timedelta(seconds=1))
        result = self.store.peek_next("leader")
        self.assertIsNotNone(result)
        id_, reply_to = result
        self.assertIsNotNone(reply_to, "pending reply deve ter reply_to")
        self.assertEqual(len(self.store.pending("leader")), 1, "peek não deve consumir")

    def test_peek_next_empty_returns_none(self):
        self.assertIsNone(self.store.peek_next("dev-1"))

    def test_peek_next_task_no_reply(self):
        self.store.send("user", "dev-1", "task", now=T0)
        result = self.store.peek_next("dev-1")
        self.assertIsNotNone(result)
        id_, reply_to = result
        self.assertIsNone(reply_to, "task sem reply_to")

    def test_clean_orphans_dry_run_lists_only(self):
        self.store.send("user", "auditor", "msg1", now=T0)
        self.store.send("user", "leader", "msg2", now=T0)
        stats = self.store.clean_orphans(["leader"], dry_run=True)
        self.assertIn("inbox_files", stats)
        self.assertIn("claimed_files", stats)
        self.assertIn("agents_removed", stats)
        self.assertTrue(
            (self.sac / "inbox" / "auditor").exists(),
            "dry_run: diretório não deve ser removido")
        self.assertTrue(
            (self.sac / "inbox" / "leader").exists(),
            "dry_run: inbox de agente válido preservado")

    def test_clean_orphans_yes_removes(self):
        self.store.send("user", "auditor", "msg1", now=T0)
        self.store.clean_orphans(["leader"], dry_run=False)
        self.assertFalse(
            (self.sac / "inbox" / "auditor").exists(),
            "dry_run=False: diretório deve ser removido")

    def test_clean_log_event_dry_run(self):
        self.store.send("user", "auditor", "msg1", now=T0)
        self.store.clean_orphans(["leader"], dry_run=True)
        log = (self.sac / "log.jsonl").read_text(encoding="utf-8")
        import json
        last_line = json.loads(log.strip().splitlines()[-1])
        self.assertEqual(last_line["event"], "clean")
        self.assertTrue(last_line.get("dry_run"), "log deve conter dry_run: true")


    # ── Seção 2: done atômico (write-ahead + fsync + verificação) ──

    @mock.patch("sac.store.shutil.move", side_effect=OSError("mock move error"))
    def test_finish_write_ahead_log(self, mock_move):
        mid = self.store.send("leader", "dev-1", "task", now=T0)
        self.store.next("dev-1")
        self.store.done("dev-1", mid, "feito", now=T0)
        log = (self.sac / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("done", log, "evento done deve estar no log mesmo se move falhar")
        self.assertIn(mid, log)

    @mock.patch("sac.store.shutil.move", side_effect=OSError("permission denied"))
    def test_finish_move_fails(self, mock_move):
        mid = self.store.send("leader", "dev-1", "task", now=T0)
        self.store.next("dev-1")
        result = self.store.done("dev-1", mid, "feito", now=T0)
        self.assertFalse(result)
        self.assertIn(mid, self.store.claimed("dev-1"), "msg deve permanecer em claimed")
        log = (self.sac / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("loop_error", log, "deve logar loop_error quando move falha")

    @mock.patch("sac.store.shutil.move", side_effect=lambda src, dst: None)
    def test_finish_move_orphan(self, mock_move):
        mid = self.store.send("leader", "dev-1", "task", now=T0)
        self.store.next("dev-1")
        result = self.store.done("dev-1", mid, "feito", now=T0)
        self.assertFalse(result)
        self.assertIn(mid, self.store.claimed("dev-1"), "msg deve permanecer em claimed")
        log = (self.sac / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("loop_error", log, "deve logar loop_error quando src persiste")

    def test_finish_success_verification(self):
        mid = self.store.send("leader", "dev-1", "task", now=T0)
        self.store.next("dev-1")
        result = self.store.done("dev-1", mid, "feito", now=T0)
        self.assertTrue(result)
        self.assertNotIn(mid, self.store.claimed("dev-1"))
        done_files = list((self.sac / "done" / "dev-1").glob("*.msg"))
        self.assertEqual(len(done_files), 1)
        log = (self.sac / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("done", log)
        self.assertIn(mid, log)

    # ── Seção 3: SAC_ROOT explícito ──

    def test_store_root_explicit(self):
        s = Store(Path("/tmp/test"))
        self.assertEqual(s.root, Path("/tmp/test/.sac"))

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_store_root_none_fallback(self):
        s = Store()
        self.assertEqual(s.root, Path.cwd() / ".sac")

    def test_store_root_explicit_preserves_path(self):
        s = Store(Path("/custom/path"))
        self.assertEqual(s.root, Path("/custom/path/.sac"))

    @mock.patch.dict(os.environ, {"SAC_ROOT": "/env/sac"}, clear=True)
    def test_store_root_env_used_when_no_explicit(self):
        s = Store()
        self.assertEqual(s.root, Path("/env/sac/.sac"))

    def test_store_root_explicit_overrides_env(self):
        with mock.patch.dict(os.environ, {"SAC_ROOT": "/env/sac"}, clear=True):
            s = Store(Path("/cli/path"))
        self.assertEqual(s.root, Path("/cli/path/.sac"),
                         "root explícito deve ter precedência sobre env")


if __name__ == "__main__":
    unittest.main()
