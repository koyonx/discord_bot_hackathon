from __future__ import annotations

from review.check import Check, CheckContext, CheckResult
from review.projects.base import ProjectSpec


def repo_layout_check(project: ProjectSpec, *, bonus: bool) -> Check:  # noqa: ARG001
    """All .c/.h must live at the repo root (subject IV.1 + Chapter VI).

    Sub-directories are flagged with the exception of ones that are
    obviously not part of the submission (`.git`, `.github`, `tests`).
    """
    _ALLOWED_SUBDIRS = {".git", ".github", ".vscode", ".idea", "tests", "test"}

    async def run(ctx: CheckContext) -> list[CheckResult]:
        offending: list[str] = []
        for path in ctx.repo_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(ctx.repo_dir)
            except ValueError:
                continue
            parts = rel.parts
            if len(parts) == 1:
                continue
            if parts[0] in _ALLOWED_SUBDIRS:
                continue
            if path.suffix in {".c", ".h"}:
                offending.append(str(rel))
        passed = not offending
        summary = ""
        if not passed:
            joined = ", ".join(sorted(offending)[:20])
            extra = "" if len(offending) <= 20 else f" 他 {len(offending) - 20} 件"
            summary = (
                "サブディレクトリに .c/.h が存在します。subject 規定「全ファイルを"
                "リポジトリのルートに置く」に違反: "
                + joined
                + extra
            )
        return [
            CheckResult(
                name="repo layout (files at root)",
                passed=passed,
                summary=summary,
            )
        ]

    return run
