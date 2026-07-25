import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from sac.config import Config, load_config
from sac.init import (
    InitError, _collect_config, _generate_prompts, _generate_toml, _harness_note,
    _is_interactive, _valid_name, cmd_init,
)


def FakeInput(answers):
    it = iter(answers)
    def _input(prompt=""):
        return next(it)
    return _input


class InitTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_init_creates_sac_toml(self):
        inputs = [
            "sessao",         # session name
            "",               # socket (default ~/.sac/tmux.sock)
            "8",              # boot_wait
            "2",              # number of agents
            "leader",         # agent1 name
            "kimi",           # agent1 command
            "esteira/k3",     # agent1 model (role auto-assigned leader)
            "",               # agent1 boot_wait
            "dev-1",          # agent2 name
            "opencode",       # agent2 command
            "aux",            # agent2 role
            "opencode-go/deepseek-v4-flash",  # agent2 model
            "",               # agent2 boot_wait
            "n",              # no loops
        ]
        rc = cmd_init(stdin=FakeInput(inputs), stdout=lambda s: None, root=self.d, is_interactive=True)
        self.assertEqual(rc, 0)
        toml_path = self.d / "sac.toml"
        self.assertTrue(toml_path.exists(), "sac.toml deve ser criado")
        cfg = load_config(toml_path)
        self.assertEqual(cfg.session_name, "sessao")
        self.assertEqual(len(cfg.agents), 2)
        self.assertEqual(cfg.agents[0].name, "leader")
        self.assertEqual(cfg.agents[0].command, "kimi")
        self.assertEqual(cfg.agents[0].role, "leader")
        self.assertEqual(cfg.agents[1].name, "dev-1")
        self.assertEqual(cfg.agents[1].role, "aux")
        prompt_file = self.d / "prompts" / "leader.md"
        self.assertTrue(prompt_file.exists(), "prompt do leader deve ser criado")

    def test_init_no_tty(self):
        original = sys.stdin.isatty
        sys.stdin.isatty = lambda: False
        try:
            rc = cmd_init(stdin=lambda: "", stdout=lambda s: None, root=self.d, is_interactive=False)
            self.assertEqual(rc, 1)
        finally:
            sys.stdin.isatty = original

    def test_init_existing_config_aborts(self):
        (self.d / "sac.toml").write_text("", encoding="utf-8")
        rc = cmd_init(stdin=FakeInput(["n"]), stdout=lambda s: None, root=self.d, is_interactive=True)
        self.assertEqual(rc, 0)
        content = (self.d / "sac.toml").read_text(encoding="utf-8")
        self.assertEqual(content, "", "sac.toml não deve ser modificado")

    def test_validate_name_no_spaces(self):
        from sac.init import _ask, _valid_name
        called = []
        def fake_stdin():
            if not called:
                called.append(None)
                return "nome com espaco"
            return "nome-sem-espaco"
        result = _ask("Nome", "default", fake_stdin, lambda s: None, validate=_valid_name)
        self.assertEqual(result, "nome-sem-espaco")

    def test_valid_name_rejects_special_chars(self):
        self.assertFalse(_valid_name(""))
        self.assertFalse(_valid_name('foo"bar'))
        self.assertFalse(_valid_name('foo\\bar'))
        self.assertFalse(_valid_name("foo/bar"))
        self.assertFalse(_valid_name("foo..bar"))
        self.assertFalse(_valid_name("foo bar"))
        self.assertTrue(_valid_name("foo"))
        self.assertTrue(_valid_name("foo-bar"))
        self.assertTrue(_valid_name("foo_bar"))
        self.assertTrue(_valid_name("Foo123"))

    def test_prompt_template_leader(self):
        from sac.init import PROMPT_TEMPLATES
        tpl = PROMPT_TEMPLATES["leader"]
        self.assertIn("Papel: leader", tpl)
        self.assertIn("SAC_DONE", tpl)
        self.assertIn("sac done", tpl)
        self.assertIn("sac send", tpl)
        self.assertIn("{harness}", tpl)

    def test_prompt_template_aux(self):
        from sac.init import PROMPT_TEMPLATES
        tpl = PROMPT_TEMPLATES["aux"]
        self.assertIn("Papel: aux", tpl)
        self.assertIn("SAC_DONE", tpl)
        self.assertNotIn("delegar", tpl)

    def test_harness_note_kimi(self):
        from sac.config import AgentConfig
        from sac.init import KIMI_NOTE
        a = AgentConfig(name="l", command="kimi", args=[], role="leader")
        cfg = Config(session_name="t", agents=[a])
        note = _harness_note(cfg, a)
        self.assertEqual(note, KIMI_NOTE)

    def test_harness_note_opencode(self):
        from sac.config import AgentConfig
        from sac.init import OPENCODE_NOTE
        a = AgentConfig(name="d", command="opencode", args=[], role="aux")
        cfg = Config(session_name="t", agents=[a])
        note = _harness_note(cfg, a)
        self.assertEqual(note, OPENCODE_NOTE)

    def test_templates_agnosticos_sem_referencias_de_ambiente(self):
        # SAC é gerenciador de harness agnóstico: templates e exemplos gerados
        # não podem mencionar aliases/modelos de nenhum ambiente específico
        from sac.init import KIMI_NOTE, OPENCODE_NOTE, PROMPT_TEMPLATES
        import inspect
        import sac.init as init_mod
        fonte = inspect.getsource(init_mod)
        for ref in ("esteira/", "deepseek", "DeepSeek", "/home/"):
            self.assertNotIn(ref, KIMI_NOTE, f"KIMI_NOTE com referência de ambiente: {ref}")
            self.assertNotIn(ref, OPENCODE_NOTE, f"OPENCODE_NOTE com referência de ambiente: {ref}")
            self.assertNotIn(ref, PROMPT_TEMPLATES["leader"])
            self.assertNotIn(ref, PROMPT_TEMPLATES["aux"])
        self.assertNotIn("esteira/", fonte, "init.py (incl. exemplos do questionário) deve ser agnóstico")

    def test_init_args_separate_entries(self):
        inputs = [
            "test", "", "5", "1",
            "lead", "kimi", "esteira/k3", "",
            "n",
        ]
        d = Path(tempfile.mkdtemp())
        cmd_init(stdin=FakeInput(inputs), stdout=lambda s: None, root=d, is_interactive=True)
        cfg = load_config(d / "sac.toml")
        self.assertEqual(cfg.agents[0].args, ["--model", "esteira/k3"])

    def test_init_toml_roundtrip(self):
        inputs = [
            "rt-sess", "", "6", "2",
            "lead", "kimi", "k3", "",
            "dev1", "opencode", "aux", "deepseek-v4", "",
            "n",
        ]
        d = Path(tempfile.mkdtemp())
        rc = cmd_init(stdin=FakeInput(inputs), stdout=lambda s: None, root=d, is_interactive=True)
        self.assertEqual(rc, 0)
        cfg = load_config(d / "sac.toml")
        self.assertEqual(len(cfg.agents), 2)

    def test_init_eof_raises_clean_exit(self):
        def eof_stdin():
            raise EOFError("EOF")
        rc = cmd_init(stdin=eof_stdin, stdout=lambda s: None, root=self.d, is_interactive=True)
        self.assertEqual(rc, 1, "EOF no questionário deve retornar 1 sem traceback")

    def test_init_keyboard_interrupt_clean_exit(self):
        def kb_stdin():
            raise KeyboardInterrupt()
        rc = cmd_init(stdin=kb_stdin, stdout=lambda s: None, root=self.d, is_interactive=True)
        self.assertEqual(rc, 1, "Ctrl-C no questionário deve retornar 1 sem traceback")

    def test_init_eof_mid_collect_config(self):
        """EOF no meio do questionário (após algumas respostas) → saída limpa"""
        inputs = iter(["sessao", "", "8", "2"])
        def partial_stdin():
            try:
                return next(inputs)
            except StopIteration:
                raise EOFError("pipe esgotado")
        rc = cmd_init(stdin=partial_stdin, stdout=lambda s: None, root=self.d, is_interactive=True)
        self.assertEqual(rc, 1, "EOF no meio do questionário deve retornar 1 sem traceback")

    def test_init_rejects_invalid_name(self):
        d = Path(tempfile.mkdtemp())
        rc = cmd_init(
            stdin=FakeInput(["test", "", "5", "1", 'lead"bad', "lead-clean", "kimi", "", "", "n"]),
            stdout=lambda s: None, root=d, is_interactive=True,
        )
        self.assertEqual(rc, 0)
        cfg = load_config(d / "sac.toml")
        self.assertEqual(cfg.agents[0].name, "lead-clean")

    def test_init_prompts_ask_before_overwrite(self):
        d = Path(tempfile.mkdtemp())
        (d / "prompts").mkdir()
        (d / "prompts" / "leader.md").write_text("old content", encoding="utf-8")
        inputs = [
            "p-sess", "", "5", "1",
            "leader", "kimi", "", "",
            "n",  # loops
            "n",  # prompts: não sobrescrever
        ]
        rc = cmd_init(stdin=FakeInput(inputs), stdout=lambda s: None, root=d, is_interactive=True)
        self.assertEqual(rc, 0)
        content = (d / "prompts" / "leader.md").read_text(encoding="utf-8")
        self.assertEqual(content, "old content", "prompt não deve ser sobrescrito")


