from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import cursus_pick_main, truncate

log = logging.getLogger("intraBot.cog.status")


class StatusCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="status", description="42 cadet の情報を表示")
    @app_commands.describe(login="42 の login (例: jdoe)")
    async def status(self, interaction: discord.Interaction, login: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            user = await self.bot.client.get_user(login)
        except Exception as e:
            log.error("status: get_user(%s) failed: %s", login, e)
            await interaction.followup.send(f"❌ user `{login}` が見つかりません: {e}")
            return

        user_id = int(user["id"])

        # 並列で取りに行く
        import asyncio
        cursus_users, projects_users, active_loc, last_loc, closes = await asyncio.gather(
            self.bot.client.get_cursus_users(user_id),
            self.bot.client.get_projects_users(user_id),
            self.bot.client.get_user_active_location(user_id),
            self.bot.client.get_user_last_location(user_id),
            self.bot.client.get_user_closes(user_id),
            return_exceptions=True,
        )
        # gather(return_exceptions=True) で吸収されたエラーをログに出す
        for label, val in (
            ("cursus_users", cursus_users),
            ("projects_users", projects_users),
            ("active_loc", active_loc),
            ("last_loc", last_loc),
            ("closes", closes),
        ):
            if isinstance(val, Exception):
                log.error("status[%s]: %s fetch failed: %s", login, label, val)

        cursus_users = cursus_users if isinstance(cursus_users, list) else []
        projects_users = projects_users if isinstance(projects_users, list) else []
        closes = closes if isinstance(closes, list) else []

        embed = self._build_embed(user, cursus_users, projects_users, active_loc, last_loc, closes)
        await interaction.followup.send(embed=embed)

    def _build_embed(
        self,
        user: dict,
        cursus_users: list[dict],
        projects_users: list[dict],
        active_loc: dict | None,
        last_loc: dict | None,
        closes: list[dict],
    ) -> discord.Embed:
        login = user["login"]
        display = user.get("displayname") or user.get("usual_full_name") or login
        embed = discord.Embed(
            title=f"{display} ({login})",
            url=f"https://profile.intra.42.fr/users/{login}",
            color=0x00BABC,
        )
        if (img := user.get("image", {}).get("link")):
            embed.set_thumbnail(url=img)

        # 座席
        if isinstance(active_loc, dict) and active_loc:
            embed.add_field(name="🪑 座席", value=f"`{active_loc.get('host', '?')}` (在校中)", inline=True)
        elif isinstance(last_loc, dict) and last_loc:
            embed.add_field(name="🪑 座席", value=f"オフライン (最終: `{last_loc.get('host', '?')}`)", inline=True)
        else:
            embed.add_field(name="🪑 座席", value="—", inline=True)

        # レベル / BH
        cu = cursus_pick_main(cursus_users)
        if cu:
            embed.add_field(name="📈 レベル", value=f"{cu.get('level', 0):.2f}", inline=True)
            bh = cu.get("blackholed_at")
            embed.add_field(name="🕳 BH", value=_fmt_bh(bh), inline=True)
        else:
            embed.add_field(name="📈 レベル", value="—", inline=True)
            embed.add_field(name="🕳 BH", value="—", inline=True)

        # eval point
        embed.add_field(
            name="✏️ eval point",
            value=str(user.get("correction_point", 0)),
            inline=True,
        )

        # freeze
        embed.add_field(name="❄️ freeze", value=_fmt_freeze(closes), inline=True)
        # spacer
        embed.add_field(name="​", value="​", inline=True)

        # 合格課題
        passed = sorted(
            [p for p in projects_users if p.get("validated?")],
            key=lambda p: (p.get("marked_at") or ""),
            reverse=True,
        )
        if passed:
            lines = []
            for p in passed[:15]:
                name = (p.get("project") or {}).get("name", "?")
                mark = p.get("final_mark")
                lines.append(f"✅ **{name}** — {mark if mark is not None else '—'}")
            embed.add_field(name=f"🏆 合格 ({len(passed)})", value=truncate("\n".join(lines)), inline=False)
        else:
            embed.add_field(name="🏆 合格", value="—", inline=False)

        # 進行中
        in_progress = [
            p for p in projects_users
            if p.get("status") == "in_progress" and not p.get("validated?")
        ]
        if in_progress:
            lines = []
            for p in in_progress[:10]:
                name = (p.get("project") or {}).get("name", "?")
                lines.append(f"🛠 {name}")
            embed.add_field(name=f"🚧 進行中 ({len(in_progress)})", value=truncate("\n".join(lines)), inline=False)

        embed.set_footer(text=f"intra id: {user['id']}")
        return embed


def _fmt_bh(bh: str | None) -> str:
    """blackholed_at の表示。

    `blackholed_at` は **BH デッドライン** (この日までに level を上げないと BH'd) を表すが、
    - 過去日付 = 必ずしも "BH 済" ではない (高 level で BH 解除済 / internship 中など複数ありうる)
    - 未来日付 = まだ猶予あり

    ここでは断定的な解釈を避けて、デッドライン日付と残/経過日数を中立に出す。
    """
    if not bh:
        return "—"
    try:
        dt = datetime.fromisoformat(bh.replace("Z", "+00:00"))
        days = (dt - datetime.now(timezone.utc)).days
        if days >= 0:
            return f"{dt.date()} (残 {days}日)"
        return f"{dt.date()} ({-days}日経過)"
    except Exception:
        log.warning("bh date parse failed: raw=%r", bh)
        return bh


def _fmt_freeze(closes: list[dict]) -> str:
    if not closes:
        return "—"
    now = datetime.now(timezone.utc)
    active = []
    for c in closes:
        # 42 closes: state in {"closed", "frozen"} の解釈は環境依存。
        # 期間中 (from_date <= now <= until_date) を active と扱う。
        try:
            f = c.get("from_date")
            u = c.get("until_date")
            if f and u:
                fd = datetime.fromisoformat(f.replace("Z", "+00:00"))
                ud = datetime.fromisoformat(u.replace("Z", "+00:00"))
                if fd <= now <= ud:
                    active.append((fd, ud, c.get("reason") or c.get("state") or "freeze"))
        except Exception:
            log.warning("freeze close parse failed: from=%r until=%r", c.get("from_date"), c.get("until_date"))
            continue
    if active:
        fd, ud, reason = active[0]
        return f"❄️ {reason} ({fd.date()} 〜 {ud.date()})"
    return f"履歴 {len(closes)} 件"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StatusCog(bot))
