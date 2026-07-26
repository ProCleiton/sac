"""v27 (ampliada): adapters data-driven de injeção por harness.

Cobre os scenarios da requirement "Injeção dos plugins nos agentes":
kimi --skills-dir (só com superpowers), opencode/mimo --pure, claude
--bare --plugin-dir, copilot COPILOT_SKILLS_DIRS, codex -c skills.config,
desconhecido sem args/env extras. Sem tmux real, sem rede.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sac.commands import _harness_cmd, _session_env, cmd_up
from sac.config import AgentConfig, load_config
from sac.harness_adapters import ADAPTERS, harness_args, harness_env
from sac.store import Store
from sac.tmux import Tmux
from tests.test_tmux import FakeRunner

VALID_COPILOT = """
[session]
name = "sac-test"

[[agents]]
name = "leader"
command = "copilot"
role = "leader"
prompt_file = "prompts/leader.md"

[[agents]]
name = "dev-1"
command = "gemini"
role = "aux"
prompt_file = "prompts/dev.md"
"""


def _agent(command, args=()):
    return AgentConfig(name="a", command=command, args=list(args), role="aux")


class AdapterBase(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())

    def _instala_superpowers(self):
        (self.home / "plugins" / "superpowers" / "skills").mkdir(parents=True)

    @property
    def skills(self):
        return str(self.home / "plugins" / "superpowers" / "skills")

    @property
    def plugin(self):
        return str(self.home / "plugins" / "superpowers")


class AdapterTableTest(AdapterBase):
    def test_tabela_contem_os_harnesses_canonicos(self):
        for h in ("kimi", "opencode", "mimo", "claude", "copilot", "codex"):
            self.assertIn(h, ADAPTERS)

    def test_kimi_skills_dir_so_com_superpowers(self):
        self.assertEqual(harness_args("kimi", self.home), [],
                         "sem superpowers instalado, nenhum arg extra")
        self._instala_superpowers()
        self.assertEqual(harness_args("kimi", self.home),
                         ["--skills-dir", self.skills])

    def test_opencode_e_mimo_pure_sempre(self):
        for h in ("opencode", "mimo"):
            self.assertEqual(harness_args(h, self.home), ["--pure"],
                             f"{h}: --pure mesmo sem plugins instalados")
            self.assertEqual(harness_env(h, self.home), {})

    def test_claude_bare_e_plugin_dir_so_com_superpowers(self):
        self.assertEqual(harness_args("claude", self.home), [])
        self._instala_superpowers()
        args = harness_args("claude", self.home)
        self.assertEqual(args, ["--bare", "--plugin-dir", self.plugin])

    def test_copilot_env_skills_dirs_so_com_superpowers(self):
        self.assertEqual(harness_env("copilot", self.home), {})
        self.assertEqual(harness_args("copilot", self.home), [])
        self._instala_superpowers()
        self.assertEqual(harness_env("copilot", self.home),
                         {"COPILOT_SKILLS_DIRS": self.skills})

    def test_codex_config_skills_so_com_superpowers(self):
        self.assertEqual(harness_args("codex", self.home), [])
        self._instala_superpowers()
        args = harness_args("codex", self.home)
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0], "-c")
        self.assertEqual(args[1],
                         f'skills.config=[{{path="{self.skills}",enabled=true}}]')

    def test_harness_desconhecido_sem_args_nem_env(self):
        self._instala_superpowers()
        for h in ("gemini", "aider", "goose", "qualquer-coisa"):
            self.assertEqual(harness_args(h, self.home), [], h)
            self.assertEqual(harness_env(h, self.home), {}, h)


class HarnessCmdAdapterTest(AdapterBase):
    """_harness_cmd migrado para a tabela — sem dupla implementação."""

    def test_mimo_ganha_pure(self):
        cmd = _harness_cmd(_agent("mimo"), home=self.home)
        self.assertEqual(cmd, ["mimo", "--pure"])

    def test_claude_ganha_bare_e_plugin_dir(self):
        self._instala_superpowers()
        cmd = _harness_cmd(_agent("claude", ["--model", "sonnet"]), home=self.home)
        self.assertEqual(cmd, ["claude", "--model", "sonnet",
                               "--bare", "--plugin-dir", self.plugin])

    def test_codex_ganha_config_de_skills(self):
        self._instala_superpowers()
        cmd = _harness_cmd(_agent("codex"), home=self.home)
        self.assertEqual(cmd[:3],
                         ["codex", "-c",
                          f'skills.config=[{{path="{self.skills}",enabled=true}}]'])

    def test_kimi_sem_superpowers_sem_skills_dir(self):
        cmd = _harness_cmd(_agent("kimi"), home=self.home)
        self.assertNotIn("--skills-dir", cmd)

    def test_pure_nao_duplica_nos_args(self):
        for h in ("opencode", "mimo"):
            cmd = _harness_cmd(_agent(h, ["--pure"]), home=self.home)
            self.assertEqual(cmd.count("--pure"), 1, h)


class SessionEnvAdapterTest(AdapterBase):
    def setUp(self):
        super().setUp()
        self.d = Path(tempfile.mkdtemp())
        self.store = Store(self.d / ".sac")

    def test_copilot_recebe_env_no_pane(self):
        self._instala_superpowers()
        with patch.dict(os.environ, {"SAC_HOME": str(self.home), "PATH": "/usr/bin"}):
            env = _session_env(self.store, None, "dev", command="copilot")
        self.assertEqual(env["COPILOT_SKILLS_DIRS"], self.skills)
        self.assertTrue(env["PATH"].startswith(str(self.home / "bin") + os.pathsep))

    def test_copilot_sem_superpowers_sem_env_extra(self):
        with patch.dict(os.environ, {"SAC_HOME": str(self.home), "PATH": "/usr/bin"}):
            env = _session_env(self.store, None, "dev", command="copilot")
        self.assertNotIn("COPILOT_SKILLS_DIRS", env)

    def test_desconhecido_recebe_so_path(self):
        self._instala_superpowers()
        with patch.dict(os.environ, {"SAC_HOME": str(self.home), "PATH": "/usr/bin"}):
            env = _session_env(self.store, None, "dev", command="gemini")
        self.assertNotIn("COPILOT_SKILLS_DIRS", env)
        self.assertTrue(env["PATH"].startswith(str(self.home / "bin") + os.pathsep))


class UpAdapterEnvTest(AdapterBase):
    """Scenario copilot: env extra aplicado no pane criado pelo `sac up`."""

    def setUp(self):
        super().setUp()
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID_COPILOT, encoding="utf-8")
        (self.d / "prompts").mkdir()
        (self.d / "prompts" / "leader.md").write_text("líder", encoding="utf-8")
        (self.d / "prompts" / "dev.md").write_text("dev", encoding="utf-8")
        self.cfg = load_config(self.d / "sac.toml")
        self.store = Store(self.d / ".sac")
        self.runner = FakeRunner(outputs={("rc", "has-session"): 1,
                                          "list-windows": "leader\ndev-1\ndash\n"})
        self.tmux = Tmux("sac-test", runner=self.runner)

    def _split(self, agente):
        return str(next(c for c in self.runner.calls
                        if c[1] == "split-window" and f"SAC_AGENT={agente}" in str(c)))

    def test_up_copilot_recebe_env_e_gemini_nao(self):
        self._instala_superpowers()
        with patch.dict(os.environ, {"SAC_HOME": str(self.home), "PATH": "/usr/bin"}):
            rc = cmd_up(self.cfg, self.store, self.tmux, self.d, boot_wait=0)
        self.assertEqual(rc, 0)
        copilot = self._split("leader")
        self.assertIn(f"COPILOT_SKILLS_DIRS={self.skills}", copilot)
        gemini = self._split("dev-1")
        self.assertNotIn("COPILOT_SKILLS_DIRS", gemini,
                         "harness sem adapter: só PATH + ponteiro no contrato")
        self.assertIn(f"PATH={self.home / 'bin'}", gemini)


if __name__ == "__main__":
    unittest.main()
