import asyncio
import math
import re
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang, t, EVENT_TYPE_LABELS_I18N, EVENT_CATEGORY_LABELS_I18N

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
        label="⏱️ الوقت اللازم لكل مرة (اختياري)", placeholder="مثال: 30", required=False
    )
    available_speedups = discord.ui.TextInput(
        label="🚀 التسريعات المتاحة (مثال: 24×2, 8×3)",
        placeholder="24×2, 8×3 أو 4h, 1d×2",
        required=False
    )
    ai_question = discord.ui.TextInput(
        label="🤖 سؤال للـAI (اختياري)",
        placeholder="اسأل عن الحدث أو سيب الـAI يساعدك",
        style=discord.TextStyle.paragraph,
        required=False
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
        self.required_points.placeholder = t("event_placeholder_required_points", lang)
        self.points_per_action.placeholder = t("event_placeholder_points_per_action", lang)
        self.time_per_action.placeholder = t("event_placeholder_time_per_action", lang)
        self.available_speedups.placeholder = t("event_placeholder_speedups", lang)

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.lang
        question = self.ai_question.value.strip()
        if question:
            await interaction.response.defer(thinking=True)
        try:
            required = float(self.required_points.value)
            per_action = float(self.points_per_action.value)
            if required <= 0 or per_action <= 0:
                raise ValueError
        except ValueError:
            if question:
                from cogs.ai_cog import ask_ai
                answer = await ask_ai(
                    question,
                    extra_context=f"الحدث المختار: {self.event_label}. البيانات التي أدخلها المستخدم غير مكتملة أو غير صحيحة.",
                    lang=lang,
                    guild_id=interaction.guild_id
                )
                await (interaction.followup.send if question else interaction.response.send_message)(embed=discord.Embed(title="🤖 مساعدة الحدث", description=answer[:3500], color=discord.Color.blurple()))
            else:
                await (interaction.followup.send if question else interaction.response.send_message)(t("event_invalid_numbers", lang), ephemeral=True)
            return

        time_raw = self.time_per_action.value.strip()
        try:
            per_time = float(time_raw) if time_raw else None
            if per_time is not None and per_time <= 0:
                raise ValueError
        except ValueError:
            await (interaction.followup.send if question else interaction.response.send_message)(t("event_invalid_numbers", lang), ephemeral=True)
            return

        speedup_raw = self.available_speedups.value.strip()
        if speedup_raw:
            speedups, speedup_breakdown, speedup_errors = parse_speedup_text(speedup_raw, lang)
        else:
            speedups, speedup_breakdown, speedup_errors = 0.0, [], []

        actions_needed = math.ceil(required / per_action)
        time_needed = actions_needed * per_time if per_time is not None else None

        embed = discord.Embed(
            title=t("event_result_title", lang, label=self.event_label),
            color=discord.Color.gold()
        )
        embed.add_field(name=t("event_required_points_field", lang), value=f"{required:,.0f}", inline=True)
        embed.add_field(name=t("event_points_per_action_field", lang), value=f"{per_action:,.0f}", inline=True)
        embed.add_field(name=t("event_actions_needed_field", lang), value=f"{actions_needed:,}", inline=True)
        if time_needed is None:
            embed.add_field(name=t("event_total_time_field", lang), value=t("event_time_not_provided", lang), inline=True)
        else:
            embed.add_field(name=t("event_total_time_field", lang), value=fmt_minutes(time_needed, lang), inline=True)
        embed.add_field(name=t("event_speedups_available_field", lang), value=fmt_minutes(speedups, lang), inline=True)
        if speedup_breakdown:
            embed.add_field(name=t("speedup_breakdown_field", lang), value="\n".join(speedup_breakdown)[:1024], inline=False)
        if speedup_errors:
            embed.add_field(name=t("speedup_errors_field", lang), value=", ".join(speedup_errors)[:1024], inline=False)

        if time_needed is not None:
            if speedups >= time_needed:
                remaining = speedups - time_needed
                embed.add_field(name=t("event_can_complete_field", lang), value=t("event_can_complete_value", lang), inline=False)
                embed.add_field(name=t("event_remaining_speedups_field", lang), value=fmt_minutes(remaining, lang), inline=False)
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
                embed.add_field(name=t("event_missing_speedups_field", lang), value=fmt_minutes(missing, lang), inline=False)
                embed.color = discord.Color.orange()
        else:
            embed.add_field(name=t("event_time_optional_note", lang), value=t("event_time_optional_value", lang), inline=False)

        if question:
            from cogs.ai_cog import ask_ai
            answer = await ask_ai(
                question,
                extra_context=f"نتيجة حاسبة الحدث: {actions_needed} أفعال، التسريعات المتاحة: {fmt_minutes(speedups, lang)}.",
                lang=lang,
                guild_id=interaction.guild_id
            )
            embed.add_field(name="🤖 مساعدة الـAI", value=answer[:1024], inline=False)

        embed.set_footer(text=t("event_footer", lang))
        await (interaction.followup.send if question else interaction.response.send_message)(embed=embed)

class EventTypeSelect(discord.ui.Select):
    def __init__(self, lang: str, category_label: str):
        self.lang = lang
        self.category_label = category_label
        options = [
            discord.SelectOption(label=EVENT_TYPE_LABELS_I18N[key][lang], value=key)
            for key in EVENT_TYPE_KEYS
        ]
        super().__init__(placeholder=t("event_select_placeholder", lang), options=options)

    async def callback(self, interaction: discord.Interaction):
        type_label = EVENT_TYPE_LABELS_I18N[self.values[0]][self.lang]
        full_label = f"{self.category_label} - {type_label}"
        await interaction.response.send_modal(EventCalcModal(self.values[0], full_label, self.lang))


class EventTypeView(discord.ui.View):
    def __init__(self, lang: str, category_label: str):
        super().__init__(timeout=120)
        self.add_item(EventTypeSelect(lang, category_label))


class EventCategorySelect(discord.ui.Select):
    def __init__(self, lang: str):
        self.lang = lang
        options = [
            discord.SelectOption(label=EVENT_CATEGORY_LABELS_I18N[key][lang], value=key)
            for key in ("hell", "solo")
        ]
        super().__init__(placeholder=t("event_category_select_placeholder", lang), options=options)

    async def callback(self, interaction: discord.Interaction):
        category_label = EVENT_CATEGORY_LABELS_I18N[self.values[0]][self.lang]
        await interaction.response.edit_message(
            content=t("event_prompt", self.lang, category=category_label),
            view=EventTypeView(self.lang, category_label)
        )


class EventCategoryView(discord.ui.View):
    def __init__(self, lang: str):
        super().__init__(timeout=120)
        self.add_item(EventCategorySelect(lang))


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
# /speedup - حساب إجمالي التسريعات (يفهم صيغة "4h, 6h, 1d×3")
# ---------------------------------------------------------------------------

# وحدة تلقائية = ساعات لو محدش كتب وحدة (زي "24×4")
SPEEDUP_UNIT_MINUTES = {"d": 24 * 60, "h": 60, "m": 1}
SPEEDUP_UNIT_ALIASES = {
    "d": "d", "day": "d", "days": "d", "يوم": "d", "أيام": "d",
    "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h", "ساعة": "h", "ساعات": "h",
    "m": "m", "min": "m", "mins": "m", "minute": "m", "minutes": "m", "دقيقة": "m", "دقايق": "m",
}
SPEEDUP_ENTRY_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Zء-ي]*)\s*(?:[×xX*]\s*(\d+(?:\.\d+)?))?\s*$"
)

