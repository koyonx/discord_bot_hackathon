from __future__ import annotations

import logging

import discord
from discord.ext import commands

log = logging.getLogger("intraBot.cog.welcome")


class WelcomeCog(commands.Cog):
    """新規メンバーが入ったら DM で `/link` の案内を送り、welcome チャンネルにもメンション投稿"""

    def __init__(self, bot: commands.Bot, welcome_channel_id: int | None):
        self.bot = bot
        self.welcome_channel_id = welcome_channel_id

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return

        dm_text = (
            f"ようこそ **{member.guild.name}** へ!\n"
            "このサーバーでは 42 intra と連携した bot を使えます。"
            " まずは任意のチャンネルで `/link` を実行して 42 アカウントを紐付けてください。"
        )
        try:
            await member.send(dm_text)
        except discord.Forbidden:
            log.info("welcome: DM blocked for %s", member.id)

        if self.welcome_channel_id:
            channel = member.guild.get_channel(self.welcome_channel_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(
                        f"👋 {member.mention} ようこそ! `/link` で 42 アカウントを紐付けてね。"
                    )
                except discord.Forbidden:
                    log.warning("welcome: cannot post to channel %s", self.welcome_channel_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot, bot.welcome_channel_id))
