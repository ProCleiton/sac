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
        self.assertEqual(cfg.boot_wait, 8)
        self.assertEqual(len(cfg.agents), 2)
        self.assertEqual(cfg.leader.name, "leader")
        self.assertEqual(cfg.agent("dev-1").command, "opencode")
        self.assertEqual(cfg.agent("dev-1").prompt_file, None)

    def test_defaults(self):
        cfg = self._load(VALID.replace("notify_interval = 30\n", "").replace("poke_stale_after = 120\n", ""))
        self.assertEqual(cfg.notify_interval, 30)
        self.assertEqual(cfg.poke_stale_after, 120)
        self.assertEqual(cfg.boot_wait, 8)

    def test_boot_wait_custom(self):
        cfg = self._load(VALID.replace("name = \"sac-test\"", "name = \"sac-test\"\nboot_wait = 3"))
        self.assertEqual(cfg.boot_wait, 3)

    def test_session_size_defaults(self):
        cfg = self._load(VALID)
        self.assertEqual(cfg.session_width, 220)
        self.assertEqual(cfg.session_height, 50)

    def test_session_size_custom(self):
        cfg = self._load(VALID.replace("name = \"sac-test\"", "name = \"sac-test\"\nwidth = 180\nheight = 40"))
        self.assertEqual(cfg.session_width, 180)
        self.assertEqual(cfg.session_height, 40)

    def test_session_size_invalid_string(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace("name = \"sac-test\"", "name = \"sac-test\"\nwidth = \"largo\""))

    def test_session_size_not_positive(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace("name = \"sac-test\"", "name = \"sac-test\"\nheight = -1"))

    def test_config_default_boot_wait_8(self):
        cfg = self._load(VALID.replace("notify_interval = 30\n", "").replace("poke_stale_after = 120\n", ""))
        self.assertEqual(cfg.boot_wait, 8, "default global deve ser 8")

    def test_config_agent_boot_wait(self):
        text = VALID + '\n[[agents]]\nname = "slow"\ncommand = "opencode"\nrole = "aux"\nboot_wait = 12\n'
        cfg = self._load(text)
        self.assertEqual(cfg.agent("slow").boot_wait, 12)
        self.assertIsNone(cfg.agent("dev-1").boot_wait, "agente sem campo herda None")

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

    def test_config_com_loops_falha_com_orientacao(self):
        # v26b: [[loops]] removido — config com a seção deve falhar orientando a remoção
        text = VALID + '\n[[loops]]\nname = "dev-review"\nsequence = ["leader", "dev-1"]\n'
        with self.assertRaises(ConfigError) as ctx:
            self._load(text)
        msg = str(ctx.exception)
        self.assertIn("loops", msg)
        self.assertIn("v26b", msg)
        self.assertIn("remova", msg)
        self.assertIn("contrato do líder", msg)

    def test_config_sem_loops_carrega_normal(self):
        cfg = self._load(VALID)
        self.assertEqual(cfg.session_name, "sac-test")

    def test_missing_file_fails(self):
        with self.assertRaises(ConfigError):
            load_config(Path("/tmp/nao-existe-sac.toml"))

    def test_agent_unknown_raises(self):
        cfg = self._load(VALID)
        with self.assertRaises(ConfigError):
            cfg.agent("fantasma")

    def test_agent_boot_wait_invalid_string(self):
        text = VALID + '\n[[agents]]\nname = "slow"\ncommand = "opencode"\nrole = "aux"\nboot_wait = "oito"\n'
        with self.assertRaises(ConfigError):
            self._load(text)

    def test_agent_boot_wait_negative(self):
        text = VALID + '\n[[agents]]\nname = "slow"\ncommand = "opencode"\nrole = "aux"\nboot_wait = -1\n'
        with self.assertRaises(ConfigError):
            self._load(text)

    def test_agent_boot_wait_zero(self):
        text = VALID + '\n[[agents]]\nname = "fast"\ncommand = "kimi"\nrole = "aux"\nboot_wait = 0\n'
        cfg = self._load(text)
        self.assertEqual(cfg.agent("fast").boot_wait, 0)


