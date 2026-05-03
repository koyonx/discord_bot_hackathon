from __future__ import annotations

import re
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from review.check import run_command

_GITHUB_HTTPS_RE = re.compile(
    r"^https://github\.com/[\w.-]+/[\w.-]+?(?:\.git)?/?$"
)


class InvalidRepositoryUrl(ValueError):
    pass


def validate_github_url(url: str) -> str:
    """Reject anything that isn't a public-https GitHub URL.

    Returns the canonicalised URL (without trailing slash, with .git).
    """
    url = url.strip()
    if not _GITHUB_HTTPS_RE.match(url):
        raise InvalidRepositoryUrl(
            "リポジトリは public な HTTPS GitHub URL を指定してください "
            "(例: https://github.com/<user>/<repo>)"
        )
    canonical = url.rstrip("/")
    if not canonical.endswith(".git"):
        canonical += ".git"
    return canonical


@asynccontextmanager
async def cloned_workspace(url: str, *, root: Path, timeout: float):
    """Clone the repo into a fresh tempdir under root, yield (repo_dir, workspace_dir).

    The workspace_dir is the parent tempdir; the repo lives inside as `repo/`.
    On exit, the entire tempdir is removed.
    """
    canonical = validate_github_url(url)
    root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="prereview-", dir=str(root)))
    repo_dir = tmp / "repo"
    try:
        clone = await run_command(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--no-tags",
                "--config",
                "core.autocrlf=false",
                canonical,
                str(repo_dir),
            ],
            timeout=timeout,
        )
        if not clone.succeeded:
            raise RuntimeError(
                "git clone に失敗しました\n"
                f"$ {clone.command}\n"
                f"{(clone.stderr or clone.stdout).strip()}"
            )
        yield repo_dir, tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
