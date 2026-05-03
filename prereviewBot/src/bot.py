from __future__ import annotations

import io
import logging
from pathlib import Path

import discord
from discord import app_commands

from config import Config, load_config
from review.projects import registry
from review.reporter import format_report
from review.runner import ReviewRequest, run_review
from review.workspace import InvalidRepositoryUrl, validate_github_url

log = logging.getLogger(__name__)

# Discord caps a single message at 2000 characters. If the report exceeds this,
# we attach it as a file instead.
DISCORD_MESSAGE_LIMIT = 1900


def _project_choices() -> list[app_commands.Choice[str]]:
    return [app_commands.Choice(name=n, value=n) for n in registry.all_names()]


class PrereviewBot(discord.Client):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.config = config
        self.tree = app_commands.CommandTree(self)
        self._register_commands()

    async def setup_hook(self) -> None:
        if self.config.discord_guild_id is not None:
            guild = discord.Object(id=self.config.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("synced commands to guild %s", self.config.discord_guild_id)
        else:
            await self.tree.sync()
            log.info("synced commands globally")

    def _register_commands(self) -> None:
        @self.tree.command(
            name="prereview",
            description="42Tokyo の課題リポジトリを自動レビューします (結果は本人にのみ表示)",
        )
        @app_commands.describe(
            project="レビュー対象の課題",
            repository="レビュー対象の public GitHub リポジトリ URL",
            bonus="bonus パートも含めてレビューするか",
        )
        @app_commands.choices(project=_project_choices())
        async def prereview(  # noqa: ARG001 — registered as a closure
            interaction: discord.Interaction,
            project: app_commands.Choice[str],
            repository: str,
            bonus: bool = False,
        ) -> None:
            await self._handle_prereview(interaction, project.value, repository, bonus)

    async def _handle_prereview(
        self,
        interaction: discord.Interaction,
        project_name: str,
        repository: str,
        bonus: bool,
    ) -> None:
        try:
            project = registry.get(project_name)
        except KeyError:
            await interaction.response.send_message(
                f"未対応のプロジェクトです: {project_name}", ephemeral=True
            )
            return

        try:
            canonical = validate_github_url(repository)
        except InvalidRepositoryUrl as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        log.info(
            "review requested by %s: project=%s repo=%s bonus=%s",
            interaction.user.id,
            project_name,
            canonical,
            bonus,
        )

        outcome = await run_review(
            ReviewRequest(project=project, repository_url=canonical, bonus=bonus),
            workspace_root=Path(self.config.workspace_root),
            check_timeout=self.config.check_timeout_seconds,
            total_timeout=self.config.total_timeout_seconds,
        )
        report = format_report(outcome)

        if len(report) <= DISCORD_MESSAGE_LIMIT:
            await interaction.followup.send(report, ephemeral=True)
        else:
            preview = report[:DISCORD_MESSAGE_LIMIT] + "\n…(続きは添付ファイル)…"
            file = discord.File(
                io.BytesIO(report.encode("utf-8")),
                filename="prereview.md",
            )
            await interaction.followup.send(preview, file=file, ephemeral=True)


async def run_bot() -> None:
    config = load_config()
    bot = PrereviewBot(config)
    async with bot:
        await bot.start(config.discord_token)
