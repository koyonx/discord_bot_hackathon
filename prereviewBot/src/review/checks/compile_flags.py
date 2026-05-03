from __future__ import annotations

import glob

from review.check import Check, CheckContext, CheckResult, run_command
from review.projects.base import ProjectSpec


def compile_flags_check(project: ProjectSpec, *, bonus: bool) -> Check:
    """Compile every .c file with the project's required flags.

    This is independent of the project's Makefile — even if `make all` passes,
    the Makefile may have softened the flags. This check enforces that every
    source file builds cleanly under -Wall -Wextra -Werror (or whatever the
    project's spec declares).
    """
    flags = list(project.required_compile_flags)

    async def run(ctx: CheckContext) -> list[CheckResult]:
        c_files = sorted(glob.glob(str(ctx.repo_dir / "*.c")))
        if bonus:
            c_files = sorted({*c_files, *glob.glob(str(ctx.repo_dir / "*_bonus.c"))})

        if not c_files:
            return [
                CheckResult(
                    name="compile flags",
                    passed=False,
                    summary="*.c ファイルが見つかりませんでした",
                )
            ]

        rel_files = [str(p).removeprefix(str(ctx.repo_dir) + "/") for p in c_files]
        run_result = await run_command(
            ["gcc", *flags, "-c", *rel_files],
            cwd=ctx.repo_dir,
            timeout=ctx.timeout,
        )
        return [
            CheckResult(
                name="compile flags",
                passed=run_result.succeeded,
                summary=(
                    f"必須フラグ {' '.join(flags)} でのコンパイルに失敗"
                    if not run_result.succeeded
                    else ""
                ),
                runs=(run_result,),
            )
        ]

    return run
