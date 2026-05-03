from __future__ import annotations

import glob

from review.check import Check, CheckContext, CheckResult, run_command
from review.projects.base import ProjectSpec


def norminette_check(project: ProjectSpec, *, bonus: bool) -> Check:
    patterns = (
        project.norminette_targets_bonus if bonus else project.norminette_targets_mandatory
    )

    async def run(ctx: CheckContext) -> list[CheckResult]:
        files: list[str] = []
        for pattern in patterns:
            files.extend(
                sorted(glob.glob(str(ctx.repo_dir / pattern), recursive=False))
            )
        # de-duplicate while preserving order
        seen: set[str] = set()
        unique_files = [f for f in files if not (f in seen or seen.add(f))]

        if not unique_files:
            return [
                CheckResult(
                    name="norminette",
                    passed=False,
                    summary=(
                        "norminette の対象ファイルが見つかりませんでした "
                        f"(patterns={list(patterns)})"
                    ),
                )
            ]

        # Pass relative paths so error output is short.
        rel = [str(p).removeprefix(str(ctx.repo_dir) + "/") for p in unique_files]
        run_result = await run_command(
            ["norminette", *rel],
            cwd=ctx.repo_dir,
            timeout=ctx.timeout,
        )
        return [
            CheckResult(
                name="norminette",
                passed=run_result.succeeded,
                summary="norminette 違反あり" if not run_result.succeeded else "",
                runs=(run_result,),
            )
        ]

    return run
