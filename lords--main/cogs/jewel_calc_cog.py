"""
/jewel_calc - حاسبة دمج الجواهر (Jewel Merge Calculator)
تحسب كام جوهر عادي (Common) لازم تجمعه عشان توصل للتاير المستهدف (لغاية الخرافي/Mythic)،
مع تفصيل عدد الجواهر المطلوبة في كل تاير وسطي في الطريق. بتحترم /language بالكامل.

ملاحظة: نسبة الدمج (كام جوهر تحت = 1 فوق) ونسبة نجاح الدمج بتختلف حسب نوع الجوهر
والأحداث الجارية في اللعبة، فالحاسبة بتاخدهم كمدخلات منك (زي باقي حواسب البوت
/cost و/event) بدل ما تفترض رقم ثابت ممكن يبقى غلط.
"""
import math
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang, t

# ترتيب تايرات الجواهر في Lords Mobile من الأدنى للأعلى
JEWEL_TIERS = [
    ("common", "⚪", {"ar": "عادي (Common)", "en": "Common"}),
    ("uncommon", "🟢", {"ar": "غير شائع (Uncommon)", "en": "Uncommon"}),
    ("rare", "🔵", {"ar": "نادر (Rare)", "en": "Rare"}),
    ("epic", "🟣", {"ar": "ملحمي (Epic)", "en": "Epic"}),
    ("legendary", "🟠", {"ar": "أسطوري (Legendary)", "en": "Legendary"}),
    ("mythic", "🔴", {"ar": "خرافي (Mythic)", "en": "Mythic"}),
]


def tier_label(key: str, lang: str) -> str:
    emoji, names = next((e, n) for k, e, n in JEWEL_TIERS if k == key)
    return f"{emoji} {names[lang]}"


class JewelCalcModal(discord.ui.Modal):
    def __init__(self, target_key: str, lang: str):
        super().__init__(title=t("jewel_modal_title", lang))
        self.target_key = target_key
        self.lang = lang
        self.quantity_needed = discord.ui.TextInput(
            label=t("jewel_field_qty", lang)[:45], placeholder="1"
        )
        self.merge_ratio = discord.ui.TextInput(
            label=t("jewel_field_ratio", lang)[:45], placeholder="3", default="3"
        )
        self.success_rate = discord.ui.TextInput(
            label=t("jewel_field_rate", lang)[:45], placeholder="100", default="100", required=False
        )
        self.add_item(self.quantity_needed)
        self.add_item(self.merge_ratio)
        self.add_item(self.success_rate)

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.lang
        try:
            qty = float(self.quantity_needed.value)
            ratio = float(self.merge_ratio.value)
            rate = float(self.success_rate.value or 100)
            if qty <= 0 or ratio <= 0 or not (0 < rate <= 100):
                raise ValueError
        except ValueError:
            await interaction.response.send_message(t("jewel_err", lang), ephemeral=True)
            return

        target_index = next(i for i, (key, _, _) in enumerate(JEWEL_TIERS) if key == self.target_key)
        success_factor = rate / 100.0

        # بنحسب رجوعاً من التاير المستهدف لحد Common، تاير بتاير.
        breakdown = [(tier_label(self.target_key, lang), math.ceil(qty))]
        current_qty = qty
        for i in range(target_index, 0, -1):
            current_qty = math.ceil((current_qty * ratio) / success_factor)
            breakdown.append((tier_label(JEWEL_TIERS[i - 1][0], lang), current_qty))

        total_common = breakdown[-1][1]
        target_label = tier_label(self.target_key, lang)

        embed = discord.Embed(
            title=t("jewel_title", lang, target=target_label),
            color=discord.Color.dark_purple(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name=t("jewel_qty_field", lang), value=f"{qty:,.0f}", inline=True)
        embed.add_field(name=t("jewel_ratio_field", lang), value=f"{ratio:,.0f} : 1", inline=True)
        embed.add_field(name=t("jewel_rate_field", lang), value=f"{rate:.0f}%", inline=True)

        steps_text = "\n".join(
            f"{'🔹' if idx == 0 else '⬇️'} **{label}**: {count:,}"
            for idx, (label, count) in enumerate(breakdown)
        )
        embed.add_field(name=t("jewel_breakdown_field", lang), value=steps_text, inline=False)
        embed.add_field(name=t("jewel_total_field", lang), value=f"**{total_common:,}**", inline=False)
        embed.set_footer(text=t("jewel_footer", lang))
        await interaction.response.send_message(embed=embed, ephemeral=True)


class JewelTierSelect(discord.ui.Select):
    def __init__(self, lang: str):
        self.lang = lang
        options = [
            discord.SelectOption(label=tier_label(key, lang), value=key)
            for key, _, _ in JEWEL_TIERS
            if key != "common"
        ]
        super().__init__(placeholder=t("jewel_select_placeholder", lang), options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(JewelCalcModal(target_key=self.values[0], lang=self.lang))


class JewelTierView(discord.ui.View):
    def __init__(self, lang: str):
        super().__init__(timeout=60)
        self.add_item(JewelTierSelect(lang))


class JewelCalcCog(commands.Cog):
    """حاسبة دمج الجواهر والمعدات."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="jewel_calc",
        description="💎 حاسبة دمج الجواهر - احسب عدد جواهر Common المطلوبة للوصول للخرافي (Mythic)",
    )
    async def jewel_calc(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        await interaction.response.send_message(
            t("jewel_pick_target", lang), view=JewelTierView(lang), ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(JewelCalcCog(bot))
