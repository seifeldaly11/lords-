import asyncio
import math
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

EVENT_TYPES = [
    ("🔬 أبحاث", "research"),
    ("🏗️ بناء", "building"),
    ("⚔️ تدريب T1", "t1"),
    ("⚔️ تدريب T2", "t2"),
    ("⚔️ تدريب T3", "t3"),
    ("⚔️ تدريب T4", "t4"),
    ("⚔️ تدريب T5", "t5"),
    ("🏺 آثار", "artifacts"),
    ("🐾 صيد وحوش", "hunting"),
    ("🎩 تايكون", "tycoon"),
    ("👻 أشباح", "ghosts"),
    ("💎 إنفاق جواهر/تسريحات", "spending"),
]


def fmt_minutes(total_minutes: int) -> str:
    """يحوّل عدد الدقائق لصيغة أيام/ساعات/دقائق مقروءة."""
    total_minutes = max(0, int(total_minutes))
    days, rem = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} يوم")
    if hours:
        parts.append(f"{hours} ساعة")
    if minutes or not parts:
        parts.append(f"{minutes} دقيقة")
    return " و ".join(parts)


# ---------------------------------------------------------------------------
# /event - حاسبة أحداث الجحيم/المنفرد
# ---------------------------------------------------------------------------

class EventCalcModal(discord.ui.Modal, title="🧮 حاسبة الحدث"):
    required_points = discord.ui.TextInput(label="🎯 النقاط المطلوبة للمرحلة", placeholder="مثال: 500000")
    points_per_action = discord.ui.TextInput(label="✨ النقاط لكل مرّة/فعل", placeholder="مثال: 1000")
    time_per_action = discord.ui.TextInput(
        label="⏱️ الوقت اللازم لكل مرة (بالدقائق)", placeholder="مثال: 30"
    )
    available_speedups = discord.ui.TextInput(
        label="🚀 إجمالي التسريحات المتاحة (بالدقائق)", placeholder="مثال: 4320"
    )

    def __init__(self, event_label: str):
        super().__init__()
        self.event_label = event_label

    async def on_submit(self, interaction: discord.Interaction):
        try:
            required = float(self.required_points.value)
            per_action = float(self.points_per_action.value)
            per_time = float(self.time_per_action.value)
            speedups = float(self.available_speedups.value)
            if per_action <= 0 or per_time <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ من فضلك أدخل أرقام صحيحة وأكبر من صفر.", ephemeral=True
            )
            return

        actions_needed = math.ceil(required / per_action)
        time_needed = actions_needed * per_time  # بالدقائق

        embed = discord.Embed(
            title=f"🧮 نتيجة حاسبة: {self.event_label}",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="🎯 النقاط المطلوبة", value=f"{required:,.0f}", inline=True)
        embed.add_field(name="✨ نقاط/فعل", value=f"{per_action:,.0f}", inline=True)
        embed.add_field(name="🔁 عدد الأفعال المطلوبة", value=f"{actions_needed:,}", inline=True)
        embed.add_field(name="⏱️ الوقت الكلي المطلوب", value=fmt_minutes(time_needed), inline=True)
        embed.add_field(name="🚀 التسريحات المتاحة", value=fmt_minutes(speedups), inline=True)

        if speedups >= time_needed:
            remaining = speedups - time_needed
            embed.add_field(name="✅ النتيجة", value="تقدر تكمل الحدث بالكامل!", inline=False)
            embed.add_field(name="🎁 المتبقي من التسريحات بعد الإكمال", value=fmt_minutes(remaining), inline=False)
            embed.color = discord.Color.green()
        else:
            missing = time_needed - speedups
            achievable_actions = math.floor(speedups / per_time)
            achievable_points = achievable_actions * per_action
            remaining_points = max(0, required - achievable_points)
            percentage = min(100.0, (achievable_points / required) * 100)
            embed.add_field(name="⚠️ النتيجة", value="لن تكمل المرحلة بالتسريحات الحالية وحدها.", inline=False)
            embed.add_field(name="📊 نسبة الإنجاز الممكنة حالياً", value=f"{percentage:.1f}%", inline=True)
            embed.add_field(name="🏁 النقاط اللي هتوصلها", value=f"{achievable_points:,.0f}", inline=True)
            embed.add_field(name="❗ النقاط اللي هتفضل ناقصة", value=f"{remaining_points:,.0f}", inline=True)
            embed.add_field(name="⏳ وقت/تسريحات إضافية مطلوبة لإكمالها", value=fmt_minutes(missing), inline=False)
            embed.color = discord.Color.orange()

        embed.set_footer(text="Lords Mobile Companion Bot")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EventTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=label, value=key) for label, key in EVENT_TYPES
        ]
        super().__init__(placeholder="اختر نوع النشاط داخل الحدث...", options=options)

    async def callback(self, interaction: discord.Interaction):
        label = next(lbl for lbl, key in EVENT_TYPES if key == self.values[0])
        await interaction.response.send_modal(EventCalcModal(event_label=label))


class EventTypeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(EventTypeSelect())


# ---------------------------------------------------------------------------
# /shelter - مؤقت حماية الجيش
# ---------------------------------------------------------------------------

class ShelterDurationView(discord.ui.View):
    def __init__(self, cog: "EventsCog"):
        super().__init__(timeout=60)
        self.cog = cog

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

