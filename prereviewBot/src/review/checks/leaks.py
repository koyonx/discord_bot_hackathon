from __future__ import annotations

import os
from pathlib import Path

from review.check import Check, CheckContext, CheckResult, run_command
from review.projects.base import ProjectSpec

_SMOKE_SOURCE = Path(__file__).parents[1] / "projects" / "libft_smoke.c"

_VALGRIND_ERROR_EXIT = 42


def memory_leaks_check(project: ProjectSpec, *, bonus: bool) -> Check:
    """Compile the behavioural smoke test WITHOUT sanitizers and run it under
    valgrind. ASAN replaces malloc, so leak detection has to live on a
    separate binary. subject Chapter II:「ヒープ確保したメモリは必要なときに
    すべて解放されなければならない (リークは許容しない)」."""

    artifact = (
        project.expected_artifacts_bonus[0]
        if bonus
        else project.expected_artifacts_mandatory[0]
    )

    async def run(ctx: CheckContext) -> list[CheckResult]:
        if not (ctx.repo_dir / artifact).exists():
            return [
                CheckResult(
                    name="memory leaks (valgrind)",
                    passed=False,
                    summary=f"{artifact} がないためリークチェックを実行できません",
                )
            ]
        if not _SMOKE_SOURCE.exists():
            return [
                CheckResult(
                    name="memory leaks (valgrind)",
                    passed=False,
                    summary="リークチェック用のスモークソースが見つかりません",
                )
            ]

        smoke_dst = ctx.workspace_dir / "libft_leakcheck.c"
        smoke_dst.write_text(_SMOKE_SOURCE.read_text())
        binary = ctx.workspace_dir / "libft_leakcheck"

        compile_args: list[str] = [
            "gcc",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-g",
            "-O0",
        ]
        if bonus:
            compile_args.append("-DLIBFT_BONUS")
        compile_args += [
            f"-I{ctx.repo_dir}",
            str(smoke_dst),
            str(ctx.repo_dir / artifact),
            "-o",
            str(binary),
        ]

        compile_run = await run_command(
            compile_args,
            cwd=ctx.workspace_dir,
            timeout=ctx.timeout,
        )
        if not compile_run.succeeded:
            return [
                CheckResult(
                    name="memory leaks (valgrind, build)",
                    passed=False,
                    summary="リークチェック用バイナリのビルドに失敗",
                    runs=(compile_run,),
                )
            ]

        env = os.environ.copy()
        # valgrind needs the locale to be sane so its own stderr is parseable.
        env.setdefault("LC_ALL", "C")
        valgrind_run = await run_command(
            [
                "valgrind",
                "--leak-check=full",
                "--show-leak-kinds=definite,indirect",
                "--errors-for-leak-kinds=definite,indirect",
                "--track-origins=yes",
                "--num-callers=20",
                f"--error-exitcode={_VALGRIND_ERROR_EXIT}",
                "-q",
                str(binary),
            ],
            cwd=ctx.workspace_dir,
            env=env,
            # valgrind is markedly slower than the host; allocate a bigger budget.
            timeout=min(max(ctx.timeout, 180.0), 300.0),
        )

        if valgrind_run.timed_out:
            return [
                CheckResult(
                    name="memory leaks (valgrind)",
                    passed=False,
                    summary="valgrind がタイムアウトしました",
                    runs=(compile_run, valgrind_run),
                )
            ]
        # Errors detected by valgrind override the program's exit code.
        if valgrind_run.returncode == _VALGRIND_ERROR_EXIT:
            return [
                CheckResult(
                    name="memory leaks (valgrind)",
                    passed=False,
                    summary=(
                        "メモリリーク (definite / indirect) が検出されました。"
                        "subject Chapter II によりリークは許容されません"
                    ),
                    runs=(compile_run, valgrind_run),
                )
            ]
        # Any other non-zero exit comes from the test program itself, which is
        # surfaced by the behavioural smoke check — the leak check is clean.
        return [
            CheckResult(
                name="memory leaks (valgrind)",
                passed=True,
                summary="",
                runs=(compile_run, valgrind_run),
            )
        ]

    return run
