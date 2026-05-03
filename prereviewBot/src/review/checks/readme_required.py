from __future__ import annotations

import re

from review.check import Check, CheckContext, CheckResult
from review.projects.base import ProjectSpec


def readme_required_check(project: ProjectSpec, *, bonus: bool) -> Check:  # noqa: ARG001
    sections = project.readme_required_sections
    first_line_pattern = project.readme_first_line_pattern

    async def run(ctx: CheckContext) -> list[CheckResult]:
        readme = ctx.repo_dir / "README.md"
        if not readme.exists():
            return [
                CheckResult(
                    name="README.md present",
                    passed=False,
                    summary="リポジトリ直下に README.md が存在しません (subject Chapter V)",
                )
            ]
        text = readme.read_text(errors="replace")
        results: list[CheckResult] = []

        # First line must match the prescribed italicized statement.
        if first_line_pattern:
            first_line = text.lstrip().splitlines()[0] if text.strip() else ""
            ok = re.match(first_line_pattern, first_line) is not None
            results.append(
                CheckResult(
                    name="README: first line credits",
                    passed=ok,
                    summary=(
                        "README.md の 1 行目が subject 規定 "
                        '"*This project has been created as part of the 42 curriculum '
                        'by <login>...*" に一致しません'
                        if not ok
                        else ""
                    ),
                )
            )

        # Required sections (use markdown heading detection, case-insensitive).
        heading_re = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", re.MULTILINE)
        headings = {m.group(1).strip().lower() for m in heading_re.finditer(text)}
        for section in sections:
            present = section.lower() in headings
            results.append(
                CheckResult(
                    name=f"README: `{section}` section",
                    passed=present,
                    summary=(
                        f"README.md に `{section}` セクション (Markdown 見出し) が見当たりません"
                        if not present
                        else ""
                    ),
                )
            )
        return results

    return run
