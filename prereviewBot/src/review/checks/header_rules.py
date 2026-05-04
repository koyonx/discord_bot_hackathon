from __future__ import annotations

import re

from review.check import Check, CheckContext, CheckResult
from review.projects.base import ProjectSpec


def _header_paths(repo_dir, bonus: bool):
    paths = sorted(repo_dir.glob("*.h"))
    if not bonus:
        paths = [p for p in paths if not p.stem.endswith("_bonus")]
    return paths


def header_rules_check(project: ProjectSpec, *, bonus: bool) -> Check:
    forbidden_kw = project.forbidden_header_keywords
    typedef_name = project.bonus_typedef_name

    async def run(ctx: CheckContext) -> list[CheckResult]:
        results: list[CheckResult] = []
        headers = _header_paths(ctx.repo_dir, bonus)
        if not headers:
            results.append(
                CheckResult(
                    name="header: present",
                    passed=False,
                    summary="`*.h` ヘッダがリポジトリに見つかりません",
                )
            )
            return results

        # Forbidden keywords (strip line comments + block comments roughly).
        for kw in forbidden_kw:
            findings: list[str] = []
            kw_re = re.compile(rf"\b{re.escape(kw)}\b")
            for h in headers:
                txt = h.read_text(errors="replace")
                txt = re.sub(r"//[^\n]*", "", txt)
                txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.DOTALL)
                if kw_re.search(txt):
                    findings.append(h.name)
            results.append(
                CheckResult(
                    name=f"header: forbidden keyword `{kw}`",
                    passed=not findings,
                    summary=(
                        f"ヘッダに `{kw}` が含まれています ({', '.join(findings)})。"
                        "subject により禁止されています"
                        if findings
                        else ""
                    ),
                )
            )

        # t_list typedef must exist when bonus.
        if bonus and typedef_name:
            joined = "\n\n".join(h.read_text(errors="replace") for h in headers)
            joined = re.sub(r"//[^\n]*", "", joined)
            joined = re.sub(r"/\*.*?\*/", "", joined, flags=re.DOTALL)
            present = re.search(
                rf"typedef\s+struct\s+\w+\s*{{[^}}]*}}\s*{re.escape(typedef_name)}\s*;",
                joined,
                re.DOTALL,
            )
            results.append(
                CheckResult(
                    name=f"header: bonus typedef `{typedef_name}`",
                    passed=bool(present),
                    summary=(
                        f"bonus 提出には `{typedef_name}` の typedef がヘッダに必要"
                        if not present
                        else ""
                    ),
                )
            )

        return results

    return run
