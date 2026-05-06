from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("intraBot.cog.link")


class LinkCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="link", description="42 アカウントと紐付け (DM で URL を送ります)")
    async def link(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        url = await self.bot.oauth.make_authorize_url(str(interaction.user.id))
        try:
            await interaction.user.send(
                "👋 42 アカウントの紐付けはこちらから行ってください (5 分以内に開いてください):\n" + url
            )
        except discord.Forbidden:
            log.warning("link: DM forbidden for discord_id=%s", interaction.user.id)
            await interaction.followup.send(
                "DM が送れませんでした。サーバー設定で DM を許可してから `/link` を再実行してください。",
                ephemeral=True,
            )
            return
        await interaction.followup.send("DM に紐付け用 URL を送りました。", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LinkCog(bot))
