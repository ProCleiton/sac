"""Wrapper fino do tmux. Toda chamada tmux do SAC passa por aqui (fakeável em testes)."""
from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from collections.abc import Callable


def _default_runner(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


class Tmux:
    def __init__(self, session: str, runner: Callable[..., subprocess.CompletedProcess] | None = None):
        self.session = session
        self.runner = runner or _default_runner

    def _target(self, window: str) -> str:
        return f"{self.session}:{window}"

    def has_session(self) -> bool:
        return self.runner("tmux", "has-session", "-t", self.session).returncode == 0

    def new_session(self, window: str, command: list[str], env: dict[str, str] | None = None) -> None:
        cmd = " ".join(command)
        if env:
            prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
            cmd = f"env {prefix} {cmd}"
        self.runner("tmux", "new-session", "-d", "-s", self.session, "-n", window, cmd)

    def new_window(self, name: str, command: list[str], env: dict[str, str] | None = None) -> None:
        cmd = " ".join(command)
        if env:
            prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
            cmd = f"env {prefix} {cmd}"
        self.runner("tmux", "new-window", "-t", self.session, "-n", name, cmd)

    def has_window(self, name: str) -> bool:
        out = self.runner("tmux", "list-windows", "-t", self.session, "-F", "#{window_name}").stdout
        return name in out.split()

    def paste(self, window: str, text: str) -> None:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".sac-paste", delete=False)
        f.write(text)
        f.close()
        self.runner("tmux", "load-buffer", f.name)
        self.runner("tmux", "paste-buffer", "-p", "-t", self._target(window))
        os.unlink(f.name)

    def send_keys(self, window: str, text: str) -> None:
        self.runner("tmux", "send-keys", "-t", self._target(window), "-l", "--", text)
        self.runner("tmux", "send-keys", "-t", self._target(window), "Enter")

    def capture_pane(self, window: str, lines: int = 200) -> str:
        return self.runner("tmux", "capture-pane", "-p", "-t", self._target(window), "-S", f"-{lines}").stdout

    def kill_session(self) -> None:
        self.runner("tmux", "kill-session", "-t", self.session)
