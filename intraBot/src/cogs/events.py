from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands, tasks

from cogs._helpers import NotLinkedError, get_valid_user_token
from intra.client import IntraError

log = logging.getLogger("intraBot.cog.events")

JST = timezone(timedelta(hours=9))

KIND_EMOJI = {
    "event": "🎉",
    "workshop": "🛠",
    "rush": "🏃",
    "speed_working": "⚡",
    "pedago": "📚",
    "exam": "📝",
    "atelier": "🎨",
    "conference": "🎤",
    "meet_up": "🤝",
    "association": "🏛",
    "extern": "🌐",
    "partnership": "🤝",
    "hackathon": "💻",
    "other": "📌",
}

# /events list の kind 引数の Choice 候補。観測上ある主要なものを並べる。
KIND_CHOICES = [
    Choice(name="🎉 event", value="event"),
    Choice(name="🛠 workshop", value="workshop"),
    Choice(name="📝 exam", value="exam"),
    Choice(name="🏃 rush", value="rush"),
    Choice(name="📚 pedago", value="pedago"),
    Choice(name="🎨 atelier", value="atelier"),
    Choice(name="🎤 conference", value="conference"),
    Choice(name="🤝 meet_up", value="meet_up"),
    Choice(name="🏛 association", value="association"),
    Choice(name="💻 hackathon", value="hackathon"),
]

# リマインダーの "1 時間前" ウィンドウ
REMINDER_LEAD_MIN = 60
REMINDER_WINDOW_MIN = 10  # [LEAD-WINDOW/2, LEAD+WINDOW/2] の範囲を 1h 扱い
REMINDER_POLL_SEC = 300  # 5 分ごと


