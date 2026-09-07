import asyncio
import math
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang, t, EVENT_TYPE_LABELS_I18N

EVENT_TYPE_KEYS = [
    "research", "building", "t1", "t2", "t3", "t4", "t5",
    "artifacts", "hunting", "tycoon", "ghosts", "spending",
]


def fmt_minutes(total_minutes: int, lang: str) -> str:
    """يحوّل عدد الدقائق لصيغة أيام/ساعات/دقائق مقروءة حسب اللغة."""
    total_minutes = max(0, int(total_minutes))
    days, rem = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} {t('fmt_unit_day', lang)}")
    if hours:
        parts.append(f"{hours} {t('fmt_unit_hour', lang)}")
    if minutes or not parts:
        parts.append(f"{minutes} {t('fmt_unit_minute', lang)}")
    return t("fmt_joiner", lang).join(parts)


# ---------------------------------------------------------------------------
# /event - حاسبة أحداث الجحيم/المنفرد
# ---------------------------------------------------------------------------

class EventCalcModal(discord.ui.Modal):
    required_points = discord.ui.TextInput(label="🎯 النقاط المطلوبة للمرحلة", placeholder="مثال: 500000")
    points_per_action = discord.ui.TextInput(label="✨ النقاط لكل مرّة/فعل", placeholder="مثال: 1000")
    time_per_action = discord.ui.TextInput(
        label="⏱️ الوقت اللازم لكل مرة (بالدقائق)", placeholder="مثال: 30"
    )
    available_speedups = discord.ui.TextInput(
        label="🚀 إجمالي التسريحات المتاحة (بالدقائق)", placeholder="مثال: 4320"
    )

    def __init__(self, event_key: str, event_label: str, lang: str):
        super().__init__(title=t("event_modal_title", lang))
        self.event_key = event_key
        self.event_label = event_label
        self.lang = lang
        self.required_points.label = t("event_field_required_points", lang)[:45]
        self.points_per_action.label = t("event_field_points_per_action", lang)[:45]
        self.time_per_action.label = t("event_field_time_per_action", lang)[:45]
        self.available_speedups.label = t("event_field_speedups", lang)[:45]

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.lang
        try:
            required = float(self.required_points.value)
            per_action = float(self.points_per_action.value)
            per_time = float(self.time_per_action.value)
            speedups = float(self.available_speedups.value)
            if per_action <= 0 or per_time <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(t("event_invalid_numbers", lang), ephemeral=True)
            return

        actions_needed = math.ceil(required / per_action)
        time_needed = actions_needed * per_time  # بالدقائق

        embed = discord.Embed(
            title=t("event_result_title", lang, label=self.event_label),
            color=discord.Color.gold(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name=t("event_required_points_field", lang), value=f"{required:,.0f}", inline=True)
        embed.add_field(name=t("event_points_per_action_field", lang), value=f"{per_action:,.0f}", inline=True)
        embed.add_field(name=t("event_actions_needed_field", lang), value=f"{actions_needed:,}", inline=True)
        embed.add_field(name=t("event_total_time_field", lang), value=fmt_minutes(time_needed, lang), inline=True)
        embed.add_field(name=t("event_speedups_available_field", lang), value=fmt_minutes(speedups, lang), inline=True)

        if speedups >= time_needed:
            remaining = speedups - time_needed
            embed.add_field(name=t("event_can_complete_field", lang), value=t("event_can_complete_value", lang), inline=False)
            embed.add_field(
                name=t("event_remaining_speedups_field", lang), value=fmt_minutes(remaining, lang), inline=False
            )
            embed.color = discord.Color.green()
        else:
            missing = time_needed - speedups
            achievable_actions = math.floor(speedups / per_time)
            achievable_points = achievable_actions * per_action
            remaining_points = max(0, required - achievable_points)
            percentage = min(100.0, (achievable_points / required) * 100)
            embed.add_field(name=t("event_cannot_complete_field", lang), value=t("event_cannot_complete_value", lang), inline=False)
            embed.add_field(name=t("event_percentage_field", lang), value=f"{percentage:.1f}%", inline=True)
            embed.add_field(name=t("event_achievable_points_field", lang), value=f"{achievable_points:,.0f}", inline=True)
            embed.add_field(name=t("event_missing_points_field", lang), value=f"{remaining_points:,.0f}", inline=True)
            embed.add_field(
                name=t("event_extra_time_field", lang), value=fmt_minutes(missing, lang), inline=False
            )
            embed.color = discord.Color.orange()

        embed.set_footer(text=t("event_footer", lang))
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EventTypeSelect(discord.ui.Select):
    def __init__(self, lang: str):
        self.lang = lang
        options = [
            discord.SelectOption(label=EVENT_TYPE_LABELS_I18N[key][lang], value=key)
            for key in EVENT_TYPE_KEYS
        ]
        super().__init__(placeholder=t("event_select_placeholder", lang), options=options)

    async def callback(self, interaction: discord.Interaction):
        label = EVENT_TYPE_LABELS_I18N[self.values[0]][self.lang]
        await interaction.response.send_modal(EventCalcModal(self.values[0], label, self.lang))


class EventTypeView(discord.ui.View):
    def __init__(self, lang: str):
        super().__init__(timeout=120)
        self.add_item(EventTypeSelect(lang))


# ---------------------------------------------------------------------------
# /shelter - مؤقت حماية الجيش
# ---------------------------------------------------------------------------

class ShelterDurationView(discord.ui.View):
    def __init__(self, cog: "EventsCog", lang: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.lang = lang
        self.four_hours.label = t("shelter_4h_button", lang)
        self.eight_hours.label = t("shelter_8h_button", lang)
        self.twelve_hours.label = t("shelter_12h_button", lang)

    @discord.ui.button(label="4 ساعات", emoji="🛡️", style=discord.ButtonStyle.secondary)
    async def four_hours(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.start_shelter(interaction, 4)

    @discord.ui.button(label="8 ساعات", emoji="🛡️", style=discord.ButtonStyle.secondary)
    async def eight_hours(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.start_shelter(interaction, 8)

    @discord.ui.button(label="12 ساعة", emoji="🛡️", style=discord.ButtonStyle.secondary)
    async def twelve_hours(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.start_shelter(interaction, 12)


# ---------------------------------------------------------------------------
# /cost - حاسبة تكلفة التدريب
# ---------------------------------------------------------------------------

COST_TIER_KEYS = ["t4", "t5", "research"]
COST_TIER_LABEL_KEYS = {"t4": "cost_tier_t4", "t5": "cost_tier_t5", "research": "cost_tier_research"}


class CostModal(discord.ui.Modal):
    quantity = discord.ui.TextInput(label="🔢 عدد الوحدات المطلوب تدريبها", placeholder="مثال: 10000")
    food = discord.ui.TextInput(label="🍖 تكلفة الطعام لكل وحدة", placeholder="مثال: 500")
    wood_stone = discord.ui.TextInput(label="🪵 تكلفة الخشب/الحجر لكل وحدة", placeholder="مثال: 300")
    ore_gold = discord.ui.TextInput(label="⛏️ تكلفة الخام/الذهب لكل وحدة", placeholder="مثال: 100")
    time_per_unit_sec = discord.ui.TextInput(
        label="⏱️ زمن الوحدة (ثانية) وعدد الطوابير",
        placeholder="مثال: 12,2  (زمن,عدد الطوابير المتزامنة)",
    )

    def __init__(self, tier_key: str, tier_label: str, lang: str):
        super().__init__(title=t("cost_modal_title", lang))
        self.tier_label = tier_label
        self.lang = lang
        self.quantity.label = t("cost_field_quantity", lang)[:45]
        self.food.label = t("cost_field_food", lang)[:45]
        self.wood_stone.label = t("cost_field_wood_stone", lang)[:45]
        self.ore_gold.label = t("cost_field_ore_gold", lang)[:45]
        self.time_per_unit_sec.label = t("cost_field_time_per_unit", lang)[:45]

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.lang
        try:
            qty = float(self.quantity.value)
            food_cost = float(self.food.value)
            ws_cost = float(self.wood_stone.value)
            og_cost = float(self.ore_gold.value)
            raw = self.time_per_unit_sec.value.split(",")
            time_per_unit = float(raw[0].strip())
            queues = float(raw[1].strip()) if len(raw) > 1 and raw[1].strip() else 1
            queues = max(1.0, queues)
        except (ValueError, IndexError):
            await interaction.response.send_message(t("cost_invalid_numbers", lang), ephemeral=True)
            return

        total_food = qty * food_cost
        total_ws = qty * ws_cost
        total_og = qty * og_cost
        total_seconds = math.ceil(qty / queues) * time_per_unit

        embed = discord.Embed(
            title=t("cost_result_title", lang, tier=self.tier_label),
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name=t("cost_quantity_field", lang), value=f"{qty:,.0f}", inline=True)
        embed.add_field(name=t("cost_total_food_field", lang), value=f"{total_food:,.0f}", inline=True)
        embed.add_field(name=t("cost_total_wood_stone_field", lang), value=f"{total_ws:,.0f}", inline=True)
        embed.add_field(name=t("cost_total_ore_gold_field", lang), value=f"{total_og:,.0f}", inline=True)
        embed.add_field(
            name=t("cost_total_time_field", lang), value=fmt_minutes(total_seconds / 60, lang), inline=True
        )
        embed.set_footer(text=t("cost_footer", lang))
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TrainingTierSelect(discord.ui.Select):
    def __init__(self, lang: str):
        self.lang = lang
        options = [
            discord.SelectOption(label=t(COST_TIER_LABEL_KEYS[key], lang), value=key)
            for key in COST_TIER_KEYS
        ]
        super().__init__(placeholder=t("cost_tier_select_placeholder", lang), options=options)

    async def callback(self, interaction: discord.Interaction):
        tier_key = self.values[0]
        tier_label = t(COST_TIER_LABEL_KEYS[tier_key], self.lang)
        await interaction.response.send_modal(CostModal(tier_key, tier_label, self.lang))


class CostTierView(discord.ui.View):
    def __init__(self, lang: str):
        super().__init__(timeout=60)
        self.add_item(TrainingTierSelect(lang))


# ---------------------------------------------------------------------------
# /speedup - حساب إجمالي التسريحات
# ---------------------------------------------------------------------------

class SpeedupModal(discord.ui.Modal):
    days = discord.ui.TextInput(label="📅 إجمالي الأيام", placeholder="مثال: 3", required=False, default="0")
    hours = discord.ui.TextInput(label="⏰ إجمالي الساعات", placeholder="مثال: 12", required=False, default="0")
    minutes = discord.ui.TextInput(label="⏱️ إجمالي الدقائق", placeholder="مثال: 45", required=False, default="0")
    stacks = discord.ui.TextInput(
        label="📦 عدد الحزم المتشابهة (لو عندك أكتر من نسخة)",
        placeholder="مثال: 1",
        required=False,
        default="1",
    )

    def __init__(self, lang: str):
        super().__init__(title=t("speedup_modal_title", lang))
        self.lang = lang
        self.days.label = t("speedup_field_days", lang)[:45]
        self.hours.label = t("speedup_field_hours", lang)[:45]
        self.minutes.label = t("speedup_field_minutes", lang)[:45]
        self.stacks.label = t("speedup_field_stacks", lang)[:45]

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.lang
        try:
            d = float(self.days.value or 0)
            h = float(self.hours.value or 0)
            m = float(self.minutes.value or 0)
            stacks = float(self.stacks.value or 1)
        except ValueError:
            await interaction.response.send_message(t("speedup_invalid_numbers", lang), ephemeral=True)
            return

        total_minutes = (d * 24 * 60 + h * 60 + m) * stacks

        embed = discord.Embed(
            title=t("speedup_result_title", lang),
            description=f"**{fmt_minutes(total_minutes, lang)}**",
            color=discord.Color.purple(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(
            name=t("speedup_in_minutes_field", lang),
            value=f"{total_minutes:,.0f} {t('speedup_minutes_unit', lang)}",
            inline=True,
        )
        embed.add_field(
            name=t("speedup_in_hours_field", lang),
            value=f"{total_minutes / 60:,.1f} {t('speedup_hours_unit', lang)}",
            inline=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# الـ Cog الرئيسي
# ---------------------------------------------------------------------------

class EventsCog(commands.Cog):
    """أوامر حواسب الأحداث وتطوير الحساب."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="event", description="🧮 حاسبة أحداث الجحيم/المنفرد - احسب هل تقدر تكمل المرحلة ولا لأ")
    async def event(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(
            t("event_prompt", lang),
            view=EventTypeView(lang),
            ephemeral=True,
        )

    @app_commands.command(name="shelter", description="🛡️ مؤقت حماية الجيش في المخبأ مع تنبيه قبل الانتهاء بـ15 دقيقة")
    async def shelter(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(
            t("shelter_prompt", lang), view=ShelterDurationView(self, lang), ephemeral=True
        )

    async def start_shelter(self, interaction: discord.Interaction, hours: int):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        end_time = datetime.utcnow() + timedelta(hours=hours)
        await interaction.response.send_message(
            t("shelter_started", lang, hours=hours, end_time=end_time.strftime('%H:%M UTC')),
            ephemeral=True,
        )
        remind_seconds = max(0, hours * 3600 - 15 * 60)
        channel = interaction.channel
        user = interaction.user
        asyncio.create_task(self._shelter_reminder(remind_seconds, channel, user, hours, lang))

    async def _shelter_reminder(self, delay: float, channel, user: discord.abc.User, hours: int, lang: str):
        await asyncio.sleep(delay)
        text = t("shelter_reminder_text", lang, hours=hours)
        try:
            if channel:
                await channel.send(f"{user.mention} {text}")
        except discord.HTTPException:
            pass
        try:
            await user.send(text)
        except discord.Forbidden:
            pass  # المستخدم مقفل الـ DMs

    @app_commands.command(name="cost", description="💰 حاسبة تكلفة تدريب T4/T5 والموارد اللازمة")
    async def cost(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(
            t("cost_prompt", lang), view=CostTierView(lang), ephemeral=True
        )

    @app_commands.command(name="speedup", description="🚀 حساب إجمالي أيام وساعات التسريحات المتاحة بالحقيبة")
    async def speedup(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        await interaction.response.send_modal(SpeedupModal(lang))


async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
