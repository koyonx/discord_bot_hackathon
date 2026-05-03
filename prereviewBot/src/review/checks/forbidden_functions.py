from __future__ import annotations

import re

from review.check import Check, CheckContext, CheckResult, run_command
from review.projects.base import ProjectSpec

# Compiler/linker-internal undefined symbols that show up in a .a archive but
# are not user calls into libc — never flag these as forbidden.
_INTERNAL_SYMBOL_PREFIXES = ("__", "_GLOBAL_", ".")
_INTERNAL_SYMBOLS = frozenset({"_init", "_fini"})


def forbidden_functions_check(project: ProjectSpec, *, bonus: bool) -> Check:
    artifacts = (
        project.expected_artifacts_bonus if bonus else project.expected_artifacts_mandatory
    )

    async def run(ctx: CheckContext) -> list[CheckResult]:
        results: list[CheckResult] = []
        for artifact in artifacts:
            artifact_path = ctx.repo_dir / artifact
            if not artifact_path.exists():
                results.append(
                    CheckResult(
                        name=f"forbidden functions ({artifact})",
                        passed=False,
                        summary=(
                            f"{artifact} がビルドされていないため禁止関数チェックが行えません"
                        ),
                    )
                )
                continue

            run_result = await run_command(
                ["nm", "--undefined-only", "--format=posix", artifact],
                cwd=ctx.repo_dir,
                timeout=ctx.timeout,
            )
            if not run_result.succeeded:
                results.append(
                    CheckResult(
                        name=f"forbidden functions ({artifact})",
                        passed=False,
                        summary=f"`nm` の実行に失敗しました ({artifact})",
                        runs=(run_result,),
                    )
                )
                continue

            # Each line: "<symbol> U" or "<symbol> U <addr> <size>"
            symbols = []
            for line in run_result.stdout.splitlines():
                m = re.match(r"^\s*([A-Za-z_.][\w.@]*)\s+U", line)
                if m:
                    symbols.append(m.group(1))

            forbidden = sorted(
                {
                    s
                    for s in symbols
                    if s not in project.allowed_external_symbols
                    and s not in _INTERNAL_SYMBOLS
                    and not s.startswith(_INTERNAL_SYMBOL_PREFIXES)
                }
            )

            passed = not forbidden
            summary = ""
            if not passed:
                summary = (
                    f"{artifact} に禁止関数の参照が含まれています: "
                    + ", ".join(forbidden)
                )
            results.append(
                CheckResult(
                    name=f"forbidden functions ({artifact})",
                    passed=passed,
                    summary=summary,
                    runs=(run_result,),
                )
            )
        return results

    return run