class InitWorkspaceTest(unittest.TestCase):
    def test_init_creates_complete_workspace(self):
        d = Path(tempfile.mkdtemp())
        inputs = [
            "sac-test",       # session
            "~/.sac-test/tmux.sock",  # socket
            "10",             # boot_wait
            "1",              # 1 agent
            "leader",         # name
            "kimi",           # command
            "k3",             # model (role auto-assigned)
            "",               # boot_wait
            "n",              # no loops
        ]
        rc = cmd_init(stdin=FakeInput(inputs), stdout=lambda s: None, root=d, is_interactive=True)
        self.assertEqual(rc, 0)

        sac_dir = d / ".sac"
        self.assertTrue((sac_dir / "inbox").is_dir(), "inbox/ deve existir")
        self.assertTrue((sac_dir / "claimed").is_dir(), "claimed/ deve existir")
        self.assertTrue((sac_dir / "done").is_dir(), "done/ deve existir")

        sock_path = Path("~/.sac-test/tmux.sock").expanduser()
        self.assertTrue(sock_path.parent.is_dir(), "diretorio do socket deve ser criado")

        cfg = load_config(d / "sac.toml")
        self.assertEqual(cfg.session_name, "sac-test")

        self.assertTrue((d / "prompts" / "leader.md").is_file())

    def test_init_without_socket_skips_mkdir(self):
        d = Path(tempfile.mkdtemp())
        inputs = [
            "no-sock",
            "",               # socket vazio
            "5",
            "1",
            "dev",
            "opencode",
            "",               # model vazio
            "",               # boot_wait
            "n",
        ]
        rc = cmd_init(stdin=FakeInput(inputs), stdout=lambda s: None, root=d, is_interactive=True)
        self.assertEqual(rc, 0)
        cfg = load_config(d / "sac.toml")
        self.assertIsNone(cfg.socket)


