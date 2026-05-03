from __future__ import annotations

from review.check import Check, CheckContext, CheckResult, run_command
from review.projects.base import ProjectSpec


def no_relink_check(project: ProjectSpec, *, bonus: bool) -> Check:  # noqa: ARG001
    """`make all` を 2 回叩いて、2 回目が再リンクしないことを確認 (subject 規定)."""

    async def run(ctx: CheckContext) -> list[CheckResult]:
        # First build (assumed already done by make_targets check, but be safe).
        first = await run_command(["make", "all"], cwd=ctx.repo_dir, timeout=ctx.timeout)
        if not first.succeeded:
            return [
                CheckResult(
                    name="Makefile: no needless relinking",
                    passed=False,
                    summary="`make all` (1回目) が失敗しているため再リンクチェックが行えません",
                    runs=(first,),
                )
            ]
        second = await run_command(["make", "all"], cwd=ctx.repo_dir, timeout=ctx.timeout)
        # 2回目で何もすることがなければ make は通常 "Nothing to be done" を出すか stdout が空。
        # cc/gcc/ar 等が呼ばれていたら再リンクしている。
        suspicious = ("cc ", "gcc ", "clang ", "\tar ", "ar rcs", "ar -rcs", "ar rc ")
        out = (second.stdout + second.stderr).lower()
        relinking = any(token in out for token in suspicious)
        passed = second.succeeded and not relinking
        summary = ""
        if not second.succeeded:
            summary = "`make all` の 2 回目実行が失敗"
        elif relinking:
            summary = (
                "`make all` を 2 回続けて呼ぶと再コンパイル/再リンクが発生しています "
                "(subject: Your Makefile must not perform unnecessary relinking)"
            )
        return [
            CheckResult(
                name="Makefile: no needless relinking",
                passed=passed,
                summary=summary,
                runs=(second,),
            )
        ]

    return run
