from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

log = logging.getLogger("intraBot.cog.notify")


class NotifyCog(commands.Cog):
    """自分が evaluator/evaluated になった scale_team を検出して DM で通知。"""

    def __init__(self, bot: commands.Bot, poll_seconds: int):
        self.bot = bot
        self.poll_seconds = poll_seconds
        # 起動時の "既存 scale_team" は通知しないため、from_ts を起点に絞る
        self.from_ts: datetime = datetime.now(timezone.utc) - timedelta(minutes=5)
        self.poll.change_interval(seconds=poll_seconds)
        self.poll.start()

    def cog_unload(self) -> None:
        self.poll.cancel()

    @tasks.loop(seconds=60)
    async def poll(self) -> None:
        try:
            users = await self.bot.store.all_linked()
        except Exception:
            log.exception("notify: fetch linked users failed")
            return

        since_iso = self.from_ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        for u in users:
            try:
                rows = await self.bot.client.get_user_scale_teams(u.intra_user_id, since_iso=since_iso)
            except Exception as e:
                log.warning("notify: scale_teams fetch failed for %s: %s", u.intra_login, e)
                continue
            for st in rows:
                sid = int(st["id"])
                if await self.bot.store.is_notify_seen(u.discord_id, sid):
                    continue
                await self._dispatch(u.discord_id, u.intra_login, st)
                await self.bot.store.mark_notify_seen(u.discord_id, sid)

    @poll.before_loop
    async def _wait_ready(self) -> None:
        await self.bot.wait_until_ready()

    async def _dispatch(self, discord_id: str, login: str, st: dict) -> None:
        try:
            user = await self.bot.fetch_user(int(discord_id))
        except Exception:
            log.warning("notify: cannot resolve discord user %s", discord_id)
            return

        proj = (st.get("team", {}).get("project_id") or "?")
        team_name = st.get("team", {}).get("name", "?")
        scale = st.get("scale", {}).get("name", "")
        begin_at = st.get("begin_at", "")
        corrector = (st.get("corrector") or {}).get("login")
        correcteds = [c.get("login") for c in (st.get("correcteds") or [])]

        role = "evaluator" if corrector == login else "evaluated"
        opp = ", ".join(correcteds) if role == "evaluator" else (corrector or "?")

        embed = discord.Embed(
            title=f"📅 新しいレビュー ({role})",
            color=0xF1C40F,
        )
        embed.add_field(name="チーム", value=f"`{team_name}` (project_id: {proj})", inline=False)
        embed.add_field(name="相手", value=f"`{opp}`", inline=True)
        embed.add_field(name="スケール", value=scale or "—", inline=True)
        embed.add_field(name="開始", value=begin_at or "—", inline=True)
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            log.info("notify: DM blocked for discord_id=%s", discord_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NotifyCog(bot, bot.notify_poll_seconds))