SPEEDUP_SEARCH_RE = re.compile(
    r"(?<![\w])(\d+(?:\.\d+)?)\s*(days?|d|hours?|hrs?|hr|h|minutes?|mins?|min|m|يوم|أيام|ساعة|ساعات|دقيقة|دقايق)\s*(?:[×xX*]\s*(\d+(?:\.\d+)?))?",
    re.IGNORECASE
)


def parse_speedup_text(raw: str, lang: str = "ar") -> tuple[float, list[str], list[str]]:
    """
    يفهم نص زي "4h, 6h, 1d×3" أو "24×4, 3d×2" ويرجع:
    (إجمالي الدقائق, تفاصيل كل بند بعد الحساب, أخطاء البنود اللي ما اتفهمتش)
    لو مفيش وحدة (زي "24×4") بتتفسر ساعات افتراضياً.
    """
    total_minutes = 0.0
    breakdown: list[str] = []
    errors: list[str] = []

    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = SPEEDUP_ENTRY_RE.match(chunk)
        if not match:
            embedded_matches = list(SPEEDUP_SEARCH_RE.finditer(chunk))
            if not embedded_matches:
                errors.append(chunk)
                continue
            for embedded in embedded_matches:
                amount_str, unit_str, multiplier_str = embedded.groups()
                amount = float(amount_str)
                multiplier = float(multiplier_str) if multiplier_str else 1.0
                unit_key = SPEEDUP_UNIT_ALIASES.get(unit_str.lower())
                if unit_key is None:
                    continue
                entry_minutes = amount * SPEEDUP_UNIT_MINUTES[unit_key] * multiplier
                total_minutes += entry_minutes
                breakdown.append(f"{embedded.group(0).strip()} = {fmt_minutes(entry_minutes, lang)}")
            continue

        amount_str, unit_str, multiplier_str = match.groups()
        amount = float(amount_str)
        multiplier = float(multiplier_str) if multiplier_str else 1.0
        unit_key = SPEEDUP_UNIT_ALIASES.get(unit_str.lower(), "h" if not unit_str else None)
        if unit_key is None:
            errors.append(chunk)
            continue

        entry_minutes = amount * SPEEDUP_UNIT_MINUTES[unit_key] * multiplier
        total_minutes += entry_minutes
        breakdown.append(f"{chunk} = {fmt_minutes(entry_minutes, lang)}")

    return total_minutes, breakdown, errors


