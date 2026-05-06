from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

log = logging.getLogger("intraBot.cog.follow")


class FollowCog(
    commands.GroupCog,
    name="follow",
    description="cadet をフォロー、校舎入室時に DM 通知",
):
    """`/follow add|remove|list` + 在校入室検知 BG task。

    フォロー対象が新たに active location に現れたら、フォロワーに DM 通知。
    "新たに" の判定は前回 poll の active user_id 集合との差分。
    """

    def __init__(self, bot: commands.Bot, poll_seconds: int = 60):
        self.bot = bot
        self._last_active: set[int] = set()
        self._first_poll = True
        self.poll.change_interval(seconds=poll_seconds)
        self.poll.start()
        super().__init__()

    def cog_unload(self) -> None:
        self.poll.cancel()

    # ===== commands =====

    @app_commands.command(name="add", description="42 cadet をフォロー (校舎入室で DM 通知)")
    @app_commands.describe(login="フォローする 42 login")
    async def add(self, interaction: discord.Interaction, login: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            user = await self.bot.client.get_user(login)
        except Exception as e:
            log.warning("follow add: get_user(%s) failed: %s", login, e)
            await interaction.followup.send(f"❌ `{login}` は存在しません: {e}", ephemeral=True)
            return
        await self.bot.store.add_follow(
            str(interaction.user.id), user["login"], int(user["id"])
        )
        await interaction.followup.send(
            f"👁 `{user['login']}` をフォローしました。校舎に入室したら DM で通知します。",
            ephemeral=True,
        )

    @app_commands.command(name="remove", description="フォロー解除")
    @app_commands.describe(login="フォロー解除する 42 login")
    async def remove(self, interaction: discord.Interaction, login: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        removed = await self.bot.store.remove_follow(str(interaction.user.id), login)
        if removed:
            await interaction.followup.send(
                f"🚫 `{login}` のフォローを解除しました。", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"`{login}` はフォローしていません。", ephemeral=True
            )

    @app_commands.command(name="list", description="フォロー中の cadet 一覧")
    async def list_follows(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        follows = await self.bot.store.list_follows(str(interaction.user.id))
        if not follows:
            await interaction.followup.send(
                "フォロー中の cadet はいません。`/follow add <login>` で追加できます。",
                ephemeral=True,
            )
            return
        lines = [f"• `{login}`" for login, _ in follows]
        embed = discord.Embed(
            title=f"👁 フォロー中 ({len(follows)} 人)",
            description="\n".join(lines),
            color=0x9B59B6,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ===== background task =====

    @tasks.loop(seconds=60)
    async def poll(self) -> None:
        try:
            locs = await self.bot.client.get_campus_active_locations(self.bot.campus_id)
        except Exception as e:
            log.warning("follow poll: active locations fetch failed: %s", e)
            return

        loc_by_uid: dict[int, dict] = {}
        current: set[int] = set()
        for loc in locs:
            user = loc.get("user") or {}
            uid = user.get("id")
            if uid is None:
                continue
            uid = int(uid)
            current.add(uid)
            loc_by_uid[uid] = loc

        if self._first_poll:
            # 起動直後の人を「新規入室」扱いしないため、初回は黙って set だけ更新
            self._last_active = current
            self._first_poll = False
            return

        newly_active = current - self._last_active
        self._last_active = current
        if not newly_active:
            return

        for uid in newly_active:
            followers = await self.bot.store.get_followers_of(uid)
            if not followers:
                continue
            loc = loc_by_uid.get(uid) or {}
            login = (loc.get("user") or {}).get("login", "?")
            host = loc.get("host", "?")
            for follower_id in followers:
                await self._dm(follower_id, login, host)

    @poll.before_loop
    async def _wait_ready(self) -> None:
        await self.bot.wait_until_ready()

    async def _dm(self, follower_discord_id: str, login: str, host: str) -> None:
        try:
            user = await self.bot.fetch_user(int(follower_discord_id))
        except Exception as e:
            log.warning("follow notify: fetch_user(%s) failed: %s", follower_discord_id, e)
            return
        try:
            await user.send(f"👁 `{login}` が校舎にログインしました (座席: `{host}`)")
        except discord.Forbidden:
            log.info("follow notify: DM blocked for %s", follower_discord_id)
        except Exception:
            log.exception("follow notify: DM send failed for %s", follower_discord_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FollowCog(bot, getattr(bot, "notify_poll_seconds", 60)))