if __name__ == "__main__":
    unittest.main()


class SocketConfigTest(unittest.TestCase):
    def test_socket_parsed_and_expanded(self):
        d = tempfile.mkdtemp()
        p = Path(d) / "sac.toml"
        p.write_text(VALID.replace('name = "sac-test"', 'name = "sac-test"\nsocket = "~/.sac/tmux.sock"'), encoding="utf-8")
        cfg = load_config(p)
        self.assertEqual(cfg.socket, str(Path("~/.sac/tmux.sock").expanduser()))

    def test_socket_default_none(self):
        d = tempfile.mkdtemp()
        p = Path(d) / "sac.toml"
        p.write_text(VALID, encoding="utf-8")
        self.assertIsNone(load_config(p).socket)


class SessionRootTest(unittest.TestCase):
    def _load(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / "sac.toml"
        p.write_text(text, encoding="utf-8")
        return load_config(p)

    def test_session_root_parsed(self):
        text = VALID.replace('name = "sac-test"', 'name = "sac-test"\nroot = "/custom/path"')
        cfg = self._load(text)
        self.assertEqual(cfg.root, "/custom/path")

    def test_session_root_relative_rejected(self):
        text = VALID.replace('name = "sac-test"', 'name = "sac-test"\nroot = "relative/path"')
        with self.assertRaises(ConfigError):
            self._load(text)

    def test_session_root_default_none(self):
        cfg = self._load(VALID)
        self.assertIsNone(cfg.root)


class PokeEscalateAfterTest(unittest.TestCase):
    def _load(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / "sac.toml"
        p.write_text(text, encoding="utf-8")
        return load_config(p)

    def test_default_3(self):
        cfg = self._load(VALID)
        self.assertEqual(cfg.poke_escalate_after, 3, "default deve ser 3")

    def test_from_toml(self):
        text = VALID.replace("poke_stale_after = 120",
                             "poke_stale_after = 120\npoke_escalate_after = 5")
        cfg = self._load(text)
        self.assertEqual(cfg.poke_escalate_after, 5)

    def test_rejects_less_than_1(self):
        text = VALID.replace("poke_stale_after = 120",
                             "poke_stale_after = 120\npoke_escalate_after = 0")
        with self.assertRaises(ConfigError):
            self._load(text)


WINDOWS_VALID = """
[session]
name = "sac-test"

[[agents]]
name = "leader"
command = "kimi"
role = "leader"

[[agents]]
name = "dev-1"
command = "opencode"

[[agents]]
name = "auditor"
command = "kimi"

[windows]
main = "leader"
trabalho = "dev-1,auditor"
"""


class WindowsConfigTest(unittest.TestCase):
    def _load(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / "sac.toml"
        p.write_text(text, encoding="utf-8")
        return load_config(p)

    def test_windows_valido_ordem_preservada(self):
        cfg = self._load(WINDOWS_VALID)
        self.assertEqual(list(cfg.windows), ["main", "trabalho"])
        self.assertEqual(cfg.windows["trabalho"], "dev-1,auditor")

    def test_windows_ausente_vazio(self):
        cfg = self._load(VALID)
        self.assertEqual(cfg.windows, {})

    def test_windows_agente_desconhecido(self):
        with self.assertRaises(ConfigError):
            self._load(WINDOWS_VALID.replace('trabalho = "dev-1,auditor"',
                                             'trabalho = "dev-1,fantasma"'))

    def test_windows_agente_duplicado(self):
        with self.assertRaises(ConfigError):
            self._load(WINDOWS_VALID.replace('trabalho = "dev-1,auditor"',
                                             'trabalho = "leader,dev-1,auditor"'))

    def test_windows_agente_ausente_dos_specs(self):
        with self.assertRaises(ConfigError):
            self._load(WINDOWS_VALID.replace('trabalho = "dev-1,auditor"',
                                             'trabalho = "dev-1"'))
