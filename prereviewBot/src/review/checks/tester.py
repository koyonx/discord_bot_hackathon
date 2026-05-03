from __future__ import annotations

from textwrap import dedent

from review.check import Check, CheckContext, CheckResult, run_command
from review.projects.base import ProjectSpec

# Minimal smoke test source.
# Verifies that libft.a links and a small set of well-known functions return
# values consistent with libc. This is intentionally narrow — a thorough
# tester (e.g. Tripouille's libftTester) can replace this later by swapping in
# a different smoke_tester_check implementation.
_SMOKE_C = dedent(
    """\
    #include "libft.h"
    #include <string.h>
    #include <stdlib.h>

    int main(void) {
        if (ft_strlen("hello") != 5) return 1;
        if (ft_atoi("42") != 42) return 2;
        if (!ft_isalpha('a')) return 3;
        if (ft_isalpha('1')) return 4;
        char *d = ft_strdup("world");
        if (!d) return 5;
        if (strcmp(d, "world") != 0) { free(d); return 6; }
        free(d);
        return 0;
    }
    """
)


def smoke_tester_check(project: ProjectSpec, *, bonus: bool) -> Check:
    artifact = (
        project.expected_artifacts_bonus[0] if bonus else project.expected_artifacts_mandatory[0]
    )

    async def run(ctx: CheckContext) -> list[CheckResult]:
        if not (ctx.repo_dir / artifact).exists():
            return [
                CheckResult(
                    name="smoke tester",
                    passed=False,
                    summary=f"{artifact} が見つからないためテストを実行できません",
                )
            ]

        smoke_path = ctx.workspace_dir / "smoke.c"
        smoke_path.write_text(_SMOKE_C)
        binary_path = ctx.workspace_dir / "smoke"

        compile_run = await run_command(
            [
                "gcc",
                "-Wall",
                "-Wextra",
                "-Werror",
                f"-I{ctx.repo_dir}",
                str(smoke_path),
                str(ctx.repo_dir / artifact),
                "-o",
                str(binary_path),
            ],
            cwd=ctx.workspace_dir,
            timeout=ctx.timeout,
        )
        if not compile_run.succeeded:
            return [
                CheckResult(
                    name="smoke tester (build)",
                    passed=False,
                    summary="スモークテストのリンクに失敗しました",
                    runs=(compile_run,),
                )
            ]

        exec_run = await run_command(
            [str(binary_path)],
            cwd=ctx.workspace_dir,
            timeout=min(ctx.timeout, 30.0),
        )
        passed = exec_run.succeeded
        summary = ""
        if not passed:
            summary = (
                "スモークテストが失敗 "
                f"(exit={exec_run.returncode}, timed_out={exec_run.timed_out})"
            )
        return [
            CheckResult(
                name="smoke tester",
                passed=passed,
                summary=summary,
                runs=(compile_run, exec_run),
            )
        ]

    return run
