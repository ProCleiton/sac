import contextlib
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from sac.cli import main, resolve_config_path
from sac.store import Store


@contextlib.contextmanager
def _cwd(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


@contextlib.contextmanager
def _sem_sac_config():
    with patch.dict(os.environ):
        os.environ.pop("SAC_CONFIG", None)
        yield

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
"""


class CliTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg_path = str(self.d / "sac.toml")

    def test_version_flag(self):
        from io import StringIO
        import sys
        from unittest.mock import patch
        buf = StringIO()
        with patch.object(sys, "stdout", buf):
            with self.assertRaises(SystemExit):
                main(["--version"])
        out = buf.getvalue()
        self.assertTrue(len(out) > 0, "--version imprime algo")
        self.assertNotIn("erro", out.lower())

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

    def test_run_command_removed(self):
        # v26b: `sac run` removido junto com os loops declarados
        err = StringIO()
        with patch.object(sys, "stderr", err):
            with self.assertRaises(SystemExit) as ctx:
                main(["--config", self.cfg_path, "run", "dev-review", "x"])
        self.assertEqual(ctx.exception.code, 2, "comando desconhecido → argparse exit 2")

    def test_config_com_loops_retorna_1_com_orientacao(self):
        cfg_loops = Path(tempfile.mkdtemp()) / "sac.toml"
        cfg_loops.write_text(VALID + '\n[[loops]]\nname = "x"\nsequence = ["leader"]\n',
                             encoding="utf-8")
        err = StringIO()
        with patch.object(sys, "stderr", err):
            rc = main(["--config", str(cfg_loops), "status"])
        self.assertEqual(rc, 1)
        self.assertIn("v26b", err.getvalue())

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


class ResolveConfigPathTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_flag_tem_precedencia_sobre_env(self):
        with patch.dict(os.environ, {"SAC_CONFIG": "/env.toml"}):
            self.assertEqual(resolve_config_path("/flag.toml"), Path("/flag.toml"))

    def test_env_tem_precedencia_sobre_diretorio(self):
        (self.d / ".sac").mkdir()
        (self.d / ".sac" / "sac.toml").write_text("x", encoding="utf-8")
        with _cwd(self.d), patch.dict(os.environ, {"SAC_CONFIG": "/env.toml"}):
            self.assertEqual(resolve_config_path(None), Path("/env.toml"))

    def test_config_oculto_preferido_ao_legado(self):
        (self.d / ".sac").mkdir()
        (self.d / ".sac" / "sac.toml").write_text("x", encoding="utf-8")
        (self.d / "sac.toml").write_text("x", encoding="utf-8")
        with _cwd(self.d), _sem_sac_config():
            self.assertEqual(resolve_config_path(None), Path(".sac") / "sac.toml")

    def test_legado_so_na_raiz_e_ignorado(self):
        (self.d / "sac.toml").write_text("x", encoding="utf-8")
        with _cwd(self.d), _sem_sac_config():
            self.assertIsNone(resolve_config_path(None),
                              "fallback legado removido na v25")

    def test_nenhum_config_retorna_none(self):
        with _cwd(self.d), _sem_sac_config():
            self.assertIsNone(resolve_config_path(None))


class ConfigDiscoveryCliTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_sem_config_erro_claro_e_sugere_init(self):
        err = StringIO()
        with _cwd(self.d), _sem_sac_config():
            with patch.object(sys, "stderr", err):
                rc = main(["status"])
        self.assertEqual(rc, 1)
        self.assertIn("sac init", err.getvalue())
        self.assertIn(".sac/sac.toml", err.getvalue())

    def test_comando_usa_config_oculto(self):
        (self.d / ".sac").mkdir()
        (self.d / ".sac" / "sac.toml").write_text(VALID, encoding="utf-8")
        with _cwd(self.d), _sem_sac_config():
            rc = main(["send", "dev-1", "tarefa"])
        self.assertEqual(rc, 0)
        store = Store(self.d)
        self.assertEqual(len(store.pending("dev-1")), 1,
                         "estado deve ficar em <workspace>/.sac, não em .sac/.sac")

    def test_comando_com_so_legado_erro_e_orienta_migracao(self):
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        err = StringIO()
        with _cwd(self.d), _sem_sac_config():
            with patch.object(sys, "stderr", err):
                rc = main(["status"])
        self.assertEqual(rc, 1, "legado na raiz não é mais carregado")
        self.assertIn("fallback removido", err.getvalue())
        self.assertIn("mv sac.toml .sac/", err.getvalue())

    def test_uninstall_via_cli(self):
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        (self.d / "prompts").mkdir()
        (self.d / ".sac").mkdir()
        with _cwd(self.d), _sem_sac_config():
            # workspace só-legado: config não é carregado (v25) — token cai para "sac"
            with patch("builtins.input", return_value="sac"):
                rc = main(["uninstall"])
        self.assertEqual(rc, 0)
        self.assertFalse((self.d / "sac.toml").exists())
        self.assertFalse((self.d / "prompts").exists())
        self.assertFalse((self.d / ".sac").exists())