class EventsCog(commands.GroupCog, name="events", description="42 Tokyo イベント"):
    """`/events list|register|leave|show` + 開始 1h 前リマインダー BG task。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminder.change_interval(seconds=REMINDER_POLL_SEC)
        self.reminder.start()
        super().__init__()

    def cog_unload(self) -> None:
        self.reminder.cancel()

    # ===== /events list =====

    @app_commands.command(name="list", description="イベント一覧 (今後 / 過去 / kind / theme で絞込)")
    @app_commands.describe(
        days="表示する日数 (今後 N 日 / 過去 N 日。省略時 30)",
        past="過去のイベントを表示する",
        kind="種別で絞り込み",
        theme="theme 名で絞り込み (部分一致)",
    )
    @app_commands.choices(kind=KIND_CHOICES)
    async def list_events(
        self,
        interaction: discord.Interaction,
        days: int = 30,
        past: bool = False,
        kind: Choice[str] | None = None,
        theme: str | None = None,
    ) -> None:
        await interaction.response.defer(thinking=True)
        import asyncio
        evts_raw, exams_raw = await asyncio.gather(
            self.bot.client.get_campus_events(self.bot.campus_id),
            self.bot.client.get_campus_exams(self.bot.campus_id),
            return_exceptions=True,
        )
        if isinstance(evts_raw, Exception):
            log.error("events list: events fetch failed: %s", evts_raw)
        if isinstance(exams_raw, Exception):
            log.error("events list: exams fetch failed: %s", exams_raw)
        evts: list[dict] = list(evts_raw) if isinstance(evts_raw, list) else []
        exams: list[dict] = list(exams_raw) if isinstance(exams_raw, list) else []

        # exam 側に _type と kind を補完して events と統合
        for ex in exams:
            ex["_type"] = "exam"
            ex.setdefault("kind", "exam")
        for ev in evts:
            ev["_type"] = "event"
        evts = evts + exams

        if not evts:
            await interaction.followup.send("❌ イベント取得失敗 (events / exams ともに 0 件)")
            return

        kind_value = kind.value if kind else None
        theme_value = theme.lower().strip() if theme else None

        now = datetime.now(timezone.utc)
        if past:
            cutoff_old = now - timedelta(days=days)
            cutoff_new = now
            label = f"過去 {days} 日"
        else:
            cutoff_old = now
            cutoff_new = now + timedelta(days=days)
            label = f"今後 {days} 日"

        filtered: list[tuple[datetime, datetime, dict]] = []
        for e in evts:
            try:
                begin = datetime.fromisoformat((e.get("begin_at") or "").replace("Z", "+00:00"))
                end = datetime.fromisoformat(
                    (e.get("end_at") or e.get("begin_at") or "").replace("Z", "+00:00")
                )
            except Exception:
                log.warning("events list: parse failed for event id=%s", e.get("id"))
                continue
            if not (cutoff_old <= begin <= cutoff_new):
                continue
            if kind_value and (e.get("kind") or "").lower() != kind_value:
                continue
            if theme_value:
                themes_str = " ".join(
                    (t.get("name") or "") for t in (e.get("themes") or [])
                ).lower()
                if theme_value not in themes_str:
                    continue
            filtered.append((begin, end, e))

        # 過去は新しい→古い、未来は近い→遠い
        filtered.sort(key=lambda x: x[0], reverse=past)

        suffix = []
        if kind_value:
            suffix.append(f"kind={kind_value}")
        if theme_value:
            suffix.append(f"theme~{theme_value}")
        cond = f" ({' / '.join(suffix)})" if suffix else ""

        if not filtered:
            await interaction.followup.send(f"{label}{cond} のイベントはありません 🌃")
            return

        embed = discord.Embed(
            title=f"📅 42 Tokyo イベント — {label}{cond} ({len(filtered)} 件)",
            color=0x00BABC,
        )
        blocks = [_render_event_block(b, e, evt) for b, e, evt in filtered[:10]]
        # 区切り線で 1 ブロック = 1 イベントを視覚的に分ける
        embed.description = ("\n" + "─" * 24 + "\n\n").join(blocks)
        if len(filtered) > 10:
            embed.set_footer(text=f"... 他 {len(filtered) - 10} 件 — `/events list days:90` 等で広げられます")
        await interaction.followup.send(embed=embed)

    # ===== /events show <id> =====

    @app_commands.command(name="show", description="イベントの詳細を表示")
    @app_commands.describe(event_id="イベント / exam の ID")
    async def show(self, interaction: discord.Interaction, event_id: int) -> None:
        await interaction.response.defer(thinking=True)
        evt: dict | None = None
        # event → exam の順で試す
        try:
            evt = await self.bot.client.get_event(event_id)
        except IntraError as e1:
            log.info("events show: not in events (%s), trying exams", e1)
            try:
                evt = await self.bot.client.get_exam(event_id)
                evt["_type"] = "exam"
                evt.setdefault("kind", "exam")
            except IntraError as e2:
                log.warning("events show: id=%s not found in events nor exams: %s / %s", event_id, e1, e2)
                await interaction.followup.send(
                    f"❌ id `{event_id}` は events / exams のいずれにも存在しません"
                )
                return
        try:
            begin = datetime.fromisoformat((evt.get("begin_at") or "").replace("Z", "+00:00"))
            end = datetime.fromisoformat(
                (evt.get("end_at") or evt.get("begin_at") or "").replace("Z", "+00:00")
            )
        except Exception:
            log.warning("events show: parse failed for event id=%s", event_id)
            await interaction.followup.send(f"❌ event `{event_id}` の日付パース失敗")
            return
        kind = evt.get("kind") or "other"
        emoji = KIND_EMOJI.get(kind, "📌")
        embed = discord.Embed(
            title=f"{emoji} {evt.get('name', '?')}",
            description=(evt.get("description") or "").strip()[:1000] or "—",
            color=0x00BABC,
        )
        embed.add_field(name="ID", value=f"`{event_id}`", inline=True)
        embed.add_field(name="kind", value=kind, inline=True)
        embed.add_field(name="📍 location", value=evt.get("location") or "—", inline=True)
        jst_b = begin.astimezone(JST)
        jst_e = end.astimezone(JST)
        if jst_b.date() == jst_e.date():
            time_str = f"{jst_b:%Y-%m-%d (%a) %H:%M}〜{jst_e:%H:%M} JST"
        else:
            time_str = f"{jst_b:%Y-%m-%d %H:%M}〜{jst_e:%Y-%m-%d %H:%M} JST"
        embed.add_field(name="⏰", value=time_str, inline=False)
        sub = evt.get("nbr_subscribers")
        cap = evt.get("max_people")
        embed.add_field(
            name="👥 参加",
            value=f"{sub if sub is not None else '?'}/{cap if cap else '∞'}",
            inline=True,
        )
        themes = ", ".join((t.get("name") or "?") for t in (evt.get("themes") or []))
        if themes:
            embed.add_field(name="theme", value=themes, inline=False)
        embed.set_footer(text="参加: /events register / 取消: /events leave")
        await interaction.followup.send(embed=embed)

    # ===== /events register <id> =====

    @app_commands.command(name="register", description="イベントに参加登録 (本人 OAuth)")
    @app_commands.describe(event_id="登録する event ID")
    async def register(self, interaction: discord.Interaction, event_id: int) -> None:
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
        try:
            await self.bot.client.register_event(token, event_id)
        except IntraError as e:
            log.error("events register: event=%s failed: %s", event_id, e)
            await interaction.followup.send(f"❌ 登録失敗: {e}", ephemeral=True)
            return
        await interaction.followup.send(
            f"✅ event `{event_id}` に参加登録しました ({user.intra_login})。",
            ephemeral=True,
        )

    # ===== /events leave <id> =====

    @app_commands.command(name="leave", description="イベント参加を取消 (本人 OAuth)")
    @app_commands.describe(event_id="取消する event ID")
    async def leave(self, interaction: discord.Interaction, event_id: int) -> None:
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
        try:
            registration = await self.bot.client.find_user_event_registration(
                token, user.intra_user_id, event_id
            )
        except IntraError as e:
            log.error("events leave: lookup event=%s failed: %s", event_id, e)
            await interaction.followup.send(f"❌ 検索失敗: {e}", ephemeral=True)
            return
        if not registration:
            await interaction.followup.send(
                f"event `{event_id}` には参加登録していません。", ephemeral=True
            )
            return
        try:
            await self.bot.client.leave_event(token, int(registration["id"]))
        except IntraError as e:
            log.error("events leave: delete event=%s eu_id=%s failed: %s", event_id, registration.get("id"), e)
            await interaction.followup.send(f"❌ 取消失敗: {e}", ephemeral=True)
            return
        await interaction.followup.send(
            f"🗑 event `{event_id}` の参加を取消しました。", ephemeral=True
        )

    # ===== background: 1h 前 reminder =====

    @tasks.loop(seconds=REMINDER_POLL_SEC)
    async def reminder(self) -> None:
        import asyncio
        evts_raw, exams_raw = await asyncio.gather(
            self.bot.client.get_campus_events(self.bot.campus_id),
            self.bot.client.get_campus_exams(self.bot.campus_id),
            return_exceptions=True,
        )
        if isinstance(evts_raw, Exception):
            log.warning("events reminder: events fetch failed: %s", evts_raw)
        if isinstance(exams_raw, Exception):
            log.warning("events reminder: exams fetch failed: %s", exams_raw)
        evts = list(evts_raw) if isinstance(evts_raw, list) else []
        exams = list(exams_raw) if isinstance(exams_raw, list) else []
        for ex in exams:
            ex["_type"] = "exam"
            ex.setdefault("kind", "exam")
        for ev in evts:
            ev["_type"] = "event"
        all_evts = evts + exams

        now = datetime.now(timezone.utc)
        lo = now + timedelta(minutes=REMINDER_LEAD_MIN - REMINDER_WINDOW_MIN / 2)
        hi = now + timedelta(minutes=REMINDER_LEAD_MIN + REMINDER_WINDOW_MIN / 2)

        for evt in all_evts:
            try:
                begin = datetime.fromisoformat((evt.get("begin_at") or "").replace("Z", "+00:00"))
            except Exception:
                continue
            if not (lo <= begin <= hi):
                continue
            event_id = int(evt["id"])
            etype = evt.get("_type", "event")
            try:
                if etype == "exam":
                    evt_users = await self.bot.client.get_exam_users(event_id)
                else:
                    evt_users = await self.bot.client.get_event_users(event_id)
            except Exception as e:
                log.warning("events reminder: %s_users(%s) failed: %s", etype, event_id, e)
                continue
            # event_id だけだと exam id と衝突する可能性があるので type を含めた key にする
            seen_key = event_id if etype == "event" else -event_id
            for eu in evt_users:
                login = (eu.get("user") or {}).get("login")
                if not login:
                    continue
                entry = await self.bot.store.get_by_login(login)
                if not entry:
                    continue
                if await self.bot.store.is_event_reminder_sent(entry.discord_id, seen_key):
                    continue
                await self._dm_reminder(entry.discord_id, evt, begin)
                await self.bot.store.mark_event_reminder_sent(entry.discord_id, seen_key)

    @reminder.before_loop
    async def _wait_ready(self) -> None:
        await self.bot.wait_until_ready()

    async def _dm_reminder(self, discord_id: str, evt: dict, begin_utc: datetime) -> None:
        try:
            user = await self.bot.fetch_user(int(discord_id))
        except Exception as e:
            log.warning("events reminder: fetch_user(%s) failed: %s", discord_id, e)
            return
        kind = evt.get("kind") or "other"
        emoji = KIND_EMOJI.get(kind, "📌")
        jst_b = begin_utc.astimezone(JST)
        embed = discord.Embed(
            title=f"⏰ 1 時間後にイベント開始: {emoji} {evt.get('name', '?')}",
            description=(evt.get("description") or "").strip()[:500] or "—",
            color=0xF1C40F,
        )
        embed.add_field(name="📍 location", value=evt.get("location") or "—", inline=True)
        embed.add_field(name="⏰ 開始", value=f"{jst_b:%m/%d %H:%M} JST", inline=True)
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            log.info("events reminder: DM blocked for %s", discord_id)
        except Exception:
            log.exception("events reminder: DM send failed for %s", discord_id)


def _render_event_block(begin: datetime, end: datetime, e: dict) -> str:
    """1 イベント分の markdown ブロック (description 用)。"""
    kind = e.get("kind") or "other"
    emoji = KIND_EMOJI.get(kind, "📌")
    jst_b = begin.astimezone(JST)
    jst_e = end.astimezone(JST)
    if jst_b.date() == jst_e.date():
        time_str = f"{jst_b:%m/%d (%a) %H:%M}〜{jst_e:%H:%M}"
    else:
        time_str = f"{jst_b:%m/%d %H:%M}〜{jst_e:%m/%d %H:%M}"
    location = e.get("location") or "—"
    sub = e.get("nbr_subscribers")
    cap = e.get("max_people")
    people = f"{sub if sub is not None else '?'}/{cap if cap else '∞'}"
    name = e.get("name", "?")
    return (
        f"{emoji} **{name}**\n"
        f"⏰ {time_str}\n"
        f"📍 {location}\n"
        f"👥 {people}　🆔 `{e.get('id')}`"
    )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventsCog(bot))
