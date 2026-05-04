from __future__ import annotations

import re

from review.check import Check, CheckContext, CheckResult
from review.projects.base import ProjectSpec


def _strip_comments(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        # Cut from the first '#' that isn't escaped.
        idx = line.find("#")
        if idx == -1:
            out.append(line)
        else:
            out.append(line[:idx])
    return "\n".join(out)


def makefile_rules_check(project: ProjectSpec, *, bonus: bool) -> Check:  # noqa: ARG001
    forbidden_subs = project.forbidden_makefile_substrings
    required_subs = project.required_makefile_substrings
    forbidden_compilers = project.forbidden_makefile_compilers

    async def run(ctx: CheckContext) -> list[CheckResult]:
        path = ctx.repo_dir / "Makefile"
        if not path.exists():
            return [
                CheckResult(
                    name="Makefile rules",
                    passed=False,
                    summary="Makefile が見つかりません",
                )
            ]
        text = path.read_text(errors="replace")
        body = _strip_comments(text)

        results: list[CheckResult] = []

        # Forbidden substrings
        bad_subs = [s for s in forbidden_subs if s in body]
        results.append(
            CheckResult(
                name="Makefile: forbidden substrings",
                passed=not bad_subs,
                summary=(
                    "Makefile に禁止された記述があります: " + ", ".join(repr(s) for s in bad_subs)
                    if bad_subs
                    else ""
                ),
            )
        )

        # Required substrings
        missing_subs = [s for s in required_subs if s not in body]
        results.append(
            CheckResult(
                name="Makefile: required substrings",
                passed=not missing_subs,
                summary=(
                    "Makefile に必須の記述が含まれていません: "
                    + ", ".join(repr(s) for s in missing_subs)
                    if missing_subs
                    else ""
                ),
            )
        )

        # Forbidden compilers used as command word.
        # Match patterns like "gcc " or "$(GCC)" or "\tgcc" (tab + name).
        compiler_findings: list[str] = []
        for cc in forbidden_compilers:
            pat = re.compile(rf"(?:^|[\s\t=:(${{]){re.escape(cc)}(?=[\s\t]|$)", re.MULTILINE)
            if pat.search(body):
                compiler_findings.append(cc)
        results.append(
            CheckResult(
                name="Makefile: compiler must be cc",
                passed=not compiler_findings,
                summary=(
                    "Makefile が `cc` 以外のコンパイラを呼び出しています: "
                    + ", ".join(compiler_findings)
                    if compiler_findings
                    else ""
                ),
            )
        )

        # Required rules (target names)
        targets = list(project.required_make_targets)
        if bonus and project.bonus_make_target:
            targets.append(project.bonus_make_target)
        rule_re = re.compile(r"^\s*([A-Za-z0-9_./\$()]+)\s*:", re.MULTILINE)
        defined_rules = {m.group(1).strip() for m in rule_re.finditer(body)}
        # Tolerate $(NAME) since it's expanded.
        # Subject only mandates the literal targets `all`, `clean`, etc.
        missing_rules = [t for t in targets if t not in defined_rules]
        results.append(
            CheckResult(
                name="Makefile: required rules present",
                passed=not missing_rules,
                summary=(
                    f"Makefile に必須ルールが定義されていません: {missing_rules}"
                    if missing_rules
                    else ""
                ),
            )
        )

        return results

    return run
