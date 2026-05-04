from __future__ import annotations

import re

from review.check import Check, CheckContext, CheckResult, run_command
from review.projects.base import ProjectSpec

# nm letters indicating storage in mutable global memory:
#   D / d   data section (initialised globals)
#   B / b   bss section  (uninitialised globals)
#   C / c   common (uninitialised globals, tentative)
#   G / g   small data
# We allow read-only initialised data (R/r) since string literals end up there.
_GLOBAL_STORAGE_TYPES = frozenset({"D", "B", "C", "G"})


def no_globals_check(project: ProjectSpec, *, bonus: bool) -> Check:  # noqa: ARG001
    artifact = (
        project.expected_artifacts_bonus[0]
        if bonus
        else project.expected_artifacts_mandatory[0]
    )

    async def run(ctx: CheckContext) -> list[CheckResult]:
        if not (ctx.repo_dir / artifact).exists():
            return [
                CheckResult(
                    name="no global variables",
                    passed=False,
                    summary=f"{artifact} がビルドされていないためグローバル変数チェックが行えません",
                )
            ]
        run_result = await run_command(
            ["nm", "--format=posix", artifact],
            cwd=ctx.repo_dir,
            timeout=ctx.timeout,
        )
        if not run_result.succeeded:
            return [
                CheckResult(
                    name="no global variables",
                    passed=False,
                    summary=f"`nm` の実行に失敗しました ({artifact})",
                    runs=(run_result,),
                )
            ]
        offending: list[str] = []
        for line in run_result.stdout.splitlines():
            # posix format: "<name> <type> [addr] [size]"
            m = re.match(r"^\s*([A-Za-z_][\w.@]*)\s+([A-Za-z])", line)
            if not m:
                continue
            name, kind = m.group(1), m.group(2)
            if kind not in _GLOBAL_STORAGE_TYPES:
                continue
            # Filter compiler/linker internals.
            if name.startswith(("__", "_GLOBAL_", ".")):
                continue
            offending.append(f"{name} [{kind}]")
        passed = not offending
        summary = ""
        if not passed:
            joined = ", ".join(sorted(offending)[:30])
            extra = "" if len(offending) <= 30 else f" 他 {len(offending) - 30} 件"
            summary = (
                "グローバル変数の宣言は subject IV.1 で禁止されています。"
                f"検出: {joined}{extra}"
            )
        return [
            CheckResult(
                name="no global variables",
                passed=passed,
                summary=summary,
                runs=(run_result,),
            )
        ]

    return run
