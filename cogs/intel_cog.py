import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load_json_data
from utils.i18n import get_lang, t
from utils.ui import styled_embed, loading_embed, ROYAL_BLUE
# from cogs.ai_cog import ask_ai (lazy loaded to prevent circular import)


# ---------------------------------------------------------------------------
# /scout - تحليل صورة الخصم بالذكاء الاصطناعي (قوي / ضعيف)
# ---------------------------------------------------------------------------

def _scout_prompt(lang: str) -> str:
    if lang == "ar":
        return (
            "حلل الصورة دي (عتاد أو بروفايل خصم في لعبة Lords Mobile) وحدد هل اللاعب ده قوي "
            "ولا ضعيف، بناءً على نوع العتاد الظاهر (اقتصادي = ضعيف دفاعياً، حربي = قوي)، "
            "الجواهر، أو أي مؤشر قوة زي الـ Might لو ظاهر في الصورة. "
            "ابدأ ردك بكلمة حكم واضحة في أول سطر: \"💪 قوي\" أو \"🪶 ضعيف\" أو \"⚖️ متوسط\"، "
            "وبعدها اشرح سبب حكمك في سطرين مختصرين بس."
        )
    return (
        "Analyze this image (a Lords Mobile opponent's gear or profile) and determine whether "
        "this player looks strong or weak, based on the visible gear type (economy gear = weak "
        "defense, war gear = strong), jewels, or any power indicator like visible Might. "
        "Start your reply with a clear verdict on the first line: \"💪 Strong\", \"🪶 Weak\", or "
        "\"⚖️ Average\", then explain your reasoning in two short sentences only."
    )


# ---------------------------------------------------------------------------
# /geartiers
# ---------------------------------------------------------------------------

class GearTierView(discord.ui.View):
    def __init__(self, gear_tiers: dict, lang: str):
        super().__init__(timeout=60)
        self.gear_tiers = gear_tiers
        self.lang = lang
        self.war.label = t("gear_type_war", lang)
        self.hunting.label = t("gear_type_hunting", lang)
        self.economy.label = t("gear_type_economy", lang)

    @discord.ui.button(label="⚔️ عتاد الحرب", style=discord.ButtonStyle.danger)
    async def war(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self.lang
        info = self.gear_tiers["war"]
        embed = discord.Embed(title=t("geartiers_war_title", lang, emoji=info["emoji"]), color=discord.Color.red())
        embed.add_field(name="💎 P2P", value=info["p2p"], inline=False)
        embed.add_field(name="🆓 F2P", value=info["f2p"], inline=False)
        embed.add_field(name=t("gear_weak_field", lang), value=info["weak"], inline=False)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="🏹 عتاد الصيد", style=discord.ButtonStyle.success)
    async def hunting(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self.lang
        info = self.gear_tiers["hunting"]
        embed = discord.Embed(
            title=t("geartiers_hunting_title", lang, emoji=info["emoji"]), color=discord.Color.green()
        )
        embed.add_field(name="💎 P2P", value=info["p2p"], inline=False)
        embed.add_field(name="🆓 F2P", value=info["f2p"], inline=False)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="🏗️ عتاد الاقتصاد", style=discord.ButtonStyle.secondary)
    async def economy(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self.lang
        info = self.gear_tiers["economy"]
        embed = discord.Embed(
            title=t("geartiers_economy_title", lang, emoji=info["emoji"]), color=discord.Color.orange()
        )
        embed.add_field(name=t("gear_pieces_field", lang), value=info["pieces"], inline=False)
        embed.add_field(name=t("gear_warning_field", lang), value=info["warning"], inline=False)
        await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# الـ Cog
# ---------------------------------------------------------------------------

class IntelCog(commands.Cog):
    """استخبارات: كشف قوة الخصم بالذكاء الاصطناعي، خلاصة الأبطال، وتصنيف العتاد."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gear_tiers = load_json_data("gear_tiers.json")

    @app_commands.command(
        name="scout",
        description="🔍 ارفق صورة عتاد/بروفايل الخصم والـ AI يحللها ويقولك هو قوي ولا ضعيف"
    )
    @app_commands.describe(image="Enemy gear or profile image for AI analysis")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def scout(self, interaction: discord.Interaction, image: discord.Attachment):
        lang = get_lang(interaction.guild_id, interaction.user.id)

        if not (image.content_type or "").lower().startswith("image/"):
            await interaction.response.send_message(t("ai_bad_image", lang), ephemeral=False)
            return

        await interaction.response.defer(thinking=True)
        loading_text = (
            "جارٍ تحليل قوة الخصم من الصورة... ⏳" if lang == "ar" else "Analyzing opponent strength from the image... ⏳"
        )
        loading_msg = await interaction.followup.send(embed=loading_embed(loading_text, lang))

        answer = await ask_ai(_scout_prompt(lang), image_url=image.url, lang=lang, guild_id=interaction.guild_id)

        embed = styled_embed(title=t("scout_result_title", lang), description=answer[:3500], color=ROYAL_BLUE, lang=lang)
        embed.set_thumbnail(url=image.url)
        embed.set_footer(text=t("scout_footer", lang))
        try:
            await loading_msg.edit(embed=embed)
        except discord.HTTPException:
            await interaction.followup.send(embed=embed)

    @scout.error
    async def scout_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(t("ai_cooldown", lang, s=f"{error.retry_after:.0f}"), ephemeral=False)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=False)

    @app_commands.command(name="geartiers", description="🧰 تصنيف العتاد الكامل (حرب / صيد / اقتصاد)")
    async def geartiers(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(
            t("geartiers_prompt", lang), view=GearTierView(self.gear_tiers, lang)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(IntelCog(bot))
