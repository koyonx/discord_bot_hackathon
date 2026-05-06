from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from cogs._helpers import NotLinkedError, get_valid_user_token
from intra.client import IntraError

log = logging.getLogger("intraBot.cog.project")


class ProjectCog(commands.GroupCog, name="project", description="自分の project を retry / giveup"):
    """`/project retry|giveup` — projects_users API を本人 OAuth で叩く。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    # ===== /project retry =====

    @app_commands.command(name="retry", description="failed の project をリトライ")
    @app_commands.describe(project="project の slug または name")
    async def retry(self, interaction: discord.Interaction, project: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            user, token = await get_valid_user_token(
                self.bot.store, self.bot.client, str(interaction.user.id)
            )
        except NotLinkedError:
            await interaction.followup.send(
                "先に `/link` で 42 アカウントを紐付けてください。", ephemeral=True
            )
            return

        proj = await self._resolve_project(project)
        if not proj:
            await interaction.followup.send(
                f"❌ project `{project}` が見つかりません。", ephemeral=True
            )
            return
        proj_id = int(proj["id"])
        proj_name = proj.get("name", project)

        try:
            pu = await self.bot.client.find_user_project(
                user.intra_user_id, proj_id, user_token=token
            )
        except IntraError as e:
            log.error("project retry: lookup failed: %s", e)
            await interaction.followup.send(f"❌ 検索失敗: {e}", ephemeral=True)
            return
        if not pu:
            await interaction.followup.send(
                f"❌ `{proj_name}` には登録されていません。", ephemeral=True
            )
            return

        try:
            await self.bot.client.retry_project(token, int(pu["id"]))
        except IntraError as e:
            log.error("project retry: failed: %s", e)
            await interaction.followup.send(f"❌ リトライ失敗: {e}", ephemeral=True)
            return
        await interaction.followup.send(
            f"✅ `{proj_name}` をリトライしました。", ephemeral=True
        )

    @retry.autocomplete("project")
    async def _retry_ac(
        self, interaction: discord.Interaction, current: str
    ) -> list[Choice[str]]:
        return self._project_autocomplete(current)

    # ===== /project giveup =====

    @app_commands.command(name="giveup", description="進行中の project を give up")
    @app_commands.describe(project="project の slug または name")
    async def giveup(self, interaction: discord.Interaction, project: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            user, token = await get_valid_user_token(
                self.bot.store, self.bot.client, str(interaction.user.id)
            )
        except NotLinkedError:
            await interaction.followup.send(
                "先に `/link` で 42 アカウントを紐付けてください。", ephemeral=True
            )
            return

        proj = await self._resolve_project(project)
        if not proj:
            await interaction.followup.send(
                f"❌ project `{project}` が見つかりません。", ephemeral=True
            )
            return
        proj_id = int(proj["id"])
        proj_name = proj.get("name", project)

        try:
            pu = await self.bot.client.find_user_project(
                user.intra_user_id, proj_id, user_token=token
            )
        except IntraError as e:
            log.error("project giveup: lookup failed: %s", e)
            await interaction.followup.send(f"❌ 検索失敗: {e}", ephemeral=True)
            return
        if not pu:
            await interaction.followup.send(
                f"❌ `{proj_name}` には登録されていません。", ephemeral=True
            )
            return

        # 確認ボタンを出す
        view = GiveUpConfirm(self.bot, str(interaction.user.id), int(pu["id"]), proj_name)
        await interaction.followup.send(
            f"⚠️ `{proj_name}` を **give up** しますか? この操作は取り消せません。",
            view=view,
            ephemeral=True,
        )

    @giveup.autocomplete("project")
    async def _giveup_ac(
        self, interaction: discord.Interaction, current: str
    ) -> list[Choice[str]]:
        return self._project_autocomplete(current)

    # ===== helpers =====

    def _project_autocomplete(self, current: str) -> list[Choice[str]]:
        finder = self.bot.get_cog("FinderCog")
        projects = list(getattr(finder, "_project_cache", []) or [])
        if not projects:
            return []
        q = (current or "").lower().strip()
        if not q:
            sample = sorted(projects, key=lambda p: p.get("slug") or "")[:25]
            return [Choice(name=p.get("name", p["slug"]), value=p["slug"]) for p in sample]
        matches = [
            p for p in projects
            if q in (p.get("slug") or "").lower() or q in (p.get("name") or "").lower()
        ]
        matches.sort(key=lambda p: (
            0 if (p.get("slug") or "").lower() == q else
            1 if (p.get("slug") or "").lower().startswith(q) else 2,
            p.get("slug") or "",
        ))
        return [Choice(name=p.get("name", p["slug"]), value=p["slug"]) for p in matches[:25]]

    async def _resolve_project(self, query: str) -> dict | None:
        finder = self.bot.get_cog("FinderCog")
        if finder is not None:
            projects = list(getattr(finder, "_project_cache", []) or [])
            nl = query.lower().strip()
            for p in projects:
                if (p.get("slug") or "").lower() == nl or (p.get("name") or "").lower() == nl:
                    return p
        return await self.bot.client.find_project(query)


class GiveUpConfirm(discord.ui.View):
    """give up 確認ボタン view (60s timeout)."""

    def __init__(self, bot: commands.Bot, discord_id: str, projects_user_id: int, project_name: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.discord_id = discord_id
        self.projects_user_id = projects_user_id
        self.project_name = project_name
        self._done = False

    @discord.ui.button(label="Give Up", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self._done:
            await interaction.response.send_message("既に処理済", ephemeral=True)
            return
        self._done = True
        try:
            user, token = await get_valid_user_token(
                self.bot.store, self.bot.client, self.discord_id
            )
        except NotLinkedError:
            await interaction.response.send_message("未紐付け", ephemeral=True)
            return
        try:
            await self.bot.client.giveup_project(token, self.projects_user_id)
        except IntraError as e:
            log.error("project giveup: pu_id=%s failed: %s", self.projects_user_id, e)
            await interaction.response.send_message(
                f"❌ give up 失敗: {e}", ephemeral=True
            )
            return
        await interaction.response.edit_message(
            content=f"🗑 `{self.project_name}` を give up しました。",
            view=None,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self._done = True
        await interaction.response.edit_message(
            content="キャンセルしました。", view=None
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProjectCog(bot))
