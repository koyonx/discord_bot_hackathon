from __future__ import annotations

from review.check import CommandRun
from review.runner import ReviewOutcome

_MAX_OUTPUT_PER_RUN = 1500  # characters of stdout/stderr to include per command


def _truncate(text: str, limit: int = _MAX_OUTPUT_PER_RUN) -> str:
    text = text.rstrip()
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n…(truncated)…"


def _format_run(run: CommandRun) -> str:
    lines = [f"$ {run.command}"]
    if run.timed_out:
        lines.append(f"(timed out after {run.duration_seconds:.0f}s)")
    else:
        lines.append(f"(exit={run.returncode}, {run.duration_seconds:.1f}s)")
    body = "\n".join(filter(None, [run.stdout.rstrip(), run.stderr.rstrip()]))
    if body:
        lines.append(_truncate(body))
    return "\n".join(lines)


def format_report(outcome: ReviewOutcome) -> str:
    """Build a Discord-friendly markdown report.

    Per the product requirements: only failed checks are included. If everything
    passed, return a short success message instead.
    """
    header_lines = [
        f"**プロジェクト**: `{outcome.project.name}`"
        + (" (with bonus)" if outcome.bonus else ""),
        f"**リポジトリ**: {outcome.repository_url}",
        f"**所要時間**: {outcome.duration_seconds:.1f}s",
    ]
    if outcome.fatal_error:
        header_lines.append("")
        header_lines.append(f"❌ **致命的エラー**: {outcome.fatal_error}")
        return "\n".join(header_lines)

    failures = [r for r in outcome.results if not r.passed]
    if not failures:
        header_lines.append("")
        header_lines.append("✅ すべてのチェックに合格しました。")
        return "\n".join(header_lines)

    body: list[str] = [*header_lines, "", f"❌ 失敗 {len(failures)} 件:"]
    for result in failures:
        body.append("")
        body.append(f"### {result.name}")
        if result.summary:
            body.append(result.summary)
        for run in result.runs:
            body.append("```")
            body.append(_format_run(run))
            body.append("```")
    return "\n".join(body)
