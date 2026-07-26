"""Fixtures globais da suíte — ambiente determinístico em qualquer máquina.

Sem isso, máquinas sem os harnesses no PATH (CI) ou sem config do kimi
quebram os fluxos do wizard na pergunta "Corrigir o comando?" e no install
de plugins (a v28 expôs isso no workflow de release). Testes que exercitam
detecção/validação re-patcheiam com seus próprios valores (o patch interno
sobrepõe o da fixture durante o corpo do teste).
"""
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def _ambiente_deterministico():
    with patch("sac.init._list_models", return_value=[]), \
         patch("sac.init._cmd_plugins", return_value=0), \
         patch("sac.init.shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}"):
        yield
