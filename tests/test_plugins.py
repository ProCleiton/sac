"""v27: plugins canônicos (superpowers, RTK, openspec) gerenciados pelo SAC.

Zero rede, zero git real: subprocess.run é substituído por FakeRun e
SAC_HOME aponta para diretório temporário.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sac.config import AgentConfig
from sac.plugins_manifest import PLUGINS, bin_dir, plugin_dir, sac_home


def _ref(nome):
    return next(p["ref"] for p in PLUGINS if p["nome"] == nome)


class FakeRun:
    """subprocess.run fake: registra chamadas e materializa artefatos locais."""

    def __init__(self, rc=0, describe=None, latest_tag=None):
        self.calls: list[list[str]] = []
        self.rc = rc
        self.describe = describe      # tag retornada por `git describe --tags --exact-match`
        self.latest_tag = latest_tag  # tag retornada por `git ls-remote`

    def __call__(self, cmd, **kw):
        cmd = [str(c) for c in cmd]
        self.calls.append(cmd)
        rc, out = self.rc, ""
        if cmd[0] == "git" and cmd[1] == "clone":
            if rc == 0:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
        elif cmd[0] == "git" and cmd[1] == "ls-remote":
            if rc == 0 and self.latest_tag:
                out = f"deadbeef\trefs/tags/{self.latest_tag}\n"
        elif cmd[0] == "git" and cmd[1] == "-C":
            sub = cmd[3]
            if sub == "describe":
                if rc == 0 and self.describe is not None:
                    out = self.describe + "\n"
                else:
                    rc = 1  # sem tag exata → cai no rev-parse
            elif sub == "rev-parse":
                out = "abc1234\n"
        elif cmd[0] == "curl":
            if rc == 0:
                import io
                import tarfile
                dest = Path(cmd[cmd.index("-o") + 1])
                with tarfile.open(dest, "w:gz") as tf:
                    data = b"bin-fake"
                    info = tarfile.TarInfo("rtk")
                    info.size = len(data)
                    info.mode = 0o755
                    tf.addfile(info, io.BytesIO(data))
        elif cmd[0] == "npm":
            if rc == 0:
                prefix = Path(cmd[cmd.index("--prefix") + 1])
                (prefix / "bin").mkdir(parents=True, exist_ok=True)
                (prefix / "bin" / "openspec").write_text("x", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, rc, stdout=out, stderr="")

    def comandos(self, *prefixo):
        return [c for c in self.calls if tuple(c[:len(prefixo)]) == prefixo]


def _instala_clone(home, nome):
    d = plugin_dir(home, next(p for p in PLUGINS if p["nome"] == nome))
    d.mkdir(parents=True, exist_ok=True)
    return d


class ManifestTest(unittest.TestCase):
    def test_manifest_contem_os_3_canonicos(self):
        nomes = {p["nome"] for p in PLUGINS}
        self.assertEqual(nomes, {"superpowers", "rtk", "openspec"})
        for p in PLUGINS:
            self.assertIn(p["tipo"], ("skills", "cli-binary", "cli-npm"))
            self.assertTrue(p["repo"].startswith("https://github.com/"), p)
            self.assertTrue(p["ref"], p)

    def test_tipos_e_repos_corretos(self):
        por_nome = {p["nome"]: p for p in PLUGINS}
        self.assertEqual(por_nome["superpowers"]["tipo"], "skills")
        self.assertIn("obra/superpowers", por_nome["superpowers"]["repo"])
        self.assertEqual(por_nome["rtk"]["tipo"], "cli-binary")
        self.assertIn("rtk-ai/rtk", por_nome["rtk"]["repo"])
        self.assertEqual(por_nome["openspec"]["tipo"], "cli-npm")
        self.assertIn("Fission-AI/OpenSpec", por_nome["openspec"]["repo"])

    def test_sac_home_default_e_sobrescrita_por_env(self):
        env_sem = {k: v for k, v in os.environ.items() if k != "SAC_HOME"}
        self.assertEqual(sac_home(env_sem), Path.home() / ".sac")
        self.assertEqual(sac_home({"SAC_HOME": "/tmp/sac-x"}), Path("/tmp/sac-x"))
        with patch.dict(os.environ, {"SAC_HOME": "/tmp/sac-y"}):
            self.assertEqual(sac_home(), Path("/tmp/sac-y"))


class PluginsInstallTest(unittest.TestCase):
    def setUp(self):
        from sac.plugins import cmd_plugins
        self.cmd_plugins = cmd_plugins
        self.home = Path(tempfile.mkdtemp())
        self.saida = []

    def _run(self, sub, fake, **kw):
        self.saida = []
        kw.setdefault("home", self.home)
        kw.setdefault("stdout", self.saida.append)
        kw.setdefault("run", fake)
        rc = self.cmd_plugins(sub, **kw)
        return rc, "\n".join(self.saida)

    def test_install_clona_na_ref_e_materializa_bins(self):
        fake = FakeRun()
        rc, out = self._run("install", fake)
        self.assertEqual(rc, 0, out)
        for p in PLUGINS:
            clones = fake.comandos("git", "clone")
            self.assertTrue(any(p["repo"] in c for c in clones), f"sem clone de {p['nome']}")
            checkouts = fake.comandos("git", "-C", str(plugin_dir(self.home, p)), "checkout")
            self.assertTrue(any(p["ref"] in c for c in checkouts),
                            f"sem checkout da ref pinada de {p['nome']}")
        self.assertTrue((bin_dir(self.home) / "rtk").exists(), "bin rtk materializado")
        self.assertTrue((bin_dir(self.home) / "openspec").exists(), "shim openspec materializado")
        shim = (bin_dir(self.home) / "openspec").read_text(encoding="utf-8")
        self.assertIn("node_modules/.bin/openspec", shim, "shim aponta para o bin real do npm")
        self.assertTrue(fake.comandos("curl"), "rtk vem do asset do release (curl)")
        curl = fake.comandos("curl")[0]
        self.assertIn("releases/download/" + _ref("rtk"), " ".join(curl))
        npm = fake.comandos("npm", "install")
        self.assertTrue(npm, "openspec via npm install --prefix")
        self.assertIn("--prefix", npm[0])
        self.assertTrue(any("@fission-ai/openspec@" in a for a in npm[0]))

    def test_install_idempotente_nao_reclona(self):
        for p in PLUGINS:
            _instala_clone(self.home, p["nome"])
        (bin_dir(self.home)).mkdir(parents=True)
        (bin_dir(self.home) / "rtk").write_text("x", encoding="utf-8")
        (bin_dir(self.home) / "openspec").write_text("x", encoding="utf-8")
        skills = plugin_dir(self.home, PLUGINS[0]) / "skills"
        skills.mkdir(parents=True)
        # cada clone já está na ref pinada: describe retorna a ref de cada plugin
        refs = {p["nome"]: p["ref"] for p in PLUGINS}
        fake_atual = FakeRun()
        chamadas = []

        def run(cmd, **kw):
            cmd = [str(c) for c in cmd]
            chamadas.append(cmd)
            if cmd[:2] == ["git", "-C"] and cmd[3] == "describe":
                nome = Path(cmd[2]).name
                return subprocess.CompletedProcess(cmd, 0, stdout=refs[nome] + "\n", stderr="")
            return fake_atual(cmd, **kw)

        rc, out = self._run("install", None, run=run)
        self.assertEqual(rc, 0, out)
        self.assertFalse([c for c in chamadas if c[:2] == ["git", "clone"]],
                         "nada é reclonado quando já instalado na ref")
        self.assertFalse(fake_atual.comandos("curl"), "bin não é re-baixado")
        self.assertFalse(fake_atual.comandos("npm"), "npm não roda de novo")

    def test_install_sem_rede_erro_claro_e_exit_1(self):
        fake = FakeRun(rc=1)
        rc, out = self._run("install", fake)
        self.assertEqual(rc, 1)
        self.assertIn("erro", out)
        self.assertIn("rede", out)


class PluginsUpdateTest(unittest.TestCase):
    def setUp(self):
        from sac.plugins import cmd_plugins
        self.cmd_plugins = cmd_plugins
        self.home = Path(tempfile.mkdtemp())
        self.saida = []

    def _run(self, sub, fake, **kw):
        self.saida = []
        kw.setdefault("home", self.home)
        kw.setdefault("stdout", self.saida.append)
        kw.setdefault("run", fake)
        rc = self.cmd_plugins(sub, **kw)
        return rc, "\n".join(self.saida)

    def test_update_faz_fetch_e_checkout_da_ref(self):
        for p in PLUGINS:
            _instala_clone(self.home, p["nome"])
        fake = FakeRun()
        rc, out = self._run("update", fake)
        self.assertEqual(rc, 0, out)
        for p in PLUGINS:
            d = str(plugin_dir(self.home, p))
            self.assertTrue(fake.comandos("git", "-C", d, "fetch"),
                            f"sem fetch em {p['nome']}")
            checkouts = fake.comandos("git", "-C", d, "checkout")
            self.assertTrue(any(p["ref"] in c for c in checkouts),
                            f"sem checkout da ref pinada em {p['nome']}")
        self.assertTrue(fake.comandos("curl"), "update re-materializa o bin do rtk")
        self.assertTrue(fake.comandos("npm"), "update re-materializa o openspec")

    def test_update_check_nao_altera_nada(self):
        for p in PLUGINS:
            _instala_clone(self.home, p["nome"])
        antes = {str(p) for p in self.home.rglob("*")}
        fake = FakeRun(latest_tag="v9.9.9")
        rc, out = self._run("update", fake, check=True)
        self.assertEqual(rc, 0, out)
        self.assertIn(_ref("rtk"), out, "mostra a ref pinada")
        self.assertIn("v9.9.9", out, "mostra a tag mais recente do upstream")
        self.assertFalse(fake.comandos("git", "clone"))
        self.assertFalse([c for c in fake.calls if "fetch" in c or "checkout" in c])
        self.assertFalse(fake.comandos("curl"))
        self.assertFalse(fake.comandos("npm"))
        depois = {str(p) for p in self.home.rglob("*")}
        self.assertEqual(antes, depois, "--check não pode alterar arquivo algum")

    def test_update_check_sem_rede_exit_1(self):
        fake = FakeRun(rc=1)
        rc, out = self._run("update", fake, check=True)
        self.assertEqual(rc, 1)
        self.assertIn("rede", out)


class PluginsStatusTest(unittest.TestCase):
    def setUp(self):
        from sac.plugins import cmd_plugins
        self.cmd_plugins = cmd_plugins
        self.home = Path(tempfile.mkdtemp())
        self.saida = []

    def test_status_reporta_instalado_ref_e_bin(self):
        sp = _instala_clone(self.home, "superpowers")
        (sp / "skills").mkdir()
        refs = {"superpowers": _ref("superpowers")}

        def run(cmd, **kw):
            cmd = [str(c) for c in cmd]
            if cmd[:2] == ["git", "-C"] and cmd[3] == "describe":
                return subprocess.CompletedProcess(
                    cmd, 0, stdout=refs[Path(cmd[2]).name] + "\n", stderr="")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

        rc = self.cmd_plugins("status", home=self.home, stdout=self.saida.append, run=run)
        out = "\n".join(self.saida)
        self.assertEqual(rc, 0, out)
        self.assertIn("superpowers", out)
        self.assertIn(_ref("superpowers"), out)
        self.assertIn("rtk", out)
        linha_rtk = next(l for l in out.splitlines() if l.startswith("rtk"))
        self.assertIn("não instalado", linha_rtk)
        linha_os = next(l for l in out.splitlines() if l.startswith("openspec"))
        self.assertIn("não instalado", linha_os)

    def test_status_bin_ausente(self):
        _instala_clone(self.home, "rtk")

        def run(cmd, **kw):
            cmd = [str(c) for c in cmd]
            if cmd[:2] == ["git", "-C"] and cmd[3] == "describe":
                return subprocess.CompletedProcess(cmd, 0, stdout=_ref("rtk") + "\n", stderr="")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

        self.cmd_plugins("status", home=self.home, stdout=self.saida.append, run=run)
        linha = next(l for l in "\n".join(self.saida).splitlines() if l.startswith("rtk"))
        self.assertIn("ausente", linha, "clone na ref mas sem bin → reporta ausência")


class PluginsUninstallTest(unittest.TestCase):
    def setUp(self):
        from sac.plugins import cmd_plugins
        self.cmd_plugins = cmd_plugins
        self.home = Path(tempfile.mkdtemp())
        (self.home / "plugins" / "rtk").mkdir(parents=True)
        (self.home / "bin").mkdir()
        self.saida = []

    def _run(self, resposta):
        self.saida = []
        rc = self.cmd_plugins("uninstall", home=self.home,
                              stdin=lambda: resposta, stdout=self.saida.append,
                              run=FakeRun())
        return rc, "\n".join(self.saida)

    def test_uninstall_exige_confirmacao(self):
        rc, out = self._run("n")
        self.assertEqual(rc, 0)
        self.assertTrue((self.home / "plugins").exists(), "sem confirmação, nada é removido")
        self.assertTrue((self.home / "bin").exists())
        self.assertIn("plugins", out, "alvos são listados antes da confirmação")

    def test_uninstall_confirmado_remove(self):
        rc, out = self._run("s")
        self.assertEqual(rc, 0)
        self.assertFalse((self.home / "plugins").exists())
        self.assertFalse((self.home / "bin").exists())


class CollectStatusTest(unittest.TestCase):
    """Base real dos checks do doctor: collect_status sobre diretório tmp."""

    def setUp(self):
        from sac.plugins import collect_status
        self.collect_status = collect_status
        self.home = Path(tempfile.mkdtemp())

    def _run_git(self, cmd, **kw):
        cmd = [str(c) for c in cmd]
        if cmd[:2] == ["git", "-C"] and cmd[3] == "describe":
            nome = Path(cmd[2]).name
            return subprocess.CompletedProcess(cmd, 0, stdout=_ref(nome) + "\n", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

    def test_tudo_ausente(self):
        sts = self.collect_status(home=self.home, run=self._run_git)
        self.assertEqual(len(sts), 3)
        for st in sts:
            self.assertFalse(st["instalado"])
            self.assertFalse(st["sincronizado"])

    def test_tudo_sincronizado(self):
        for p in PLUGINS:
            d = _instala_clone(self.home, p["nome"])
            if p["tipo"] == "skills":
                (d / p["skills_dir"]).mkdir()
            else:
                bin_dir(self.home).mkdir(parents=True, exist_ok=True)
                (bin_dir(self.home) / p["nome"]).write_text("x", encoding="utf-8")
        sts = self.collect_status(home=self.home, run=self._run_git)
        for st in sts:
            self.assertTrue(st["instalado"], st)
            self.assertTrue(st["sincronizado"], st)
            self.assertEqual(st["ref_atual"], st["ref"])


class HarnessCmdTest(unittest.TestCase):
    """v27: injeção dos plugins nos args do harness."""

    def setUp(self):
        from sac.commands import _harness_cmd
        self.harness_cmd = _harness_cmd
        self.home = Path(tempfile.mkdtemp())

    def _agent(self, command, args=()):
        return AgentConfig(name="a", command=command, args=list(args), role="aux")

    def _instala_superpowers(self):
        (self.home / "plugins" / "superpowers" / "skills").mkdir(parents=True)

    def test_kimi_com_superpowers_ganha_skills_dir(self):
        self._instala_superpowers()
        cmd = self.harness_cmd(self._agent("kimi", ["--model", "k3"]), home=self.home)
        self.assertIn("--skills-dir", cmd)
        idx = cmd.index("--skills-dir")
        self.assertEqual(cmd[idx + 1],
                         str(self.home / "plugins" / "superpowers" / "skills"))
        self.assertEqual(cmd[:3], ["kimi", "--model", "k3"], "args originais preservados")

    def test_kimi_sem_superpowers_nao_ganha_skills_dir(self):
        cmd = self.harness_cmd(self._agent("kimi"), home=self.home)
        self.assertNotIn("--skills-dir", cmd)
        self.assertEqual(cmd, ["kimi"])

    def test_opencode_ganha_pure_mesmo_sem_plugins(self):
        cmd = self.harness_cmd(self._agent("opencode", ["--auto"]), home=self.home)
        self.assertIn("--pure", cmd)
        self.assertEqual(cmd, ["opencode", "--auto", "--pure"])

    def test_opencode_pure_nao_duplica(self):
        cmd = self.harness_cmd(self._agent("opencode", ["--pure"]), home=self.home)
        self.assertEqual(cmd.count("--pure"), 1)

    def test_outros_harnesses_sem_args_extras(self):
        self._instala_superpowers()
        cmd = self.harness_cmd(self._agent("gemini"), home=self.home)
        self.assertEqual(cmd, ["gemini"])


class SessionEnvPluginsTest(unittest.TestCase):
    def setUp(self):
        from sac.commands import _session_env
        from sac.store import Store
        self.session_env = _session_env
        self.d = Path(tempfile.mkdtemp())
        self.store = Store(self.d / ".sac")
        self.home = Path(tempfile.mkdtemp())

    def test_path_comeca_com_bin_do_sac_home(self):
        with patch.dict(os.environ, {"SAC_HOME": str(self.home), "PATH": "/usr/bin:/bin"}):
            env = self.session_env(self.store, None, "leader")
        self.assertTrue(env["PATH"].startswith(str(self.home / "bin") + os.pathsep),
                        "$SAC_HOME/bin tem precedência sobre qualquer instalação externa")
        self.assertIn("/usr/bin", env["PATH"])

    def test_env_padrao_preservado(self):
        cfg = self.d / ".sac" / "sac.toml"
        with patch.dict(os.environ, {"SAC_HOME": str(self.home), "PATH": "/usr/bin"}):
            env = self.session_env(self.store, cfg, "leader")
        self.assertEqual(env["SAC_AGENT"], "leader")
        self.assertEqual(env["SAC_CONFIG"], str(cfg))
        self.assertEqual(env["SAC_ROOT"], str(self.store.root.parent))


class StackCanonicaTest(unittest.TestCase):
    """v27: seção 'Stack canônica SAC' nos contratos gerados."""

    def setUp(self):
        from sac.contracts import stack_canonica
        from sac.init import _contract_by_key, _render_contract
        self.stack = stack_canonica
        self.contract_by_key = _contract_by_key
        self.render = _render_contract
        self.home = Path(tempfile.mkdtemp())

    def test_todos_tem_rtk_e_ponteiro_de_skills(self):
        for key in ("lider", "desenvolvedor", "revisor", "documentacao", "deploy",
                    "seguranca", "auxiliar"):
            with patch.dict(os.environ, {"SAC_HOME": str(self.home)}):
                sec = self.stack(key)
            self.assertIn("rtk", sec, key)
            skills = str(self.home / "plugins" / "superpowers" / "skills")
            self.assertIn(skills, sec, f"{key}: caminho absoluto das skills do SAC")

    def test_lider_tem_openspec_e_delegacao_canonica(self):
        with patch.dict(os.environ, {"SAC_HOME": str(self.home)}):
            sec = self.stack("lider")
        self.assertIn("openspec", sec)
        self.assertIn("delegar", sec, "líder instrui a ferramenta canônica ao delegar")

    def test_documentacao_tem_openspec(self):
        with patch.dict(os.environ, {"SAC_HOME": str(self.home)}):
            sec = self.stack("documentacao")
        self.assertIn("openspec", sec)

    def test_aux_sem_openspec(self):
        with patch.dict(os.environ, {"SAC_HOME": str(self.home)}):
            sec = self.stack("desenvolvedor")
        self.assertNotIn("openspec", sec)

    def test_secao_sem_instrucoes_de_instalacao(self):
        for key in ("lider", "desenvolvedor", "documentacao"):
            with patch.dict(os.environ, {"SAC_HOME": str(self.home)}):
                sec = self.stack(key)
            for proibido in ("pip install", "npm i"):
                self.assertNotIn(proibido, sec,
                                 "seção descreve o que já está disponível — nunca instala")

    def test_contrato_gerado_contem_secao_com_path_absoluto(self):
        with patch.dict(os.environ, {"SAC_HOME": str(self.home)}):
            content = self.render(self.contract_by_key("lider"), "kimi", "")
        self.assertIn("Stack canônica SAC", content)
        self.assertIn(str(self.home / "plugins" / "superpowers" / "skills"), content)
        for proibido in ("pip install", "npm i"):
            self.assertNotIn(proibido, content)


if __name__ == "__main__":
    unittest.main()
