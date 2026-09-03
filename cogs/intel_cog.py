import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load_json_data

# كلمات مفتاحية للكشف عن عتاد الاقتصاد (Noceros / Gryphon / Lunar Flute) بالعربي والإنجليزي
ECONOMY_KEYWORDS = [
    "noceros", "نوسيروس",
    "gryphon", "جريفون", "جريفين",
    "lunar flute", "لونار فلوت", "مزمار",
]

# كلمات مفتاحية لأنواع القوات عشان نكشف تضارب (خوذة رماة + جواهر مشاة مثلاً)
TROOP_KEYWORDS = {
    "🛡️ مشاة": ["مشاة", "infantry"],
    "🏹 رماة": ["رماة", "ranged"],
    "🐎 فرسان": ["فرسان", "cavalry"],
}


def analyze_enemy_gear(text: str) -> list[str]:
    """يحلل نص وصف عتاد الخصم ويرجع قائمة بالتنبيهات المكتشفة."""
    lowered = text.lower()
    alerts = []

    if any(k in lowered for k in ECONOMY_KEYWORDS):
        alerts.append(
            "🚨 **الخصم لابس عتاد تطوير/بحث (اقتصادي)!** دفاعه شبه معدوم - احشده حالاً قبل ما يغيّر عتاده!"
        )

    found_troops = {label for label, kws in TROOP_KEYWORDS.items() if any(k in lowered for k in kws)}
    if len(found_troops) >= 2:
        alerts.append(
            "⚠️ **لخبطة واضحة في نوع العتاد/الجواهر** (تشكيلة مختلطة غير متجانسة) - "
            "على الأغلب حساب مش ممتلك خبرة أو بيلعب بشكل عشوائي، فرصة جيدة للهجوم."
        )

    if not alerts:
        alerts.append("✅ العتاد الموصوف يبدو حرب عادي متجانس - قيّم قوة الجيش الظاهرة قبل ما تقرر تهاجم.")

    return alerts


# ---------------------------------------------------------------------------
# /scout - كاشف الخصم الضعيف
# ---------------------------------------------------------------------------

class ScoutModal(discord.ui.Modal, title="🔍 كشف عتاد الخصم"):
    gear_seen = discord.ui.TextInput(
        label="👀 العتاد اللي شايفه على الخصم",
        style=discord.TextStyle.paragraph,
        placeholder="مثال: خوذة نوسيروس، درع رماة فيه جواهر مشاة...",
    )

    async def on_submit(self, interaction: discord.Interaction):
        alerts = analyze_enemy_gear(self.gear_seen.value)
        embed = discord.Embed(title="🔍 نتيجة تحليل عتاد الخصم", color=discord.Color.dark_orange())
        embed.add_field(name="📋 الوصف المدخل", value=self.gear_seen.value[:1000], inline=False)
        for a in alerts:
            embed.add_field(name="\u200b", value=a, inline=False)
        embed.set_footer(text="تحليل تقريبي مبني على كلمات مفتاحية - استخدمه كمؤشر مش كيقين 100%")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ScoutView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="صف عتاد الخصم", emoji="🔍", style=discord.ButtonStyle.danger)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ScoutModal())


# ---------------------------------------------------------------------------
# /heroes و /geartiers
# ---------------------------------------------------------------------------

class HeroCategoryView(discord.ui.View):
    def __init__(self, heroes_data: dict):
        super().__init__(timeout=60)
        self.heroes_data = heroes_data

    @discord.ui.button(label="🧪 أبطال التطوير", style=discord.ButtonStyle.secondary)
    async def economy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send(interaction, "economy", "🧪 أبطال التطوير (بناء/بحث/طاقة)")

    @discord.ui.button(label="🆓 أبطال حرب مجانيين", style=discord.ButtonStyle.green)
    async def free_war(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send(interaction, "free_war", "🆓 أفضل أبطال حرب مجانيين")

    @discord.ui.button(label="💎 أبطال حرب للشحن", style=discord.ButtonStyle.blurple)
    async def paid_war(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send(interaction, "paid_war", "💎 أفضل أبطال حرب مدفوعين")

    async def _send(self, interaction: discord.Interaction, key: str, title: str):
        heroes = self.heroes_data[key]
        desc = "\n".join(f"{h['emoji']} **{h['name']}** — {h['role']}" for h in heroes)
        embed = discord.Embed(title=title, description=desc, color=discord.Color.dark_teal())
        await interaction.response.send_message(embed=embed, ephemeral=True)


class GearTierView(discord.ui.View):
    def __init__(self, gear_tiers: dict):
        super().__init__(timeout=60)
        self.gear_tiers = gear_tiers

    @discord.ui.button(label="⚔️ عتاد الحرب", style=discord.ButtonStyle.danger)
    async def war(self, interaction: discord.Interaction, button: discord.ui.Button):
        info = self.gear_tiers["war"]
        embed = discord.Embed(title=f"{info['emoji']} تصنيف عتاد الحرب", color=discord.Color.red())
        embed.add_field(name="💎 P2P", value=info["p2p"], inline=False)
        embed.add_field(name="🆓 F2P", value=info["f2p"], inline=False)
        embed.add_field(name="⚠️ عتاد ضعيف", value=info["weak"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🏹 عتاد الصيد", style=discord.ButtonStyle.success)
    async def hunting(self, interaction: discord.Interaction, button: discord.ui.Button):
        info = self.gear_tiers["hunting"]
        embed = discord.Embed(title=f"{info['emoji']} تصنيف عتاد الصيد", color=discord.Color.green())
        embed.add_field(name="💎 P2P", value=info["p2p"], inline=False)
        embed.add_field(name="🆓 F2P", value=info["f2p"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🏗️ عتاد الاقتصاد", style=discord.ButtonStyle.secondary)
    async def economy(self, interaction: discord.Interaction, button: discord.ui.Button):
        info = self.gear_tiers["economy"]
        embed = discord.Embed(title=f"{info['emoji']} عتاد الاقتصاد", color=discord.Color.orange())
        embed.add_field(name="🧩 القطع", value=info["pieces"], inline=False)
        embed.add_field(name="⚠️ تحذير", value=info["warning"], inline=False)
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
        await interaction.response.send_message(
            "اضغط الزر وصف عتاد الخصم اللي شايفه 👇", view=ScoutView(), ephemeral=True
        )

    @app_commands.command(name="heroes", description="🦸 خلاصة أفضل الأبطال (تطوير / حرب مجاني / حرب مدفوع)")
    async def heroes(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "اختر التصنيف اللي عايز تشوفه:", view=HeroCategoryView(self.heroes_data), ephemeral=True
        )

    @app_commands.command(name="geartiers", description="🧰 تصنيف العتاد الكامل (حرب / صيد / اقتصاد)")
    async def geartiers(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "اختر تصنيف العتاد:", view=GearTierView(self.gear_tiers), ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(IntelCog(bot))
