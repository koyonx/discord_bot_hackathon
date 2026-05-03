from __future__ import annotations

from review.check import Check, CheckContext, CheckResult, run_command
from review.projects.base import ProjectSpec


def make_targets_check(project: ProjectSpec, *, bonus: bool) -> Check:
    targets = list(project.required_make_targets)
    if bonus and project.bonus_make_target:
        # Insert `bonus` after `all` so the artifact ordering is intuitive.
        if "all" in targets:
            idx = targets.index("all") + 1
            targets.insert(idx, project.bonus_make_target)
        else:
            targets.insert(0, project.bonus_make_target)

    async def run(ctx: CheckContext) -> list[CheckResult]:
        results: list[CheckResult] = []
        for target in targets:
            run_result = await run_command(
                ["make", target],
                cwd=ctx.repo_dir,
                timeout=ctx.timeout,
            )
            results.append(
                CheckResult(
                    name=f"make {target}",
                    passed=run_result.succeeded,
                    summary=(
                        f"`make {target}` が失敗しました"
                        if not run_result.succeeded
                        else ""
                    ),
                    runs=(run_result,),
                )
            )
            # If `all` fails the rest of the targets are unlikely to be meaningful;
            # but we still run them so the report is complete.
        return results

    return run