class CostModal(discord.ui.Modal, title="💰 حاسبة تكلفة التدريب"):
    quantity = discord.ui.TextInput(label="🔢 عدد الوحدات المطلوب تدريبها", placeholder="مثال: 10000")
    food = discord.ui.TextInput(label="🍖 تكلفة الطعام لكل وحدة", placeholder="مثال: 500")
    wood_stone = discord.ui.TextInput(label="🪵 تكلفة الخشب/الحجر لكل وحدة", placeholder="مثال: 300")
    ore_gold = discord.ui.TextInput(label="⛏️ تكلفة الخام/الذهب لكل وحدة", placeholder="مثال: 100")
    time_per_unit_sec = discord.ui.TextInput(
        label="⏱️ زمن الوحدة (ثانية) وعدد الطوابير",
        placeholder="مثال: 12,2  (زمن,عدد الطوابير المتزامنة)",
    )

    def __init__(self, tier_label: str):
        super().__init__()
        self.tier_label = tier_label

    async def on_submit(self, interaction: discord.Interaction):
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
            await interaction.response.send_message(
                "❌ تأكد من إدخال أرقام صحيحة، وخانة الزمن بصيغة: الزمن,عدد الطوابير (مثال: 12,2)",
                ephemeral=True,
            )
            return

        total_food = qty * food_cost
        total_ws = qty * ws_cost
        total_og = qty * og_cost
        total_seconds = math.ceil(qty / queues) * time_per_unit

        embed = discord.Embed(
            title=f"💰 تكلفة تدريب: {self.tier_label}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="🔢 عدد الوحدات", value=f"{qty:,.0f}", inline=True)
        embed.add_field(name="🍖 إجمالي الطعام", value=f"{total_food:,.0f}", inline=True)
        embed.add_field(name="🪵 إجمالي الخشب/الحجر", value=f"{total_ws:,.0f}", inline=True)
        embed.add_field(name="⛏️ إجمالي الخام/الذهب", value=f"{total_og:,.0f}", inline=True)
        embed.add_field(name="⏱️ الزمن الكلي التقريبي", value=fmt_minutes(total_seconds / 60), inline=True)
        embed.set_footer(text="القيم المدخلة تقريبية حسب بيانات المستخدم - راجع الأكاديمية للأرقام الدقيقة")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TrainingTierSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="⚔️ تدريب T4", value="T4"),
            discord.SelectOption(label="⚔️ تدريب T5", value="T5"),
            discord.SelectOption(label="🎓 أبحاث الأكاديمية", value="أبحاث"),
        ]
        super().__init__(placeholder="اختر نوع التكلفة المطلوب حسابها...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CostModal(tier_label=self.values[0]))


class CostTierView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(TrainingTierSelect())


# ---------------------------------------------------------------------------
# /speedup - حساب إجمالي التسريحات
# ---------------------------------------------------------------------------

class SpeedupModal(discord.ui.Modal, title="🚀 حاسبة التسريحات"):
    days = discord.ui.TextInput(label="📅 إجمالي الأيام", placeholder="مثال: 3", required=False, default="0")
    hours = discord.ui.TextInput(label="⏰ إجمالي الساعات", placeholder="مثال: 12", required=False, default="0")
    minutes = discord.ui.TextInput(label="⏱️ إجمالي الدقائق", placeholder="مثال: 45", required=False, default="0")
    stacks = discord.ui.TextInput(
        label="📦 عدد الحزم المتشابهة (لو عندك أكتر من نسخة)",
        placeholder="مثال: 1",
        required=False,
        default="1",
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            d = float(self.days.value or 0)
            h = float(self.hours.value or 0)
            m = float(self.minutes.value or 0)
            stacks = float(self.stacks.value or 1)
        except ValueError:
            await interaction.response.send_message("❌ أدخل أرقام صحيحة فقط.", ephemeral=True)
            return

        total_minutes = (d * 24 * 60 + h * 60 + m) * stacks

        embed = discord.Embed(
            title="🚀 إجمالي التسريحات المتاحة",
            description=f"**{fmt_minutes(total_minutes)}**",
            color=discord.Color.purple(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="🔢 بالدقائق", value=f"{total_minutes:,.0f} دقيقة", inline=True)
        embed.add_field(name="🕐 بالساعات", value=f"{total_minutes / 60:,.1f} ساعة", inline=True)
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
        await interaction.response.send_message(
            "اختر نوع النشاط اللي عايز تحسبه من القائمة تحت 👇",
            view=EventTypeView(),
            ephemeral=True,
        )

    @app_commands.command(name="shelter", description="🛡️ مؤقت حماية الجيش في المخبأ مع تنبيه قبل الانتهاء بـ15 دقيقة")
    async def shelter(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "اختر مدة حماية المخبأ:", view=ShelterDurationView(self), ephemeral=True
        )

    async def start_shelter(self, interaction: discord.Interaction, hours: int):
        end_time = datetime.utcnow() + timedelta(hours=hours)
        await interaction.response.send_message(
            f"🛡️ تم تفعيل حماية المخبأ لمدة **{hours} ساعات**.\n"
            f"⏰ هينتهي تقريباً الساعة `{end_time.strftime('%H:%M UTC')}`.\n"
            f"🔔 هوصلك تنبيه هنا وبرسالة خاصة قبل الانتهاء بـ 15 دقيقة.",
            ephemeral=True,
        )
        remind_seconds = max(0, hours * 3600 - 15 * 60)
        channel = interaction.channel
        user = interaction.user
        asyncio.create_task(self._shelter_reminder(remind_seconds, channel, user, hours))

    async def _shelter_reminder(self, delay: float, channel, user: discord.abc.User, hours: int):
        await asyncio.sleep(delay)
        text = f"⏰ تنبيه: حماية المخبأ ({hours} ساعات) هتنتهي خلال **15 دقيقة**! جهّز جيشك 🛡️"
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
        await interaction.response.send_message(
            "اختر نوع التكلفة اللي عايز تحسبها:", view=CostTierView(), ephemeral=True
        )

    @app_commands.command(name="speedup", description="🚀 حساب إجمالي أيام وساعات التسريحات المتاحة بالحقيبة")
    async def speedup(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SpeedupModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