class SpeedupModal(discord.ui.Modal):
    entries = discord.ui.TextInput(
        label="🚀 التسريعات",
        style=discord.TextStyle.paragraph,
        placeholder="مثال: 4h, 6h, 1d×3  أو  24×4, 3d×2"
    )
    ai_question = discord.ui.TextInput(
        label="🤖 سؤال للـAI (اختياري)",
        placeholder="اسأل عن التسريعات أو طريقة استخدامها",
        style=discord.TextStyle.paragraph,
        required=False
    )

    def __init__(self, lang: str):
        super().__init__(title=t("speedup_modal_title", lang))
        self.lang = lang
        self.entries.label = t("speedup_field_entries", lang)[:45]
        self.entries.placeholder = t("speedup_field_entries_placeholder", lang)

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.lang
        total_minutes, breakdown, errors = parse_speedup_text(self.entries.value, lang)
        question = self.ai_question.value.strip()
        if question:
            await interaction.response.defer(thinking=True)

        if not breakdown:
            if question:
                from cogs.ai_cog import ask_ai
                answer = await ask_ai(question, extra_context=f"المدخلات التي كتبها المستخدم للتسريعات: {self.entries.value}", lang=lang, guild_id=interaction.guild_id)
                await (interaction.followup.send if question else interaction.response.send_message)(embed=discord.Embed(title="🤖 مساعدة التسريعات", description=answer[:3500], color=discord.Color.blurple()))
            else:
                await (interaction.followup.send if question else interaction.response.send_message)(t("speedup_invalid_numbers", lang), ephemeral=True)
            return

        embed = discord.Embed(
            title=t("speedup_result_title", lang),
            description=f"**{fmt_minutes(total_minutes, lang)}**",
            color=discord.Color.purple(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name=t("speedup_breakdown_field", lang), value="\n".join(breakdown)[:1024], inline=False)
        embed.add_field(name=t("speedup_in_hours_field", lang), value=f"{total_minutes / 60:g} {t('speedup_hours_unit', lang)}", inline=True)
        if errors:
            embed.add_field(name=t("speedup_errors_field", lang), value=", ".join(errors)[:1024], inline=False)
        if question:
            from cogs.ai_cog import ask_ai
            answer = await ask_ai(question, extra_context=f"إجمالي التسريعات المحسوب: {fmt_minutes(total_minutes, lang)}. التفاصيل: {', '.join(breakdown)}", lang=lang, guild_id=interaction.guild_id)
            embed.add_field(name="🤖 مساعدة الـAI", value=answer[:1024], inline=False)

        await (interaction.followup.send if question else interaction.response.send_message)(embed=embed)

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
            t("event_category_prompt", lang),
            view=EventCategoryView(lang)
            
        )

    @app_commands.command(name="shelter", description="🛡️ مؤقت حماية الجيش في المخبأ مع تنبيه قبل الانتهاء بـ15 دقيقة")
    async def shelter(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(
            t("shelter_prompt", lang), view=ShelterDurationView(self, lang)
        )

    async def start_shelter(self, interaction: discord.Interaction, hours: int):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        end_time = datetime.utcnow() + timedelta(hours=hours)
        await interaction.response.send_message(
            t("shelter_started", lang, hours=hours, end_time=end_time.strftime('%H:%M UTC'))
            
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

    @app_commands.command(name="speedup", description="🚀 اجمع كل تسريعاتك في نص واحد (مثال: 4h, 6h, 1d×3) واعرف الإجمالي")
    async def speedup(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        await interaction.response.send_modal(SpeedupModal(lang))


async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
