from __future__ import annotations

import re

from review.check import Check, CheckContext, CheckResult, run_command
from review.projects.base import ProjectSpec


def required_functions_check(project: ProjectSpec, *, bonus: bool) -> Check:
    expected = list(project.required_mandatory_functions)
    if bonus:
        expected.extend(project.required_bonus_functions)
    artifact = (
        project.expected_artifacts_bonus[0]
        if bonus
        else project.expected_artifacts_mandatory[0]
    )

    async def run(ctx: CheckContext) -> list[CheckResult]:
        if not (ctx.repo_dir / artifact).exists():
            return [
                CheckResult(
                    name=f"required functions ({artifact})",
                    passed=False,
                    summary=f"{artifact} がビルドされていないため必須関数の存在確認が行えません",
                )
            ]
        run_result = await run_command(
            ["nm", "--defined-only", "--format=posix", artifact],
            cwd=ctx.repo_dir,
            timeout=ctx.timeout,
        )
        if not run_result.succeeded:
            return [
                CheckResult(
                    name=f"required functions ({artifact})",
                    passed=False,
                    summary=f"`nm` の実行に失敗しました ({artifact})",
                    runs=(run_result,),
                )
            ]
        defined: set[str] = set()
        for line in run_result.stdout.splitlines():
            m = re.match(r"^\s*([A-Za-z_][\w]*)\s+T", line)
            if m:
                defined.add(m.group(1))
        missing = sorted(set(expected) - defined)
        passed = not missing
        summary = ""
        if not passed:
            summary = (
                f"{artifact} に未定義の必須関数があります ({len(missing)} 件): "
                + ", ".join(missing)
            )
        return [
            CheckResult(
                name=f"required functions ({artifact})",
                passed=passed,
                summary=summary,
                runs=(run_result,),
            )
        ]

    return run
