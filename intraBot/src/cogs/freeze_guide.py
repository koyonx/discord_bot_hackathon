from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("intraBot.cog.freeze_guide")


GUIDE_TEXT = """\
**Freeze (休止) とは?**
- 健康・インターン・個人事情等で **一時的に cursus を停止**する制度
- freeze 中は **BH カウントが止まる**
- 期間終了後に自動復帰

**申請手順 (一般的な 42 の流れ)**
1. <https://intra.42.fr> にログイン
2. 自分のプロフィールページから **`Freeze`** メニューを開く
3. **理由** (健康/インターン/個人事情 等) と **希望期間** を入力
4. 必要書類を添付 (例: 健康診断書 / インターン契約書)
5. 提出 → staff の承認待ち (通常 数営業日)

**Tokyo 独自のルール**
- 期間上限・必要書類・申請可能タイミング等は campus ごとに異なります
- 正確な手順 / 必要書類 は **#help-desk** で staff に直接確認してください

**よくある質問**
- 「いきなり freeze できる?」→ 場合による (緊急 freeze は staff と相談)
- 「freeze 中に校舎に来ていい?」→ 基本 NG。校舎で見つかると freeze 解除される事あり
- 「freeze 中に project 提出できる?」→ できない。提出するなら復帰してから
"""


class FreezeGuideCog(commands.Cog):
    """freeze 申請の手順案内 (静的コンテンツ)。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="freeze_guide",
        description="freeze (休止) 申請の手順を表示",
    )
    async def freeze_guide(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="❄️ Freeze 申請ガイド",
            description=GUIDE_TEXT,
            color=0x3498DB,
        )
        embed.set_footer(text="正確な手順は staff に確認してください")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FreezeGuideCog(bot))
