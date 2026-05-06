from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("intraBot.cog.find_evaluator")


class FindEvaluatorCog(commands.Cog):
    """`/find_evaluator <project>` — 校舎にいる合格者(Discord 連携済)に DM 一斉送信。

    候補が "評価する" を押したら募集者に DM 通知。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="find_evaluator",
        description="指定 project の評価者を募集 (合格者かつ在校中の Discord 連携済 cadet に DM)",
    )
    @app_commands.describe(project="評価してほしい project (slug または name)")
    async def find_evaluator(self, interaction: discord.Interaction, project: str) -> None:
        await interaction.response.defer(thinking=True)

        proj = await self._resolve_project(project)
        if not proj:
            await interaction.followup.send(
                f"❌ プロジェクト `{project}` は存在しません。`/finder` で project 名を確認してください。"
            )
            return

        proj_id = int(proj["id"])
        proj_name = proj.get("name", project)

        # 合格者 (Tokyo) ∩ 在校中 を取得
        try:
            validated, active_locs = await asyncio.gather(
                self.bot.client.get_project_validated_users(proj_id, self.bot.campus_id),
                self.bot.client.get_campus_active_locations(self.bot.campus_id),
            )
        except Exception as e:
            log.error("find_evaluator: data fetch failed: %s", e)
            await interaction.followup.send(f"❌ データ取得失敗: {e}")
            return

        active_user_ids = {int(loc["user"]["id"]): loc for loc in active_locs if "user" in loc}
        validated_user_ids = {int(p["user"]["id"]): p for p in validated}
        intersect = set(active_user_ids) & set(validated_user_ids)

        if not intersect:
            await interaction.followup.send(
                f"🌃 `{proj_name}` の合格者で在校中の人がいません。intra の Find a peer で募集してください。"
            )
            return

        # Discord 連携済の候補だけ抽出
        linked_candidates: list[tuple[str, str, str]] = []  # (discord_id, login, host)
        for uid in intersect:
            login = active_user_ids[uid]["user"]["login"]
            host = active_user_ids[uid].get("host", "?")
            entry = await self.bot.store.get_by_login(login)
            if entry:
                linked_candidates.append((entry.discord_id, login, host))

        if not linked_candidates:
            await interaction.followup.send(
                f"🌃 `{proj_name}` の合格者は在校中ですが、Discord 連携済の人が **0 人** です。"
                f"\nintra の Find a peer で直接募集してください。"
            )
            return

        # 各候補に DM 送信
        requester = interaction.user
        guild_name = interaction.guild.name if interaction.guild else "intraBot"
        sent: list[str] = []
        failed: list[str] = []
        for cand_did, cand_login, cand_host in linked_candidates:
            try:
                cand_user = await self.bot.fetch_user(int(cand_did))
                view = AcceptView(
                    self.bot,
                    requester_id=requester.id,
                    requester_name=getattr(requester, "display_name", str(requester)),
                    project=proj_name,
                    guild_name=guild_name,
                )
                msg = (
                    f"🆘 **{getattr(requester, 'display_name', requester.name)}** さん"
                    f" ({guild_name}) が `{proj_name}` の **評価者を募集**しています。\n"
                    f"あなたは合格者かつ在校中なので候補に入っています (座席: `{cand_host}`)。\n"
                    f"引き受けてくれる場合は下のボタンを押してください。募集者に DM が届きます。"
                )
                await cand_user.send(msg, view=view)
                sent.append(cand_login)
            except discord.Forbidden:
                log.info("find_evaluator: DM forbidden for %s", cand_login)
                failed.append(cand_login)
            except Exception:
                log.exception("find_evaluator: DM send failed for %s", cand_login)
                failed.append(cand_login)

        embed = discord.Embed(
            title=f"🆘 評価者募集: `{proj_name}`",
            description=(
                f"{requester.mention} が `{proj_name}` の評価者を探しています。\n"
                f"DM 送信成功: **{len(sent)}** 人 / 失敗: **{len(failed)}** 人\n"
                f"返答があり次第、{requester.mention} に DM 通知されます。"
            ),
            color=0xE74C3C,
        )
        if sent:
            embed.add_field(name="送信先", value=", ".join(f"`{n}`" for n in sent[:25]), inline=False)
        await interaction.followup.send(embed=embed)

    async def _resolve_project(self, query: str) -> dict | None:
        # FinderCog のキャッシュを再利用
        finder = self.bot.get_cog("FinderCog")
        if finder is not None:
            projects = getattr(finder, "_project_cache", []) or []
            nl = query.lower().strip()
            for p in projects:
                if (p.get("slug") or "").lower() == nl or (p.get("name") or "").lower() == nl:
                    return p
        return await self.bot.client.find_project(query)


class AcceptView(discord.ui.View):
    """各候補への DM に付ける Accept ボタン。1h でタイムアウト。"""

    def __init__(self, bot: commands.Bot, *, requester_id: int, requester_name: str, project: str, guild_name: str):
        super().__init__(timeout=3600)
        self.bot = bot
        self.requester_id = requester_id
        self.requester_name = requester_name
        self.project = project
        self.guild_name = guild_name
        self._claimed = False

    @discord.ui.button(label="評価する", style=discord.ButtonStyle.success, emoji="🙋")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self._claimed:
            await interaction.response.send_message("既に応答済です。", ephemeral=True)
            return
        self._claimed = True
        button.disabled = True
        button.label = "応答済"

        responder = interaction.user
        try:
            requester_user = await self.bot.fetch_user(self.requester_id)
            await requester_user.send(
                f"🙋 **{getattr(responder, 'display_name', responder.name)}** ({responder.mention}) "
                f"が `{self.project}` の評価を引き受けてくれました! ({self.guild_name})\n"
                f"DM で日程調整してください。"
            )
        except discord.Forbidden:
            log.warning(
                "find_evaluator accept: cannot DM requester %s (DM closed)", self.requester_id
            )
            await interaction.response.send_message(
                "応答 OK ですが、募集者の DM が閉じていて通知できませんでした。"
                "直接連絡してください。",
                ephemeral=True,
            )
            return
        except Exception:
            log.exception("find_evaluator accept: notify requester failed")
            await interaction.response.send_message(
                "応答 OK ですが、募集者への通知中にエラーが発生しました。",
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            content=f"✅ `{self.project}` の評価を引き受けました。募集者 ({self.requester_name}) に通知済。",
            view=self,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FindEvaluatorCog(bot))
