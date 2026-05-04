from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from review.check import CheckContext, CheckResult
from review.projects.base import ProjectSpec
from review.workspace import cloned_workspace

log = logging.getLogger(__name__)


@dataclass
class ReviewRequest:
    project: ProjectSpec
    repository_url: str
    bonus: bool


@dataclass
class ReviewOutcome:
    project: ProjectSpec
    repository_url: str
    bonus: bool
    results: list[CheckResult]
    duration_seconds: float
    fatal_error: str | None = None


async def run_review(
    request: ReviewRequest,
    *,
    workspace_root: Path,
    check_timeout: float,
    total_timeout: float,
) -> ReviewOutcome:
    if request.project.check_builder is None:
        return ReviewOutcome(
            project=request.project,
            repository_url=request.repository_url,
            bonus=request.bonus,
            results=[],
            duration_seconds=0.0,
            fatal_error=f"{request.project.name} には check_builder が定義されていません",
        )

    start = time.monotonic()
    try:
        return await asyncio.wait_for(
            _run_review_inner(
                request,
                workspace_root=workspace_root,
                check_timeout=check_timeout,
                start=start,
            ),
            timeout=total_timeout,
        )
    except asyncio.TimeoutError:
        return ReviewOutcome(
            project=request.project,
            repository_url=request.repository_url,
            bonus=request.bonus,
            results=[],
            duration_seconds=time.monotonic() - start,
            fatal_error=f"レビュー全体が {total_timeout:.0f}s でタイムアウトしました",
        )
    except Exception as exc:
        log.exception("review failed")
        return ReviewOutcome(
            project=request.project,
            repository_url=request.repository_url,
            bonus=request.bonus,
            results=[],
            duration_seconds=time.monotonic() - start,
            fatal_error=f"想定外のエラー: {exc}",
        )


async def _run_review_inner(
    request: ReviewRequest,
    *,
    workspace_root: Path,
    check_timeout: float,
    start: float,
) -> ReviewOutcome:
    project = request.project
    assert project.check_builder is not None

    async with cloned_workspace(
        request.repository_url,
        root=workspace_root,
        timeout=min(check_timeout, 60.0),
    ) as (repo_dir, workspace_dir):
        ctx = CheckContext(
            repo_dir=repo_dir,
            workspace_dir=workspace_dir,
            project=project,
            bonus=request.bonus,
            timeout=check_timeout,
        )
        checks = project.check_builder(project, request.bonus)
        results: list[CheckResult] = []
        for check in checks:
            try:
                results.extend(await check(ctx))
            except Exception as exc:
                log.exception("check raised")
                results.append(
                    CheckResult(
                        name=getattr(check, "__name__", "check"),
                        passed=False,
                        summary=f"チェックの実行中に例外が発生: {exc}",
                    )
                )

    return ReviewOutcome(
        project=project,
        repository_url=request.repository_url,
        bonus=request.bonus,
        results=results,
        duration_seconds=time.monotonic() - start,
    )
