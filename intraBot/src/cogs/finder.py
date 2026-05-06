from __future__ import annotations

import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

log = logging.getLogger("intraBot.cog.finder")

PROJECT_CACHE_TTL = 3600  # 1h


class FinderCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._project_cache: list[dict] = []
        self._project_cache_at: float = 0.0
        self._refresh_lock = asyncio.Lock()

    async def cog_load(self) -> None:
        # 起動直後にバックグラウンドで cache を温めておく (autocomplete を 3s 制限内に収めるため)
        asyncio.create_task(self._refresh_cache())

    async def _refresh_cache(self) -> None:
        if self._refresh_lock.locked():
            return
        async with self._refresh_lock:
            try:
                projects = await self.bot.client.get_cursus_projects(21)
                self._project_cache = projects
                self._project_cache_at = time.time()
                log.info("project cache primed: %d projects", len(projects))
            except Exception:
                log.exception("project cache refresh failed")

    def _projects_sync(self) -> list[dict]:
        """autocomplete 用 — 絶対に API を待たない。期限切れなら background で更新だけ仕掛ける。"""
        if not self._project_cache or (time.time() - self._project_cache_at) > PROJECT_CACHE_TTL:
            if not self._refresh_lock.locked():
                asyncio.create_task(self._refresh_cache())
        return self._project_cache

    async def _projects(self) -> list[dict]:
        """通常コマンド用 — cache が空ならその場で 1 回だけ取りに行く。"""
        if not self._project_cache:
            await self._refresh_cache()
        return self._project_cache

    @staticmethod
    def _match(p: dict, q: str) -> bool:
        return q in (p.get("slug") or "").lower() or q in (p.get("name") or "").lower()

    @app_commands.command(
        name="finder",
        description="指定課題に合格 ∩ 現在校舎にいる人を検索",
    )
    @app_commands.describe(project="プロジェクト名 / slug (打ち始めると候補が出ます)")
    async def finder(self, interaction: discord.Interaction, project: str) -> None:
        await interaction.response.defer(thinking=True)

        # 1. cache (cursus 21 一覧) から完全一致を探す。autocomplete 経由ならここで殆どヒット
        projects = await self._projects()
        nl = project.lower().strip()
        proj: dict | None = next(
            (
                p for p in projects
                if (p.get("slug") or "").lower() == nl or (p.get("name") or "").lower() == nl
            ),
            None,
        )
        # 2. cache に無ければ API に直接問い合わせ (piscine project / cache 未温 等のケース)
        if not proj:
            proj = await self.bot.client.find_project(project)
        if not proj:
            # ===== ケース 1: そもそも project が存在しない =====
            projects = await self._projects()
            q = project.lower().strip()
            similar = [p for p in projects if self._match(p, q)]
            similar.sort(key=lambda p: (len(p.get("slug") or ""), p.get("slug") or ""))
            if similar:
                names = ", ".join(f"`{p['slug']}`" for p in similar[:30])
                msg = f"❌ プロジェクト `{project}` は存在しません。\n似た名前の候補: {names}"
            elif projects:
                sample = sorted(projects, key=lambda p: p.get("slug") or "")[:30]
                names = ", ".join(f"`{p['slug']}`" for p in sample)
                msg = (
                    f"❌ プロジェクト `{project}` は存在しません。\n"
                    f"42cursus の project 例: {names}\n"
                    f"(打ち始めると autocomplete で候補が出ます)"
                )
            else:
                msg = f"❌ プロジェクト `{project}` は存在しません。"
            await interaction.followup.send(msg)
            return

        proj_id = int(proj["id"])
        proj_name = proj.get("name", project)

        validated, active_locs = await asyncio.gather(
            self.bot.client.get_project_validated_users(proj_id, self.bot.campus_id),
            self.bot.client.get_campus_active_locations(self.bot.campus_id),
        )

        validated_user_ids = {int(p["user"]["id"]): p for p in validated}

        if not validated_user_ids:
            # ===== ケース 2: project は存在するが Tokyo の合格者がまだいない =====
            await interaction.followup.send(
                f"🤔 `{proj_name}` の合格者は Tokyo にまだいません。"
            )
            return

        active_user_ids = {int(loc["user"]["id"]): loc for loc in active_locs}
        intersect_ids = set(active_user_ids) & set(validated_user_ids)

        if not intersect_ids:
            # ===== ケース 3: 合格者はいるが、現在校舎にはいない =====
            await interaction.followup.send(
                f"🌃 `{proj_name}` 合格者は Tokyo に **{len(validated_user_ids)} 人**いますが、"
                f"今校舎に来ている人はいません。"
            )
            return

        rows: list[tuple[int, str, str, str]] = []  # (user_id, login, host, mark)
        for uid in intersect_ids:
            login = validated_user_ids[uid]["user"]["login"]
            host = active_user_ids[uid].get("host", "?")
            mark = validated_user_ids[uid].get("final_mark")
            rows.append((uid, login, host, str(mark) if mark is not None else "—"))
        rows.sort(key=lambda r: r[2])  # by host

        embed = discord.Embed(
            title=f"🔎 `{proj_name}` 合格 ∩ 在校中 ({len(rows)} 人)",
            color=0x00BABC,
        )
        lines = []
        for _, login, host, mark in rows[:25]:
            lines.append(f"• `{host}` — **{login}** (mark {mark})")
        embed.description = "\n".join(lines)
        if len(rows) > 25:
            embed.set_footer(text=f"... 他 {len(rows) - 25} 人")

        # 各人を呼び出すボタン (login のドロップダウン)
        view = ContactView([(login, host) for _, login, host, _ in rows[:25]], self.bot)
        await interaction.followup.send(embed=embed, view=view)

    @finder.autocomplete("project")
    async def _project_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[Choice[str]]:
        projects = self._projects_sync()  # ← 絶対に await しない
        if not projects:
            # cache 未温時は何も返さない (Discord 側は "候補なし" 表示)
            return []
        q = (current or "").lower().strip()
        if not q:
            # 空入力時は名前順で先頭 25 件
            sample = sorted(projects, key=lambda p: p.get("slug") or "")[:25]
            return [Choice(name=p.get("name", p["slug"]), value=p["slug"]) for p in sample]
        matches = [p for p in projects if self._match(p, q)]
        # 完全一致 → 前方一致 → 部分一致 の順で並べる
        matches.sort(key=lambda p: (
            0 if (p.get("slug") or "").lower() == q else
            1 if (p.get("slug") or "").lower().startswith(q) else 2,
            p.get("slug") or "",
        ))
        return [Choice(name=p.get("name", p["slug"]), value=p["slug"]) for p in matches[:25]]


