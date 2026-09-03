"""
/play - لعبة التحدي والمعرفة.
البوت بيختار عنصر عشوائي (عتاد / بطل / وحش / مرافق) وبيوريك تلميح بدل صورة حقيقية
(تجنباً لاستخدام صور اللعبة الأصلية المحمية بحقوق نشر)، واللاعب بيحاول يخمّن الاسم
خلال 30 ثانية عن طريق زرار بيفتح نافذة إدخال (Modal) - لأن البوت شغّال بـ Slash
Commands بس ومش بيقرأ رسائل الشات (message_content intent متقفول).
بيحترم تفضيل اللغة المضبوط بـ /language.
"""
import os
import random

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.storage import load, save, load_json_data
from utils.i18n import get_lang, t
from .guild_cog import get_rank

load_dotenv()
GAME_CHANNEL_ID = os.getenv("GAME_CHANNEL_ID")

PLAY_FILE = "play_scores"
ROUND_SECONDS = 30


class GuessModal(discord.ui.Modal):
    def __init__(self, parent_view: "PlayView"):
        super().__init__(title=t("play_modal_title", parent_view.lang))
        self.parent_view = parent_view
        self.guess = discord.ui.TextInput(
            label=t("play_modal_label", parent_view.lang), placeholder="Rose Knight", max_length=50
        )
        self.add_item(self.guess)

    async def on_submit(self, interaction: discord.Interaction):
        await self.parent_view.handle_guess(interaction, self.guess.value)


class PlayView(discord.ui.View):
    def __init__(self, item: dict, cog: "GamesCog", lang: str):
        super().__init__(timeout=ROUND_SECONDS)
        self.item = item
        self.cog = cog
        self.lang = lang
        self.solved = False
        self.message: discord.Message | None = None
        self.guess_button.label = t("play_guess_button", lang)

    @discord.ui.button(style=discord.ButtonStyle.blurple)
    async def guess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.solved:
            await interaction.response.send_message(t("play_already_solved", self.lang), ephemeral=True)
            return
        await interaction.response.send_modal(GuessModal(self))

    async def handle_guess(self, interaction: discord.Interaction, guess_text: str):
        if self.solved:
            await interaction.response.send_message(t("play_already_solved", self.lang), ephemeral=True)
            return

        correct = guess_text.strip().lower() == self.item["name"].lower()
        if not correct:
            await interaction.response.send_message(t("play_wrong", self.lang), ephemeral=True)
            return

        self.solved = True
        self.stop()

        data = load(PLAY_FILE)
        gid = str(interaction.guild_id)
        uid = str(interaction.user.id)
        data.setdefault(gid, {})
        data[gid].setdefault(uid, {"name": str(interaction.user), "points": 0})
        data[gid][uid]["points"] += 1
        save(PLAY_FILE, data)
        points = data[gid][uid]["points"]

        for child in self.children:
            child.disabled = True

        answer = f"**{self.item['emoji']} {self.item['name']}** ({self.item['category']})"
        result_embed = discord.Embed(
            title=t("play_win_title", self.lang, user=interaction.user.display_name),
            description=f"{t('play_answer_was', self.lang)}: {answer}",
            color=discord.Color.green(),
        )
        result_embed.set_footer(text=t("play_score_footer", self.lang, points=points, rank=get_rank(points)))

        await interaction.response.send_message(t("play_correct_msg", self.lang), ephemeral=True)
        if self.message:
            try:
                await self.message.edit(embed=result_embed, view=self)
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        if self.solved:
            return
        for child in self.children:
            child.disabled = True
        answer = f"**{self.item['emoji']} {self.item['name']}** ({self.item['category']})"
        reveal_embed = discord.Embed(
            title=t("play_timeout_title", self.lang),
            description=t("play_timeout_desc", self.lang, answer=answer),
            color=discord.Color.red(),
        )
        if self.message:
            try:
                await self.message.edit(embed=reveal_embed, view=self)
            except discord.HTTPException:
                pass


class GamesCog(commands.Cog):
    """لعبة التحدي والمعرفة (/play)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.play_items = load_json_data("play_items.json")

    @app_commands.command(name="play", description="🎮 خمّن اسم العنصر (عتاد/بطل/وحش/مرافق) خلال 30 ثانية! | Guess the item's name in 30s")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def play(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)

        if GAME_CHANNEL_ID and str(interaction.channel_id) != str(GAME_CHANNEL_ID):
            await interaction.response.send_message(
                t("play_wrong_channel", lang, channel=GAME_CHANNEL_ID), ephemeral=True
            )
            return

        item = random.choice(self.play_items)
        embed = discord.Embed(
            title=t("play_title", lang),
            description=f"# {item['emoji']}\n{t('play_category', lang)}: **{item['category']}**\n{t('play_hint', lang)}: {item['hint']}",
            color=discord.Color.orange(),
        )
        embed.set_footer(text=t("play_footer", lang))

        view = PlayView(item, self, lang)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @play.error
    async def play_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id)
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                t("play_cooldown", lang, s=f"{error.retry_after:.0f}"), ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ حصل خطأ غير متوقع. / Unexpected error.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))
