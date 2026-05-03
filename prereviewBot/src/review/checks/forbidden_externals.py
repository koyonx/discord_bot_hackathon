from __future__ import annotations

import re

from review.check import Check, CheckContext, CheckResult, run_command
from review.projects.base import ProjectSpec


def forbidden_externals_check(project: ProjectSpec, *, bonus: bool) -> Check:
    """Strict re-take: nm 由来の undefined シンボルが allowed_external_libc に
    収まっていることを確認。
    - `@GLIBC_2.34` などのバージョン接尾辞は剥がして比較する。
    - `__` / `_GLOBAL_` / `.` で始まるシンボル (compiler/linker internals) は除外。
    - 小文字 `_` 1文字始まりも除外 (POSIX `_init` / `_fini` 等のセクション関数)。
    """
    artifact = (
        project.expected_artifacts_bonus[0]
        if bonus
        else project.expected_artifacts_mandatory[0]
    )
    allowed = set(project.allowed_external_libc)

    async def run(ctx: CheckContext) -> list[CheckResult]:
        if not (ctx.repo_dir / artifact).exists():
            return [
                CheckResult(
                    name="forbidden externals",
                    passed=False,
                    summary=f"{artifact} がビルドされていないため外部関数チェックが行えません",
                )
            ]
        run_result = await run_command(
            ["nm", "--undefined-only", "--format=posix", artifact],
            cwd=ctx.repo_dir,
            timeout=ctx.timeout,
        )
        if not run_result.succeeded:
            return [
                CheckResult(
                    name="forbidden externals",
                    passed=False,
                    summary=f"`nm` の実行に失敗しました ({artifact})",
                    runs=(run_result,),
                )
            ]
        offending: set[str] = set()
        for line in run_result.stdout.splitlines():
            m = re.match(r"^\s*([A-Za-z_.][\w.]*?)(?:@@?[\w.]+)?\s+U", line)
            if not m:
                continue
            name = m.group(1)
            if name.startswith(("__", "_GLOBAL_", ".")):
                continue
            if name.startswith("_") and len(name) > 1 and name[1].islower():
                continue
            if name in allowed:
                continue
            offending.add(name)
        passed = not offending
        summary = ""
        if not passed:
            summary = (
                f"{artifact} に subject 非許可の外部関数参照があります "
                f"(allowed: {sorted(allowed)}): "
                + ", ".join(sorted(offending))
            )
        return [
            CheckResult(
                name="forbidden externals",
                passed=passed,
                summary=summary,
                runs=(run_result,),
            )
        ]

    return run
