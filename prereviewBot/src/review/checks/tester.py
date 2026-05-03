from __future__ import annotations

from pathlib import Path

from review.check import Check, CheckContext, CheckResult, run_command
from review.projects.base import ProjectSpec

_SMOKE_SOURCE = Path(__file__).parents[1] / "projects" / "libft_smoke.c"

# ASAN + UBSAN environment for deterministic output and per-error halts.
# Leak detection is intentionally disabled here — leaks are reported by the
# dedicated valgrind-based `memory_leaks_check` to keep responsibilities clean.
_SANITIZER_ENV = {
    "ASAN_OPTIONS": "abort_on_error=0:halt_on_error=1:detect_leaks=0:strict_string_checks=1",
    "UBSAN_OPTIONS": "abort_on_error=0:halt_on_error=1:print_stacktrace=1",
}


def libft_smoke_check(project: ProjectSpec, *, bonus: bool) -> Check:
    """Compile a comprehensive smoke test against libft.a and run it under
    AddressSanitizer / UndefinedBehaviorSanitizer."""

    artifact = (
        project.expected_artifacts_bonus[0]
        if bonus
        else project.expected_artifacts_mandatory[0]
    )

    async def run(ctx: CheckContext) -> list[CheckResult]:
        if not (ctx.repo_dir / artifact).exists():
            return [
                CheckResult(
                    name="behavioural smoke test",
                    passed=False,
                    summary=f"{artifact} がないためスモークテストを実行できません",
                )
            ]
        if not _SMOKE_SOURCE.exists():
            return [
                CheckResult(
                    name="behavioural smoke test",
                    passed=False,
                    summary=f"スモークテストのテンプレート {_SMOKE_SOURCE} が見つかりません",
                )
            ]

        smoke_dst = ctx.workspace_dir / "libft_smoke.c"
        smoke_dst.write_text(_SMOKE_SOURCE.read_text())
        binary = ctx.workspace_dir / "libft_smoke"

        compile_args = [
            "gcc",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-g",
            "-fsanitize=address,undefined",
            f"-I{ctx.repo_dir}",
            str(smoke_dst),
            str(ctx.repo_dir / artifact),
            "-o",
            str(binary),
        ]
        if bonus:
            compile_args.insert(compile_args.index(f"-I{ctx.repo_dir}"), "-DLIBFT_BONUS")

        compile_run = await run_command(
            compile_args,
            cwd=ctx.workspace_dir,
            timeout=ctx.timeout,
        )
        if not compile_run.succeeded:
            return [
                CheckResult(
                    name="behavioural smoke test (build)",
                    passed=False,
                    summary=(
                        "スモークテストのコンパイル/リンクに失敗。プロトタイプ違反、"
                        "必須関数の欠落、ヘッダ不備、リンクエラーなどが疑われます"
                    ),
                    runs=(compile_run,),
                )
            ]

        import os

        env = os.environ.copy()
        env.update(_SANITIZER_ENV)
        exec_run = await run_command(
            [str(binary)],
            cwd=ctx.workspace_dir,
            env=env,
            timeout=min(ctx.timeout, 60.0),
        )

        passed = exec_run.succeeded
        summary = ""
        if not passed:
            if exec_run.timed_out:
                summary = "スモークテストがタイムアウトしました (無限ループ等の疑い)"
            elif exec_run.returncode == 1:
                summary = "1 つ以上の関数が subject 規定の挙動と異なります (詳細は出力参照)"
            else:
                summary = (
                    f"スモークテストが異常終了 (exit={exec_run.returncode})。"
                    "ASAN/UBSAN による不正アクセスや UB 検出の可能性"
                )
        return [
            CheckResult(
                name="behavioural smoke test",
                passed=passed,
                summary=summary,
                runs=(compile_run, exec_run),
            )
        ]

    return run
