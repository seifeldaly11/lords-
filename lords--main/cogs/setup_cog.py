"""
/setup - دليل التثبيت السريع لمدراء السيرفر (Onboarding).
بضغطة زر واحدة (Select Menus فعلية، مش كتابة أوامر يدوياً)، يضبط:
  🌐 لغة البوت
  🏹 قناة تقارير الصيد اليومي (+ التارجت الافتراضي)
  📣 رتبة قادة التحالف (R4/R5) اللي هتتمنشن تلقائياً في تنبيهات /shield لو محدش رد

كل اختيار بيتخزن فوراً (نفس دوال load/save المستخدمة في باقي الكوجز)، فمفيش حاجة
"تتأكد" بأمر منفصل - الواجهة نفسها بترجع تأكيد لحظي تحت كل قائمة.

كمان فيه فحص حالة (🩺 Diagnostics) بيتحقق فعلياً إن كل إعداد شغال صح مش بس متسجل:
صلاحيات القناة، إمكانية منشنة رتبة القيادة فعلياً، مفتاح Cohere، PyNaCl للصوت،
Server Members Intent، وصلاحيات البوت الأساسية - عشان مدير السيرفر يكتشف أي مشكلة
قبل ما تحصل وقت الأزمة (زي درع خلص والبوت مش قادر يرن أو يمنشن حد).
"""
import os

import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import set_lang, get_lang, t
from utils.storage import load, save, set_leadership_role_id, get_leadership_role_id, get_game_link
from utils.ui import styled_embed, GOLD, EMERALD, CRIMSON

HUNT_FILE = "hunt_log"
DEFAULT_DAILY_TARGET = 100
DEFAULT_GAME_LINK = "https://www.lordsmobile.com/"


def _get_hunt_bucket(guild_id: int) -> dict:
    data = load(HUNT_FILE)
    gid = str(guild_id)
    data.setdefault(gid, {"channel_id": None, "daily_target": DEFAULT_DAILY_TARGET, "members": {}})
    return data[gid]


class SetupLanguageSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🇪🇬 العربية", value="ar"),
            discord.SelectOption(label="🇬🇧 English", value="en"),
        ]
        super().__init__(placeholder="🌐 لغة ردود البوت | Bot reply language", options=options)

    async def callback(self, interaction: discord.Interaction):
        set_lang(interaction.guild_id, self.values[0])
        confirm = "✅ اتضبطت اللغة: العربية" if self.values[0] == "ar" else "✅ Language set: English"
        await interaction.response.send_message(confirm, ephemeral=True)


class SetupHuntChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="🏹 قناة تقارير الصيد اليومي (اختياري)",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        data = load(HUNT_FILE)
        bucket = _get_hunt_bucket(interaction.guild_id)
        data[str(interaction.guild_id)] = bucket
        bucket["channel_id"] = channel.id
        save(HUNT_FILE, data)
        await interaction.response.send_message(f"✅ قناة الصيد اتضبطت: {channel.mention}", ephemeral=True)


class SetupLeadershipRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(
            placeholder="📣 رتبة قادة التحالف (R4/R5) لتنبيهات الدرع (اختياري)",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        set_leadership_role_id(interaction.guild_id, role.id)
        await interaction.response.send_message(
            f"✅ رتبة القيادة اتضبطت: {role.mention} — هتتمنشن تلقائياً لو حد اتأخر يرد على تنبيه درعه.",
            ephemeral=True,
        )


class SetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(SetupLanguageSelect())
        self.add_item(SetupHuntChannelSelect())
        self.add_item(SetupLeadershipRoleSelect())
        self.add_item(SetupDiagnosticsButton())


class SetupDiagnosticsButton(discord.ui.Button):
    """زرار 🩺 فحص الإعدادات: بيتأكد إن كل حاجة اتضبطت فعلاً شغالة، مش بس متسجلة."""

    def __init__(self):
        super().__init__(label="🩺 فحص الإعدادات الحالية", style=discord.ButtonStyle.secondary, row=3)

    async def callback(self, interaction: discord.Interaction):
        embed = build_diagnostics_embed(interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)


def _check_line(ok: bool, ok_text: str, bad_text: str, warn: bool = False) -> str:
    if ok:
        return f"✅ {ok_text}"
    return f"⚠️ {bad_text}" if warn else f"❌ {bad_text}"


def build_diagnostics_embed(interaction: discord.Interaction) -> discord.Embed:
    """يبني تقرير حالة حقيقي لكل إعداد - بيتحقق من صلاحيات فعلية مش بس إن القيمة متسجلة."""
    guild = interaction.guild
    me = guild.me if guild else None
    lang = get_lang(interaction.guild_id)

    lines: list[str] = []

    # 1) اللغة
    lang_label = "العربية 🇪🇬" if lang == "ar" else "English 🇬🇧"
    lines.append(f"✅ اللغة مضبوطة: **{lang_label}**")

    # 2) قناة تقارير الصيد
    hunt_bucket = load(HUNT_FILE).get(str(interaction.guild_id), {})
    hunt_channel_id = hunt_bucket.get("channel_id")
    if not hunt_channel_id:
        lines.append("⚠️ قناة تقارير الصيد لسه ماتحددتش (اختياري - `/hunt_log` هيرد في نفس القناة اللي بتنفّذ فيها الأمر)")
    else:
        channel = guild.get_channel(hunt_channel_id) if guild else None
        if not channel:
            lines.append("❌ قناة الصيد المحددة اتمسحت أو البوت طرد منها - اضبطها تاني من `/setup`")
        else:
            perms = channel.permissions_for(me) if me else None
            if perms and perms.send_messages and perms.embed_links:
                lines.append(f"✅ قناة الصيد شغالة: {channel.mention}")
            else:
                lines.append(f"❌ البوت ناقصه صلاحية Send Messages/Embed Links في {channel.mention}")

    # 3) رتبة قادة التحالف (R4/R5)
    role_id = get_leadership_role_id(interaction.guild_id)
    if not role_id:
        lines.append("⚠️ رتبة القيادة لسه ماتحددتش (اختياري - تنبيه `/shield` مش هيمنشن حد لو الدرع خلص من غير رد)")
    else:
        role = guild.get_role(role_id) if guild else None
        if not role:
            lines.append("❌ رتبة القيادة المحددة اتمسحت - اضبط رتبة تانية من `/setup`")
        elif role.mentionable or (me and me.guild_permissions.mention_everyone):
            lines.append(f"✅ رتبة القيادة هتتمنشن فعلياً: {role.mention}")
        else:
            lines.append(
                f"⚠️ رتبة القيادة {role.mention} مضبوطة، بس الرتبة مش Mentionable والبوت مالوش صلاحية "
                "Mention Everyone - يعني المنشنة ممكن متوصلش تنبيه فعلي. فعّل \"Allow anyone to mention\" "
                "في إعدادات الرتبة، أو ادّي البوت صلاحية Mention Everyone."
            )

    # 4) رابط فتح اللعبة
    link = get_game_link(interaction.guild_id) if guild else DEFAULT_GAME_LINK
    if link == DEFAULT_GAME_LINK:
        lines.append("⚠️ رابط اللعبة لسه بالقيمة الافتراضية (اختياري تخصيصه بـ `/set_game_link`)")
    else:
        lines.append(f"✅ رابط اللعبة مخصص: {link}")

    # 5) مفتاح Cohere (/ai و/hunt_log بوضع الصورة)
    if os.getenv("COHERE_API_KEY"):
        lines.append("✅ مفتاح Cohere موجود - `/ai` وتحليل صور الصيد شغالين")
    else:
        lines.append("❌ مفيش COHERE_API_KEY في `.env` - `/ai` وتحليل الصور بالكامل معطّلين حالياً")

    # 6) PyNaCl (الصوت وقت تصعيد /shield)
    try:
        import nacl  # noqa: F401
        lines.append("✅ PyNaCl متثبتة - تصعيد `/shield` الصوتي هيشتغل")
    except ImportError:
        lines.append("❌ PyNaCl مش متثبتة - تصعيد `/shield` الصوتي مش هيشتغل (`pip install PyNaCl`)")

    # 7) Server Members Intent
    if interaction.client.intents.members:
        lines.append("✅ Server Members Intent مفعّل")
    else:
        lines.append(
            "❌ Server Members Intent مقفول من Discord Developer Portal - أوامر زي `/stats_event` "
            "و`/log_activity` ممكن ما تشتغلش صح"
        )

    # 8) صلاحيات البوت الأساسية في السيرفر
    if me:
        base_ok = me.guild_permissions.send_messages and me.guild_permissions.embed_links
        voice_ok = me.guild_permissions.connect and me.guild_permissions.speak
        lines.append(_check_line(base_ok, "صلاحيات الرسائل الأساسية (Send Messages/Embed Links) سليمة", "ناقص صلاحية Send Messages أو Embed Links في السيرفر"))
        lines.append(_check_line(voice_ok, "صلاحيات الصوت (Connect/Speak) سليمة لتصعيد الدرع", "ناقص صلاحية Connect أو Speak - تصعيد `/shield` الصوتي مش هيقدر يدخل الروم"))

    healthy = sum(1 for l in lines if l.startswith("✅"))
    warnings = sum(1 for l in lines if l.startswith("⚠️"))
    broken = sum(1 for l in lines if l.startswith("❌"))

    color = CRIMSON if broken else GOLD
    embed = styled_embed(
        title="🩺 فحص حالة إعدادات البوت",
        description="\n".join(lines),
        color=color,
        lang=lang,
    )
    embed.add_field(
        name="📋 الخلاصة",
        value=f"✅ سليم: {healthy}  •  ⚠️ تنبيه: {warnings}  •  ❌ معطّل: {broken}",
        inline=False,
    )
    return embed


class SetupCog(commands.Cog):
    """دليل التثبيت السريع للجدد - /setup."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="⚙️ (إدارة) دليل التثبيت السريع: اللغة، قناة الصيد، رتبة القيادة - كله بضغطة زر",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_cmd(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        embed = styled_embed(
            title="⚙️ دليل التثبيت السريع",
            description=(
                "اختر من القوائم تحت لضبط البوت لسيرفرك في ثواني - كل اختيار بيتحفظ فوراً "
                "من غير ما تحتاج تكتب أي أمر إضافي.\n\n"
                "🌐 **اللغة** — تتحكم في كل ردود البوت الفعلية.\n"
                "🏹 **قناة الصيد** — فين تتبعت تقارير وملخصات `/hunt_log` تلقائياً.\n"
                "📣 **رتبة القيادة** — مين يتمنشن تلقائياً لو عضو اتأخر يرد على تنبيه `/shield`.\n"
                "🩺 **فحص الإعدادات** — تأكد إن كل حاجة فعلاً شغالة (صلاحيات، Cohere، الصوت...) مش بس متسجلة."
            ),
            color=GOLD,
            lang=lang,
        )
        current_role_id = get_leadership_role_id(interaction.guild_id)
        if current_role_id and interaction.guild and interaction.guild.get_role(current_role_id):
            embed.add_field(
                name="📣 رتبة القيادة الحالية",
                value=interaction.guild.get_role(current_role_id).mention,
                inline=False,
            )
        await interaction.response.send_message(embed=embed, view=SetupView(), ephemeral=True)

    @setup_cmd.error
    async def setup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id)
        if isinstance(error, app_commands.MissingPermissions):
            msg = "❌ الأمر ده يحتاج صلاحية Manage Server." if lang == "ar" else "❌ This command requires Manage Server."
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)

    @app_commands.command(
        name="setup_check",
        description="🩺 (إدارة) فحص سريع: هل إعدادات البوت (قناة الصيد، رتبة القيادة، الصوت، الـAI...) شغالة فعلاً؟",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_check(self, interaction: discord.Interaction):
        embed = build_diagnostics_embed(interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @setup_check.error
    async def setup_check_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id)
        if isinstance(error, app_commands.MissingPermissions):
            msg = "❌ الأمر ده يحتاج صلاحية Manage Server." if lang == "ar" else "❌ This command requires Manage Server."
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
