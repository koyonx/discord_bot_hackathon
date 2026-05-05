from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from cogs._helpers import truncate

log = logging.getLogger("intraBot.cog.online")

POOL_MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


class OnlineCog(commands.Cog):
    """現在校舎にいる cadet 一覧。host 前方一致 / piscine タイミングで絞り込み可能。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="online", description="現在校舎にいる cadet 一覧")
    @app_commands.describe(
        host_prefix="座席名の前方一致 (例: f3 → f3r1, f3r2 ...)",
        pool_year="入学(piscine) の年。例: 2024",
        pool_month="入学(piscine) の月",
    )
    @app_commands.choices(
        pool_month=[Choice(name=m, value=m) for m in POOL_MONTHS],
    )
    async def online(
        self,
        interaction: discord.Interaction,
        host_prefix: str | None = None,
        pool_year: int | None = None,
        pool_month: Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer(thinking=True)

        try:
            locs = await self.bot.client.get_campus_active_locations(self.bot.campus_id)
        except Exception as e:
            log.error("online: active locations fetch failed: %s", e)
            await interaction.followup.send(f"❌ 在校者取得失敗: {e}")
            return

        # piscine フィルタが指定されたらコホート ID 集合を取得
        cohort_ids: set[int] | None = None
        pm_value = pool_month.value if pool_month else None
        cohort_label_parts: list[str] = []
        if pool_year is not None or pm_value is not None:
            try:
                cohort = await self.bot.client.get_campus_users(
                    self.bot.campus_id,
                    pool_year=pool_year,
                    pool_month=pm_value,
                )
            except Exception as e:
                log.error("online: cohort fetch failed (year=%s, month=%s): %s", pool_year, pm_value, e)
                await interaction.followup.send(f"❌ コホート取得失敗: {e}")
                return
            cohort_ids = {int(u["id"]) for u in cohort}
            if pm_value:
                cohort_label_parts.append(pm_value.capitalize())
            if pool_year is not None:
                cohort_label_parts.append(str(pool_year))

        # 絞り込み
        rows: list[tuple[str, str]] = []
        for loc in locs:
            host = loc.get("host") or "?"
            user = loc.get("user") or {}
            uid = user.get("id")
            login = user.get("login") or "?"
            if host_prefix and not host.lower().startswith(host_prefix.lower()):
                continue
            if cohort_ids is not None and (uid is None or int(uid) not in cohort_ids):
                continue
            rows.append((host, login))

        # ラベル組み立て
        title_tags: list[str] = []
        if host_prefix:
            title_tags.append(f"`{host_prefix}*`")
        if cohort_label_parts:
            title_tags.append(" ".join(cohort_label_parts) + " piscine")
        suffix = f" — {' / '.join(title_tags)}" if title_tags else ""

        if not rows:
            cond = f" ({' / '.join(title_tags)})" if title_tags else ""
            await interaction.followup.send(f"該当者なし{cond} 🌃")
            return

        rows.sort(key=lambda r: r[0])
        embed = discord.Embed(
            title=f"💻 在校中 ({len(rows)} 人){suffix}",
            color=0x00BABC,
        )
        shown = rows[:80]
        embed.description = truncate(
            "\n".join(f"`{host}` — **{login}**" for host, login in shown),
            n=4000,
        )
        if len(rows) > len(shown):
            embed.set_footer(text=f"... 他 {len(rows) - len(shown)} 人")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OnlineCog(bot))
