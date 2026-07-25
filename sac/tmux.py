"""Wrapper fino do tmux. Toda chamada tmux do SAC passa por aqui (fakeável em testes)."""
from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import time
from collections.abc import Callable


class TmuxError(Exception):
    """Erro ao executar comando tmux."""


def _default_runner(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


class Tmux:
    def __init__(self, session: str, runner: Callable[..., subprocess.CompletedProcess] | None = None,
                 socket: str | None = None):
        self.session = session
        self.socket = socket
        self.runner = runner or _default_runner

    def _cmd(self, *args: str) -> tuple[str, ...]:
        if self.socket:
            return ("tmux", "-S", self.socket, *args)
        return ("tmux", *args)

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return self.runner(*self._cmd(*args))

    def check(self, *args: str) -> subprocess.CompletedProcess:
        cp = self._run(*args)
        if cp.returncode != 0:
            raise TmuxError(cp.stderr.strip() or f"tmux {' '.join(args)} falhou (rc={cp.returncode})")
        return cp

    def _target(self, window: str) -> str:
        return f"{self.session}:{window}"

    def _ptarget(self, target: str) -> str:
        if target.startswith("%"):
            return target
        return f"{self.session}:{target}"

    def has_session(self) -> bool:
        return self._run("has-session", "-t", self.session).returncode == 0

    def _pane_id(self) -> list[str]:
        return ["-P", "-F", "#{pane_id}"]

    def new_session(self, window: str, command: list[str], env: dict[str, str] | None = None,
                    width: int | None = None, height: int | None = None) -> str:
        cmd = shlex.join(command)
        if env:
            prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
            cmd = f"env {prefix} {cmd}"
        size = []
        if width is not None and height is not None:
            size = ["-x", str(width), "-y", str(height)]
        return self.check("new-session", "-d", "-s", self.session, "-n", window,
                          *size, *self._pane_id(), cmd).stdout.strip()

    def new_window(self, name: str, command: list[str], env: dict[str, str] | None = None) -> str:
        cmd = shlex.join(command)
        if env:
            prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
            cmd = f"env {prefix} {cmd}"
        return self.check("new-window", "-t", self.session, "-n", name,
                          *self._pane_id(), cmd).stdout.strip()

    def split_window(self, target: str, command: list[str], vertical: bool = False,
                     env: dict[str, str] | None = None, pct: int | None = None,
                     full: bool = False, before: bool = False,
                     lines: int | None = None) -> str:
        cmd = shlex.join(command)
        if env:
            prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
            cmd = f"env {prefix} {cmd}"
        args = ["split-window", "-t", self._ptarget(target), "-v" if vertical else "-h"]
        if before:
            args.append("-b")
        if full:
            args.append("-f")
        if lines is not None:
            args += ["-l", str(lines)]
        elif pct is not None:
            args += ["-p", str(pct)]
        return self.check(*args, *self._pane_id(), cmd).stdout.strip()

    def set_pane_option(self, target: str, name: str, value: str) -> None:
        self._run("set-option", "-p", "-t", self._ptarget(target), name, value)

    def resize_pane(self, target: str, width: int) -> None:
        self._run("resize-pane", "-t", self._ptarget(target), "-x", str(width))

    def select_layout(self, window: str, layout: str) -> None:
        self._run("select-layout", "-t", self._target(window), layout)

    def select_window(self, window: str) -> None:
        self._run("select-window", "-t", self._target(window))

    def select_pane(self, target: str) -> None:
        self._run("select-pane", "-t", self._ptarget(target))

    def set_pane_title(self, pane_id: str, title: str) -> None:
        self._run("select-pane", "-t", self._ptarget(pane_id), "-T", title)

    def has_pane(self, name: str) -> bool:
        return self.find_pane_id(name) is not None

    def find_pane_id(self, name: str) -> str | None:
        out = self._run("list-panes", "-s", "-t", self.session, "-F",
                         "#{pane_id}|#{pane_start_command}").stdout
        for line in out.splitlines():
            if "|" not in line:
                continue
            pid, cmd = line.split("|", 1)
            if f"SAC_AGENT={name}" in cmd:
                return pid
        return None

    def has_window(self, name: str) -> bool:
        out = self._run("list-windows", "-t", self.session, "-F", "#{window_name}").stdout
        return name in out.split()

    def paste(self, target: str, text: str) -> None:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".sac-paste", delete=False)
        f.write(text)
        f.close()
        self._run("load-buffer", f.name)
        self._run("paste-buffer", "-p", "-t", self._ptarget(target))
        os.unlink(f.name)

    def press_enter(self, target: str) -> None:
        self._run("send-keys", "-t", self._ptarget(target), "Enter")

    SUBMIT_DELAY_S = 0.5
    POKE_DELAY_S = 0.2

    def send_keys(self, target: str, text: str) -> None:
        self._run("send-keys", "-t", self._ptarget(target), "-l", "--", text)
        time.sleep(self.SUBMIT_DELAY_S)
        self._run("send-keys", "-t", self._ptarget(target), "Enter")

    def poke_with_enter(self, target: str, body: str) -> None:
        self._run("send-keys", "-t", self._ptarget(target), "-l", "--", body)
        time.sleep(self.POKE_DELAY_S)
        self._run("send-keys", "-t", self._ptarget(target), "Enter")

    def capture_pane(self, target: str, lines: int = 200) -> str:
        return self._run("capture-pane", "-p", "-t", self._ptarget(target), "-S", f"-{lines}").stdout

    def kill_pane(self, target: str) -> None:
        self._run("kill-pane", "-t", self._ptarget(target))

    def find_pane_by_command(self, substring: str, window: str | None = None) -> str | None:
        if window:
            out = self._run("list-panes", "-t", f"{self.session}:{window}", "-F",
                             "#{pane_id}|#{pane_start_command}").stdout
        else:
            out = self._run("list-panes", "-s", "-t", self.session, "-F",
                             "#{pane_id}|#{pane_start_command}").stdout
        for line in out.splitlines():
            if "|" not in line:
                continue
            pid, cmd = line.split("|", 1)
            if substring in cmd:
                return pid
        return None

    def kill_session(self) -> None:
        self._run("kill-session", "-t", self.session)
