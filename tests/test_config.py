import tempfile
import unittest
from pathlib import Path

from sac.config import ConfigError, load_config

VALID = """
[session]
name = "sac-test"
notify_interval = 30
poke_stale_after = 120

[[agents]]
name = "leader"
command = "kimi"
args = ["--model", "k3"]
role = "leader"
prompt_file = "prompts/leader.md"

[[agents]]
name = "dev-1"
command = "opencode"
args = ["-m", "x/y"]
role = "aux"

[[loops]]
name = "dev-review"
sequence = ["leader", "dev-1"]
max_iterations = 3
"""


class LoadConfigTest(unittest.TestCase):
    def _load(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / "sac.toml"
        p.write_text(text, encoding="utf-8")
        return load_config(p)

    def test_valid_config(self):
        cfg = self._load(VALID)
        self.assertEqual(cfg.session_name, "sac-test")
        self.assertEqual(cfg.notify_interval, 30)
        self.assertEqual(cfg.poke_stale_after, 120)
        self.assertEqual(len(cfg.agents), 2)
        self.assertEqual(cfg.leader.name, "leader")
        self.assertEqual(cfg.agent("dev-1").command, "opencode")
        self.assertEqual(cfg.agent("dev-1").prompt_file, None)
        self.assertEqual(cfg.loops[0].max_iterations, 3)

    def test_defaults(self):
        cfg = self._load(VALID.replace("notify_interval = 30\n", "").replace("poke_stale_after = 120\n", ""))
        self.assertEqual(cfg.notify_interval, 30)
        self.assertEqual(cfg.poke_stale_after, 120)

    def test_no_leader_fails(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace('role = "leader"', 'role = "aux"'))

    def test_two_leaders_fail(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace('role = "aux"', 'role = "leader"'))

    def test_duplicate_names_fail(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace('name = "dev-1"', 'name = "leader"'))

    def test_invalid_role_fails(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace('role = "aux"', 'role = "chefe"'))

    def test_loop_unknown_agent_fails(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace('sequence = ["leader", "dev-1"]', 'sequence = ["leader", "fantasma"]'))

    def test_missing_file_fails(self):
        with self.assertRaises(ConfigError):
            load_config(Path("/tmp/nao-existe-sac.toml"))

    def test_agent_unknown_raises(self):
        cfg = self._load(VALID)
        with self.assertRaises(ConfigError):
            cfg.agent("fantasma")


if __name__ == "__main__":
    unittest.main()
