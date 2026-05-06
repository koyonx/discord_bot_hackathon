from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("intraBot.cog.help")


class HelpCog(commands.Cog):
    """登録済の slash command 一覧を embed で見せる。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="intraBot で使えるコマンド一覧")
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        guild = discord.Object(id=self.bot.guild_id) if hasattr(self.bot, "guild_id") else None
        cmds = self.bot.tree.get_commands(guild=guild) or self.bot.tree.get_commands()

        embed = discord.Embed(
            title="📘 intraBot コマンド一覧",
            description="42 Tokyo の intra と Discord を繋ぐ bot",
            color=0x00BABC,
        )

        # Group / subcommand を含めて全部展開
        lines: list[str] = []
        for cmd in sorted(cmds, key=lambda c: c.name):
            lines.extend(_render(cmd))
        embed.add_field(name="Commands", value="\n".join(lines) or "(no commands)", inline=False)

        embed.set_footer(text="先に /link で 42 アカウントを紐付けてください。")
        await interaction.response.send_message(embed=embed, ephemeral=True)


def _render(cmd: app_commands.Command | app_commands.Group, prefix: str = "") -> list[str]:
    """commands を `<full name> — desc` の行に展開する。Group は再帰。"""
    name = f"{prefix}{cmd.name}" if not prefix else f"{prefix} {cmd.name}"
    if isinstance(cmd, app_commands.Group):
        out: list[str] = []
        for sub in sorted(cmd.commands, key=lambda c: c.name):
            out.extend(_render(sub, prefix=name))
        return out
    desc = cmd.description or ""
    return [f"• `/{name}` — {desc}"]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
