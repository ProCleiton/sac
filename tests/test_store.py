import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sac.store import Store, StoreError

T0 = datetime(2026, 7, 24, 10, 0, 0)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.store = Store(self.root)

    def test_send_creates_file_and_returns_id(self):
        mid = self.store.send("leader", "dev-1", "faça X", now=T0)
        self.assertEqual(mid, "20260724-100000-001-from-leader")
        files = list((self.root / "inbox" / "dev-1").glob("*.msg"))
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
        done_files = list((self.root / "done" / "dev-1").glob("*.msg"))
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
        lines = (self.root / "log.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        self.assertEqual(first["event"], "send")
        self.assertEqual(first["ts"], "2026-07-24T10:00:00")
        self.assertEqual(first["to"], "dev-1")


if __name__ == "__main__":
    unittest.main()
