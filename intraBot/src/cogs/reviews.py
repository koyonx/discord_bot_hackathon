from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import NotLinkedError, get_valid_user_token
from intra.client import IntraError

log = logging.getLogger("intraBot.cog.reviews")
JST = timezone(timedelta(hours=9))


class ReviewsCog(commands.GroupCog, name="reviews", description="自分のレビュー予約 (list/cancel)"):
    """`/reviews list|cancel` — scale_teams を本人 OAuth で操作。

    book (新規予約) は API endpoint (/v2/projects/:id/slots, /v2/teams/:id/slots) が
    student scope では 403/404 になり実装不可のため intra UI で行うこと。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    # ===== /reviews list =====

    @app_commands.command(name="list", description="今後のレビュー予約一覧")
    async def list_reviews(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            user, _ = await get_valid_user_token(
                self.bot.store, self.bot.client, str(interaction.user.id)
            )
        except NotLinkedError:
            await interaction.followup.send(
                "先に `/link` で 42 アカウントを紐付けてください。", ephemeral=True
            )
            return

        try:
            sts = await self.bot.client.get_user_scale_teams(user.intra_user_id)
        except IntraError as e:
            log.error("reviews list: scale_teams fetch failed: %s", e)
            await interaction.followup.send(f"❌ 取得失敗: {e}", ephemeral=True)
            return

        now = datetime.now(timezone.utc)
        upcoming: list[tuple[datetime, dict]] = []
        for st in sts:
            try:
                begin = datetime.fromisoformat((st.get("begin_at") or "").replace("Z", "+00:00"))
            except Exception:
                continue
            if begin >= now:
                upcoming.append((begin, st))
        upcoming.sort(key=lambda x: x[0])

        if not upcoming:
            await interaction.followup.send(
                "予約中のレビューはありません。", ephemeral=True
            )
            return

        blocks = []
        for begin, st in upcoming[:10]:
            jst_b = begin.astimezone(JST)
            team = st.get("team") or {}
            corrector_login = (st.get("corrector") or {}).get("login")
            correcteds = [c.get("login") for c in (st.get("correcteds") or []) if c.get("login")]
            role = "evaluator" if corrector_login == user.intra_login else "evaluated"
            opp = ", ".join(correcteds) if role == "evaluator" else (corrector_login or "?")
            scale = (st.get("scale") or {}).get("name", "—")
            blocks.append(
                f"**{team.get('name', '?')}**\n"
                f"⏰ {jst_b:%m/%d (%a) %H:%M}\n"
                f"📝 scale: {scale}\n"
                f"👤 role: {role} (相手: `{opp}`)\n"
                f"🆔 `{st['id']}`"
            )
        embed = discord.Embed(
            title=f"📅 自分のレビュー予約 ({len(upcoming)} 件)",
            description=("\n" + "─" * 24 + "\n\n").join(blocks),
            color=0x00BABC,
        )
        if len(upcoming) > 10:
            embed.set_footer(text=f"... 他 {len(upcoming) - 10} 件")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ===== /reviews cancel =====

    @app_commands.command(name="cancel", description="レビュー予約をキャンセル")
    @app_commands.describe(scale_team_id="`/reviews list` で表示される 🆔")
    async def cancel(self, interaction: discord.Interaction, scale_team_id: int) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            _, token = await get_valid_user_token(
                self.bot.store, self.bot.client, str(interaction.user.id)
            )
        except NotLinkedError:
            await interaction.followup.send(
                "先に `/link` で 42 アカウントを紐付けてください。", ephemeral=True
            )
            return
        try:
            await self.bot.client.cancel_scale_team(token, scale_team_id)
        except IntraError as e:
            log.error("reviews cancel: id=%s failed: %s", scale_team_id, e)
            await interaction.followup.send(f"❌ キャンセル失敗: {e}", ephemeral=True)
            return
        await interaction.followup.send(
            f"🗑 review `{scale_team_id}` をキャンセルしました。", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReviewsCog(bot))
