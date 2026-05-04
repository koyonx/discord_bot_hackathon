from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from review.projects.base import ProjectSpec


@dataclass(frozen=True)
class CommandRun:
    """A single command execution captured for reporting."""

    command: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool

    @property
    def succeeded(self) -> bool:
        return not self.timed_out and self.returncode == 0


@dataclass(frozen=True)
class CheckResult:
    """Result of a single named check. May reference one or more command runs."""

    name: str
    passed: bool
    summary: str
    runs: tuple[CommandRun, ...] = field(default_factory=tuple)


@dataclass
class CheckContext:
    repo_dir: Path
    workspace_dir: Path
    project: "ProjectSpec"
    bonus: bool
    timeout: float


Check = Callable[[CheckContext], Awaitable[list[CheckResult]]]


async def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float,
    stdin_input: bytes | None = None,
) -> CommandRun:
    """Run a command with a hard timeout and capture stdout/stderr."""
    display = " ".join(args)
    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdin=asyncio.subprocess.PIPE if stdin_input is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        return CommandRun(
            command=display,
            returncode=-1,
            stdout="",
            stderr=f"command not found: {exc.filename}",
            duration_seconds=time.monotonic() - start,
            timed_out=False,
        )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=stdin_input),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except Exception:
            pass
        return CommandRun(
            command=display,
            returncode=-1,
            stdout="",
            stderr=f"timed out after {timeout:.0f}s",
            duration_seconds=time.monotonic() - start,
            timed_out=True,
        )

    return CommandRun(
        command=display,
        returncode=proc.returncode if proc.returncode is not None else -1,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
        duration_seconds=time.monotonic() - start,
        timed_out=False,
    )