class ContactView(discord.ui.View):
    def __init__(self, candidates: list[tuple[str, str]], bot: commands.Bot):
        super().__init__(timeout=300)
        self.add_item(ContactSelect(candidates, bot))


class ContactSelect(discord.ui.Select):
    def __init__(self, candidates: list[tuple[str, str]], bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(label=login, description=f"@ {host}", value=login)
            for login, host in candidates
        ]
        super().__init__(
            placeholder="呼び出す相手を選ぶ…",
            min_values=1,
            max_values=1,
            options=options[:25],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        login = self.values[0]
        target = await self.bot.store.get_by_login(login)
        if target is None:
            await interaction.response.send_message(
                f"`{login}` はまだ Discord 紐付けしていません。intra で `Find a peer` から直接呼び出してください。",
                ephemeral=True,
            )
            return

        try:
            user = await self.bot.fetch_user(int(target.discord_id))
            sender = interaction.user
            sender_name = sender.display_name if hasattr(sender, "display_name") else sender.name
            guild_name = interaction.guild.name if interaction.guild else "intraBot"
            await user.send(
                f"👋 **{sender_name}** さん ({guild_name}) があなたを呼んでいます。"
                f"\nDM で連絡を取ってみてください: <@{sender.id}>"
            )
        except discord.Forbidden:
            log.warning("finder: DM forbidden to login=%s (discord_id=%s)", login, target.discord_id)
            await interaction.response.send_message(
                f"`{login}` の DM が閉じていて送れませんでした。",
                ephemeral=True,
            )
            return
        except Exception as e:
            log.exception("finder: DM send failed to login=%s", login)
            await interaction.response.send_message(f"❌ DM 送信失敗: {e}", ephemeral=True)
            return

        await interaction.response.send_message(f"📨 `{login}` に呼び出し DM を送りました。", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FinderCog(bot))