class BootWaitTest(unittest.TestCase):
    def test_boot_wait_elapsed_second_agent_sleeps_less(self):
        from unittest.mock import patch
        from sac.commands import cmd_up
        from sac.tmux import Tmux
        from tests.test_tmux import FakeRunner

        d = Path(tempfile.mkdtemp())
        config_toml = """
[session]
name = "sac-boot"
boot_wait = 10

[[agents]]
name = "leader"
command = "kimi"
role = "leader"
prompt_file = "prompts/leader.md"
boot_wait = 10.0

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"
prompt_file = "prompts/dev.md"
boot_wait = 10.0
"""
        (d / "sac.toml").write_text(config_toml, encoding="utf-8")
        (d / "prompts").mkdir(parents=True, exist_ok=True)
        (d / "prompts" / "leader.md").write_text("leader prompt")
        (d / "prompts" / "dev.md").write_text("dev prompt")
        cfg = load_config(d / "sac.toml")
        store = __import__("sac.store", fromlist=["Store"]).Store(d / ".sac")
        r = FakeRunner(outputs={("rc", "has-session"): 1, "list-windows": "leader\ndev-1\ndash\n"})
        t = Tmux("sac-boot", runner=r)

        fake_now = [1000.0, 1000.0, 1008.0]
        def monotonic():
            return fake_now.pop(0)
        with patch("sac.commands.time.sleep") as mock_sleep:
            with patch("sac.commands.time.monotonic", side_effect=monotonic):
                cmd_up(cfg, store, t, d, boot_wait=None)

        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list if c.args[0] > 0]
        self.assertGreaterEqual(len(sleep_calls), 2, "ambos agentes devem dormir")
        self.assertEqual(sleep_calls[0], 10, "leader dorme boot_wait cheio")
        self.assertLess(sleep_calls[1], 10, "segundo agente dorme menos pois tempo decorreu")


if __name__ == "__main__":
    unittest.main()
