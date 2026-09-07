import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load_json_data
from utils.i18n import get_lang, t

# كلمات مفتاحية للكشف عن عتاد الاقتصاد (Noceros / Gryphon / Lunar Flute) بالعربي والإنجليزي
ECONOMY_KEYWORDS = [
    "noceros", "نوسيروس",
    "gryphon", "جريفون", "جريفين",
    "lunar flute", "لونار فلوت", "مزمار",
]

# كلمات مفتاحية لأنواع القوات عشان نكشف تضارب (خوذة رماة + جواهر مشاة مثلاً)
# (دي مفاتيح داخلية للكشف بس، مش نص ظاهر للمستخدم، فمش محتاجة ترجمة)
TROOP_KEYWORDS = {
    "infantry": ["مشاة", "infantry"],
    "ranged": ["رماة", "ranged"],
    "cavalry": ["فرسان", "cavalry"],
}


def analyze_enemy_gear(text: str, lang: str) -> list[str]:
    """يحلل نص وصف عتاد الخصم ويرجع قائمة بالتنبيهات المكتشفة (مترجمة حسب lang)."""
    lowered = text.lower()
    alerts = []

    if any(k in lowered for k in ECONOMY_KEYWORDS):
        alerts.append(t("scout_alert_economy", lang))

    found_troops = {key for key, kws in TROOP_KEYWORDS.items() if any(k in lowered for k in kws)}
    if len(found_troops) >= 2:
        alerts.append(t("scout_alert_mixed", lang))

    if not alerts:
        alerts.append(t("scout_alert_normal", lang))

    return alerts


# ---------------------------------------------------------------------------
# /scout - كاشف الخصم الضعيف
# ---------------------------------------------------------------------------

class ScoutModal(discord.ui.Modal):
    gear_seen = discord.ui.TextInput(
        label="👀 العتاد اللي شايفه على الخصم",
        style=discord.TextStyle.paragraph,
        placeholder="مثال: خوذة نوسيروس، درع رماة فيه جواهر مشاة...",
    )

    def __init__(self, lang: str):
        super().__init__(title=t("scout_modal_title", lang))
        self.lang = lang
        self.gear_seen.label = t("scout_modal_label", lang)[:45]
        self.gear_seen.placeholder = t("scout_modal_placeholder", lang)

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.lang
        alerts = analyze_enemy_gear(self.gear_seen.value, lang)
        embed = discord.Embed(title=t("scout_result_title", lang), color=discord.Color.dark_orange())
        embed.add_field(name=t("scout_input_field", lang), value=self.gear_seen.value[:1000], inline=False)
        for a in alerts:
            embed.add_field(name="\u200b", value=a, inline=False)
        embed.set_footer(text=t("scout_footer", lang))
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ScoutView(discord.ui.View):
    def __init__(self, lang: str):
        super().__init__(timeout=60)
        self.lang = lang
        self.open_modal.label = t("scout_button_label", lang)

    @discord.ui.button(label="صف عتاد الخصم", emoji="🔍", style=discord.ButtonStyle.danger)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ScoutModal(self.lang))


# ---------------------------------------------------------------------------
# /heroes و /geartiers
# ---------------------------------------------------------------------------

class HeroCategoryView(discord.ui.View):
    def __init__(self, heroes_data: dict, lang: str):
        super().__init__(timeout=60)
        self.heroes_data = heroes_data
        self.lang = lang
        self.economy.label = t("heroes_btn_economy", lang)
        self.free_war.label = t("heroes_btn_free_war", lang)
        self.paid_war.label = t("heroes_btn_paid_war", lang)

    @discord.ui.button(label="🧪 أبطال التطوير", style=discord.ButtonStyle.secondary)
    async def economy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send(interaction, "economy", t("heroes_title_economy", self.lang))

    @discord.ui.button(label="🆓 أبطال حرب مجانيين", style=discord.ButtonStyle.green)
    async def free_war(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send(interaction, "free_war", t("heroes_title_free_war", self.lang))

    @discord.ui.button(label="💎 أبطال حرب للشحن", style=discord.ButtonStyle.blurple)
    async def paid_war(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send(interaction, "paid_war", t("heroes_title_paid_war", self.lang))

    async def _send(self, interaction: discord.Interaction, key: str, title: str):
        heroes = self.heroes_data[key]
        desc = "\n".join(f"{h['emoji']} **{h['name']}** — {h['role']}" for h in heroes)
        embed = discord.Embed(title=title, description=desc, color=discord.Color.dark_teal())
        await interaction.response.send_message(embed=embed, ephemeral=True)


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
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🏹 عتاد الصيد", style=discord.ButtonStyle.success)
    async def hunting(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self.lang
        info = self.gear_tiers["hunting"]
        embed = discord.Embed(
            title=t("geartiers_hunting_title", lang, emoji=info["emoji"]), color=discord.Color.green()
        )
        embed.add_field(name="💎 P2P", value=info["p2p"], inline=False)
        embed.add_field(name="🆓 F2P", value=info["f2p"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🏗️ عتاد الاقتصاد", style=discord.ButtonStyle.secondary)
    async def economy(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self.lang
        info = self.gear_tiers["economy"]
        embed = discord.Embed(
            title=t("geartiers_economy_title", lang, emoji=info["emoji"]), color=discord.Color.orange()
        )
        embed.add_field(name=t("gear_pieces_field", lang), value=info["pieces"], inline=False)
        embed.add_field(name=t("gear_warning_field", lang), value=info["warning"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# الـ Cog
# ---------------------------------------------------------------------------

class IntelCog(commands.Cog):
    """استخبارات: كشف الخصم الضعيف، خلاصة الأبطال، وتصنيف العتاد."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.heroes_data = load_json_data("heroes.json")
        self.gear_tiers = load_json_data("gear_tiers.json")

    @app_commands.command(name="scout", description="🔍 اكتشف هل الخصم ضعيف من عتاده (عتاد اقتصادي/جواهر ملخبطة)")
    async def scout(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(
            t("scout_button_prompt", lang), view=ScoutView(lang), ephemeral=True
        )

    @app_commands.command(name="heroes", description="🦸 خلاصة أفضل الأبطال (تطوير / حرب مجاني / حرب مدفوع)")
    async def heroes(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(
            t("heroes_prompt", lang), view=HeroCategoryView(self.heroes_data, lang), ephemeral=True
        )

    @app_commands.command(name="geartiers", description="🧰 تصنيف العتاد الكامل (حرب / صيد / اقتصاد)")
    async def geartiers(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(
            t("geartiers_prompt", lang), view=GearTierView(self.gear_tiers, lang), ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(IntelCog(bot))
