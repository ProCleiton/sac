import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sac.cli import main
from sac.store import Store

VALID = """
[session]
name = "sac-cli-test"

[[agents]]
name = "leader"
command = "kimi"
role = "leader"

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"

[[loops]]
name = "dev-review"
sequence = ["leader", "dev-1"]
"""


class CliTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg_path = str(self.d / "sac.toml")

    def test_send_via_cli(self):
        rc = main(["--config", self.cfg_path, "send", "dev-1", "faça X"])
        self.assertEqual(rc, 0)
        store = Store(self.d)
        self.assertEqual(len(store.pending("dev-1")), 1)

    def test_send_with_agent_env_sets_sender(self):
        with patch.dict(os.environ, {"SAC_AGENT": "leader"}):
            rc = main(["--config", self.cfg_path, "send", "dev-1", "tarefa"])
        self.assertEqual(rc, 0)
        store = Store(self.d)
        pending = store.pending("dev-1")
        self.assertEqual(len(pending), 1)
        msg = store.next("dev-1")
        self.assertEqual(msg.sender, "leader")

    def test_send_without_env_sets_sender_user(self):
        with patch.dict(os.environ, {}, clear=True):
            rc = main(["--config", self.cfg_path, "send", "dev-1", "tarefa"])
        self.assertEqual(rc, 0)
        store = Store(self.d)
        msg = store.next("dev-1")
        self.assertEqual(msg.sender, "user")

    def test_next_without_agent_env_returns_2(self):
        with patch.dict(os.environ, {}, clear=True):
            rc = main(["--config", self.cfg_path, "next"])
        self.assertEqual(rc, 2)

    def test_run_via_cli(self):
        rc = main(["--config", self.cfg_path, "run", "dev-review", "implementar X"])
        self.assertEqual(rc, 0)
        store = Store(self.d)
        self.assertEqual(len(store.pending("leader")), 1)

    def test_run_unknown_loop_returns_1(self):
        rc = main(["--config", self.cfg_path, "run", "fantasma", "x"])
        self.assertEqual(rc, 1)

    def test_missing_config_returns_1(self):
        rc = main(["--config", "/tmp/nao-existe.toml", "status"])
        self.assertEqual(rc, 1)

    def test_notify_once(self):
        rc = main(["--config", self.cfg_path, "notify", "--once"])
        self.assertEqual(rc, 0)

    def test_inject_unknown_agent_returns_1(self):
        rc = main(["--config", self.cfg_path, "inject", "fantasma"])
        self.assertEqual(rc, 1)

    def test_sidebar_via_cli(self):
        rc = main(["--config", self.cfg_path, "sidebar"])
        self.assertEqual(rc, 0)

    def test_inject_known_agent_returns_0(self):
        # sem sessão tmux, o inject não encontra pane → rc 1 (mas o parsing funciona)
        rc = main(["--config", self.cfg_path, "inject", "dev-1"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()


class SacRootWiringTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg_path = str(self.d / "sac.toml")

    def test_inject_project_root_eh_dir_do_config_mesmo_com_sac_root(self):
        with patch("sac.cli.cmd_inject") as m:
            m.return_value = 0
            rc = main(["--config", self.cfg_path, "--sac-root", "/tmp/outra-fila",
                       "inject", "dev-1"])
        self.assertEqual(rc, 0)
        self.assertEqual(m.call_args[0][2], self.d,
                         "project_root deve ser o dir do config, não o --sac-root")

    def test_up_project_root_eh_dir_do_config_mesmo_com_sac_root(self):
        with patch("sac.cli.cmd_up") as m:
            m.return_value = 0
            rc = main(["--config", self.cfg_path, "--sac-root", "/tmp/outra-fila", "up"])
        self.assertEqual(rc, 0)
        self.assertEqual(m.call_args[0][3], self.d,
                         "project_root deve ser o dir do config, não o --sac-root")

    def test_kill_project_root_eh_dir_do_config_mesmo_com_sac_root(self):
        with patch("sac.cli.cmd_kill") as m:
            m.return_value = 0
            rc = main(["--config", self.cfg_path, "--sac-root", "/tmp/outra-fila",
                       "kill", "dev-1"])
        self.assertEqual(rc, 0)
        self.assertEqual(m.call_args[0][3], self.d,
                         "project_root deve ser o dir do config, não o --sac-root")

    def test_config_default_honra_sac_config_env(self):
        # Sem --config e com SAC_CONFIG definido: usa o caminho da env,
        # mesmo sem sac.toml no cwd
        with patch.dict(os.environ, {"SAC_CONFIG": self.cfg_path}):
            rc = main(["status"])
        self.assertEqual(rc, 0)

    def test_config_explicito_tem_precedencia_sobre_sac_config(self):
        with patch.dict(os.environ, {"SAC_CONFIG": "/caminho/inexistente.toml"}):
            rc = main(["--config", self.cfg_path, "status"])
        self.assertEqual(rc, 0)
