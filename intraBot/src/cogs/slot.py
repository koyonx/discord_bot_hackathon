from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs._helpers import NotLinkedError, get_valid_user_token
from intra.client import IntraError

log = logging.getLogger("intraBot.cog.slot")


class SlotCog(commands.GroupCog, name="slot"):
    """`/slot add|list|del` — Find a peer の slot を本人トークンで操作"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="add", description="自分の slot を追加 (15分単位)")
    @app_commands.describe(
        start="開始 (例: 2026-05-10T14:00 / JST 想定)",
        duration_min="長さ (分。15 の倍数。例: 60)",
    )
    async def add(self, interaction: discord.Interaction, start: str, duration_min: int) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            user, token = await get_valid_user_token(self.bot.store, self.bot.client, str(interaction.user.id))
        except NotLinkedError:
            await interaction.followup.send("先に `/link` で 42 アカウントを紐付けてください。", ephemeral=True)
            return

        try:
            begin = _parse_local(start)
        except ValueError as e:
            log.warning("slot add: invalid start format %r: %s", start, e)
            await interaction.followup.send(f"❌ start のフォーマットが不正: {e}", ephemeral=True)
            return
        if duration_min <= 0 or duration_min % 15 != 0:
            await interaction.followup.send("❌ duration_min は 15 の倍数で指定してください。", ephemeral=True)
            return
        end = begin + timedelta(minutes=duration_min)

        try:
            slot = await self.bot.client.create_slot(
                token, user.intra_user_id, _to_iso(begin), _to_iso(end)
            )
        except IntraError as e:
            log.error("slot add: create_slot failed (%s〜%s): %s", _to_iso(begin), _to_iso(end), e)
            await interaction.followup.send(f"❌ slot 作成失敗: {e}", ephemeral=True)
            return

        sid = slot.get("id") if isinstance(slot, dict) else None
        await interaction.followup.send(
            f"✅ slot 追加完了 ({_jst(begin):%Y-%m-%d %H:%M} 〜 {_jst(end):%H:%M}) id=`{sid}`",
            ephemeral=True,
        )

    @app_commands.command(name="list", description="自分の slot 一覧 + キャンセルボタン")
    async def list_slots(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            _, token = await get_valid_user_token(self.bot.store, self.bot.client, str(interaction.user.id))
        except NotLinkedError:
            await interaction.followup.send("先に `/link` で 42 アカウントを紐付けてください。", ephemeral=True)
            return

        try:
            slots = await self.bot.client.list_user_slots(token)
        except IntraError as e:
            log.error("slot list: list_user_slots failed: %s", e)
            await interaction.followup.send(f"❌ 取得失敗: {e}", ephemeral=True)
            return
        if not slots:
            await interaction.followup.send("登録済みの slot はありません。", ephemeral=True)
            return

        embed, options, group_map = _build_list_embed(slots)
        view: discord.ui.View | None
        if options:
            view = SlotCancelView(self.bot, options, group_map)
        else:
            view = None
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="del", description="自分の slot を削除")
    @app_commands.describe(slot_id="削除する slot の ID (`/slot list` で確認)")
    async def delete(self, interaction: discord.Interaction, slot_id: int) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            _, token = await get_valid_user_token(self.bot.store, self.bot.client, str(interaction.user.id))
        except NotLinkedError:
            await interaction.followup.send("先に `/link` で 42 アカウントを紐付けてください。", ephemeral=True)
            return
        try:
            await self.bot.client.delete_slot(token, slot_id)
        except IntraError as e:
            log.error("slot del: delete_slot(id=%s) failed: %s", slot_id, e)
            await interaction.followup.send(f"❌ slot 削除失敗: {e}", ephemeral=True)
            return
        await interaction.followup.send(f"🗑 slot `{slot_id}` を削除しました。", ephemeral=True)


def _group_consecutive_slots(slots: list[dict]) -> list[list[dict]]:
    """begin_at 昇順にソートし、`前 slot.end_at == 次 slot.begin_at` の連続を 1 ブロックにまとめる。"""
    parsed: list[tuple[datetime, datetime, dict]] = []
    for s in slots:
        try:
            b = datetime.fromisoformat(s["begin_at"].replace("Z", "+00:00"))
            e = datetime.fromisoformat(s["end_at"].replace("Z", "+00:00"))
            parsed.append((b, e, s))
        except Exception:
            log.warning("slot list: parse failed for slot=%r", s)
            continue
    parsed.sort(key=lambda x: x[0])

    groups: list[list[dict]] = []
    current: list[dict] = []
    last_end: datetime | None = None
    for b, e, s in parsed:
        if current and last_end is not None and b == last_end:
            current.append(s)
        else:
            if current:
                groups.append(current)
            current = [s]
        last_end = e
    if current:
        groups.append(current)
    return groups


def _build_list_embed(slots: list[dict]) -> tuple[discord.Embed, list[discord.SelectOption], dict[str, list[int]]]:
    """slot 一覧 embed + cancel Select 用 options + group_key→slot_ids のマップ を作る。

    Select の value は 100 字制限があるので id 列をそのまま入れず group key (g0, g1, ...) を使う。
    """
    groups = _group_consecutive_slots(slots)
    embed = discord.Embed(
        title=f"📅 自分の slot ({len(slots)} 件 / {len(groups)} ブロック)",
        color=0x00BABC,
    )
    options: list[discord.SelectOption] = []
    group_map: dict[str, list[int]] = {}

    for i, grp in enumerate(groups[:25]):
        first = grp[0]
        last = grp[-1]
        try:
            b = datetime.fromisoformat(first["begin_at"].replace("Z", "+00:00"))
            e = datetime.fromisoformat(last["end_at"].replace("Z", "+00:00"))
            label = f"{_jst(b):%m/%d (%a) %H:%M}〜{_jst(e):%H:%M}"
        except Exception:
            label = f"{first.get('begin_at')} 〜 {last.get('end_at')}"

        ids = [int(s["id"]) for s in grp if s.get("id") is not None]
        if not ids:
            continue
        if len(ids) == 1:
            id_display = f"`{ids[0]}`"
        else:
            id_display = f"`{ids[0]}` 〜 `{ids[-1]}` ({len(ids)} 個)"

        embed.add_field(name=id_display, value=label, inline=False)
        key = f"g{i}"
        group_map[key] = ids
        options.append(discord.SelectOption(label=label[:100], value=key))

    if len(groups) > 25:
        embed.set_footer(text=f"... 他 {len(groups) - 25} ブロック (Select には載っていません)")
    return embed, options, group_map


class SlotCancelView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        options: list[discord.SelectOption],
        group_map: dict[str, list[int]],
    ):
        super().__init__(timeout=300)
        self.add_item(SlotCancelSelect(bot, options, group_map))


class SlotCancelSelect(discord.ui.Select):
    def __init__(
        self,
        bot: commands.Bot,
        options: list[discord.SelectOption],
        group_map: dict[str, list[int]],
    ):
        self.bot = bot
        self.group_map = group_map
        super().__init__(
            placeholder="キャンセルするブロックを選ぶ…",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        key = self.values[0]
        slot_ids = self.group_map.get(key) or []
        if not slot_ids:
            await interaction.response.send_message("❌ 対象 slot が見つかりません", ephemeral=True)
            return
        try:
            _, token = await get_valid_user_token(
                self.bot.store, self.bot.client, str(interaction.user.id)
            )
        except NotLinkedError:
            await interaction.response.send_message(
                "先に `/link` で 42 アカウントを紐付けてください。", ephemeral=True
            )
            return

        deleted: list[int] = []
        failed: list[tuple[int, IntraError]] = []
        for sid in slot_ids:
            try:
                await self.bot.client.delete_slot(token, sid)
                deleted.append(sid)
            except IntraError as e:
                log.error("slot list-cancel: delete_slot(id=%s) failed: %s", sid, e)
                failed.append((sid, e))

        if not deleted:
            err = failed[0][1] if failed else "unknown"
            await interaction.response.send_message(
                f"❌ 全件削除失敗: {err}", ephemeral=True
            )
            return
        msg = f"🗑 slot を {len(deleted)} 個キャンセルしました。"
        if failed:
            msg += f"\n⚠️ うち {len(failed)} 個は削除に失敗 (id: {', '.join(str(i) for i, _ in failed)})"
        await interaction.response.send_message(msg, ephemeral=True)


JST = timezone(timedelta(hours=9))


def _parse_local(s: str) -> datetime:
    """Accept '2026-05-10T14:00' / '2026-05-10 14:00' / '...:00' as JST-naive, return UTC datetime."""
    t = s.strip().replace(" ", "T")
    if len(t) == 16:
        t += ":00"
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(timezone.utc)


def _to_iso(dt_utc: datetime) -> str:
    return dt_utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _jst(dt: datetime) -> datetime:
    return dt.astimezone(JST)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SlotCog(bot))
