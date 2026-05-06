from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from cogs._helpers import NotLinkedError, get_valid_user_token
from intra.client import IntraError

log = logging.getLogger("intraBot.cog.reviews")
JST = timezone(timedelta(hours=9))


class ReviewsCog(commands.GroupCog, name="reviews", description="自分のレビュー予約 (book/list/cancel)"):
    """`/reviews book|list|cancel` — scale_teams を本人 OAuth で操作。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    # ===== /reviews book =====

    @app_commands.command(
        name="book",
        description="進行中の project に対する空き slot を一覧してレビュー予約",
    )
    @app_commands.describe(project="レビューしてもらいたい project の slug / name")
    async def book(self, interaction: discord.Interaction, project: str) -> None:
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

        # 自分の projects_user (team_id を取るため)
        try:
            pu = await self.bot.client.find_user_project(
                user.intra_user_id, proj_id, user_token=token
            )
        except IntraError as e:
            log.error("reviews book: find_user_project failed: %s", e)
            await interaction.followup.send(f"❌ 検索失敗: {e}", ephemeral=True)
            return
        if not pu:
            await interaction.followup.send(
                f"❌ `{proj_name}` には登録されていません。先に project を `set` してください。",
                ephemeral=True,
            )
            return
        team_id = pu.get("current_team_id")
        if not team_id:
            await interaction.followup.send(
                f"❌ `{proj_name}` の team_id が取れません (まだ submit していない可能性)。",
                ephemeral=True,
            )
            return

        # scale_id (project の rubric) を解決。多段 fallback で粘る
        scale_id: int | None = None
        if proj.get("scales"):
            try:
                scale_id = int(proj["scales"][0]["id"])
            except Exception:
                scale_id = None
        if scale_id is None:
            scale_id = await self.bot.client.resolve_project_scale_id(proj_id)
        if scale_id is None:
            log.error("reviews book: scale_id resolve failed for project=%s", proj_name)
            await interaction.followup.send(
                f"❌ `{proj_name}` の scale が解決できませんでした。intra 側の Find a peer を使ってください。",
                ephemeral=True,
            )
            return

        # 空き slot 取得 → フィルタ (未来 / 未予約 / 自分以外)
        try:
            slots = await self.bot.client.get_project_slots(proj_id)
        except IntraError as e:
            log.error("reviews book: get_project_slots failed: %s", e)
            await interaction.followup.send(f"❌ slot 取得失敗: {e}", ephemeral=True)
            return

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        available: list[dict] = []
        for s in slots:
            if s.get("scale_team"):
                continue  # 既に誰かが予約済
            slot_user = s.get("user") or {}
            if (slot_user.get("login") or "").lower() == user.intra_login.lower():
                continue  # 自分の slot は除外
            if (s.get("end_at") or "") < now_iso:
                continue
            available.append(s)

        if not available:
            await interaction.followup.send(
                f"🌃 `{proj_name}` に予約可能な slot がありません。"
                f"\n後ほど `/online` で在校中の合格者を探したり、intra で募集したりしてください。",
                ephemeral=True,
            )
            return

        available.sort(key=lambda s: s.get("begin_at") or "")

        embed = discord.Embed(
            title=f"📅 `{proj_name}` の空き slot ({len(available)} 件)",
            description="下のメニューから 1 つ選ぶと予約します",
            color=0x00BABC,
        )
        view = SlotPickerView(
            self.bot,
            discord_id=str(interaction.user.id),
            team_id=int(team_id),
            scale_id=scale_id,
            project_name=proj_name,
            slots=available[:25],
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @book.autocomplete("project")
    async def _book_ac(
        self, interaction: discord.Interaction, current: str
    ) -> list[Choice[str]]:
        return _project_autocomplete(self.bot, current)

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

    # ===== helpers =====

    async def _resolve_project(self, query: str) -> dict | None:
        finder = self.bot.get_cog("FinderCog")
        if finder is not None:
            projects = list(getattr(finder, "_project_cache", []) or [])
            nl = query.lower().strip()
            for p in projects:
                if (p.get("slug") or "").lower() == nl or (p.get("name") or "").lower() == nl:
                    return p
        return await self.bot.client.find_project(query)


def _project_autocomplete(bot: commands.Bot, current: str) -> list[Choice[str]]:
    finder = bot.get_cog("FinderCog")
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


class SlotPickerView(discord.ui.View):
    """空き slot から 1 つ選んで scale_team を作成する Select。"""

    def __init__(
        self,
        bot: commands.Bot,
        *,
        discord_id: str,
        team_id: int,
        scale_id: int,
        project_name: str,
        slots: list[dict],
    ):
        super().__init__(timeout=300)
        self.add_item(
            SlotPickerSelect(
                bot,
                discord_id=discord_id,
                team_id=team_id,
                scale_id=scale_id,
                project_name=project_name,
                slots=slots,
            )
        )


class SlotPickerSelect(discord.ui.Select):
    def __init__(
        self,
        bot: commands.Bot,
        *,
        discord_id: str,
        team_id: int,
        scale_id: int,
        project_name: str,
        slots: list[dict],
    ):
        self.bot = bot
        self.discord_id = discord_id
        self.team_id = team_id
        self.scale_id = scale_id
        self.project_name = project_name
        self.slots_by_id: dict[str, dict] = {}
        options: list[discord.SelectOption] = []
        for s in slots[:25]:
            sid = str(s.get("id"))
            self.slots_by_id[sid] = s
            evaluator = (s.get("user") or {}).get("login", "?")
            try:
                begin = datetime.fromisoformat(
                    (s.get("begin_at") or "").replace("Z", "+00:00")
                )
                jst_b = begin.astimezone(JST)
                label = f"{jst_b:%m/%d %H:%M} — {evaluator}"
            except Exception:
                label = f"{evaluator} ({s.get('begin_at')})"
            options.append(discord.SelectOption(label=label[:100], value=sid))
        super().__init__(
            placeholder="予約する slot を選ぶ…",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        sid = self.values[0]
        slot = self.slots_by_id.get(sid)
        if not slot:
            await interaction.response.send_message("❌ slot が見つかりません", ephemeral=True)
            return
        begin_at = slot.get("begin_at")
        if not begin_at:
            await interaction.response.send_message("❌ slot.begin_at 不正", ephemeral=True)
            return
        try:
            _, token = await get_valid_user_token(
                self.bot.store, self.bot.client, self.discord_id
            )
        except NotLinkedError:
            await interaction.response.send_message("未紐付け", ephemeral=True)
            return
        try:
            await self.bot.client.book_scale_team(
                token,
                team_id=self.team_id,
                scale_id=self.scale_id,
                begin_at=begin_at,
            )
        except IntraError as e:
            log.error("reviews book: scale_team create failed: %s", e)
            await interaction.response.send_message(
                f"❌ 予約失敗: {e}\n(他の人が同時に取った可能性があります。再度 `/reviews book` を試してください)",
                ephemeral=True,
            )
            return
        evaluator = (slot.get("user") or {}).get("login", "?")
        try:
            jst_b = datetime.fromisoformat(begin_at.replace("Z", "+00:00")).astimezone(JST)
            time_str = f"{jst_b:%Y-%m-%d (%a) %H:%M}"
        except Exception:
            time_str = begin_at
        await interaction.response.edit_message(
            content=(
                f"✅ `{self.project_name}` のレビュー予約完了\n"
                f"👤 評価者: `{evaluator}`\n"
                f"⏰ {time_str}"
            ),
            view=None,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReviewsCog(bot))
