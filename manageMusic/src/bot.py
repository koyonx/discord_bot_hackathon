import os
import logging
from typing import List

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

if not DISCORD_TOKEN:
    raise SystemExit("DISCORD_TOKEN 環境変数を設定してください。")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("manageMusic")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)
queue: List[str] = []

@bot.event
async def on_ready():
    logger.info("Logged in as %s", bot.user)
    await bot.change_presence(activity=discord.Game(name="Manage music queue"))

@bot.command(name="add")
async def add_track(ctx: commands.Context, *, title: str):
    title = title.strip()
    if not title:
        await ctx.send("❌ 曲名を指定してください。例: `!add Shape of You`")
        return

    queue.append(title)
    await ctx.send(f"✅ `{title}` をキューに追加しました。現在のキュー数: {len(queue)}")

@bot.command(name="queue")
async def show_queue(ctx: commands.Context):
    if not queue:
        await ctx.send("🎵 キューに曲がありません。`!add <曲名>` で追加できます。")
        return

    lines = [f"{idx + 1}. {item}" for idx, item in enumerate(queue[:10])]
    more = ""
    if len(queue) > 10:
        more = f"\n...and {len(queue) - 10} more"

    await ctx.send("🎧 現在のキュー:\n" + "\n".join(lines) + more)

@bot.command(name="remove")
async def remove_track(ctx: commands.Context, index: int):
    if index < 1 or index > len(queue):
        await ctx.send("❌ 無効な番号です。`!queue` で番号を確認してください。")
        return

    removed = queue.pop(index - 1)
    await ctx.send(f"🗑 `{removed}` をキューから削除しました。")

@bot.command(name="clear")
async def clear_queue(ctx: commands.Context):
    queue.clear()
    await ctx.send("✅ キューをクリアしました。")

@bot.command(name="help")
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title="manageMusic コマンド一覧",
        description="音楽キューを管理するシンプルなボットです。",
        color=0x1DB954,
    )
    embed.add_field(name=f"{COMMAND_PREFIX}add <曲名>", value="キューに曲を追加します。", inline=False)
    embed.add_field(name=f"{COMMAND_PREFIX}queue", value="現在のキューを表示します。", inline=False)
    embed.add_field(name=f"{COMMAND_PREFIX}remove <番号>", value="指定した番号の曲を削除します。", inline=False)
    embed.add_field(name=f"{COMMAND_PREFIX}clear", value="キューを空にします。", inline=False)
    await ctx.send(embed=embed)

bot.run(DISCORD_TOKEN)
