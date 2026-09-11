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
        await interaction.response.send_message(confirm)


class SetupHuntChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, lang: str):
        self.lang = lang
        super().__init__(
            placeholder=t("setup_hunt_channel_select_placeholder", lang),
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        channel = self.values[0]
        data = load(HUNT_FILE)
        bucket = _get_hunt_bucket(interaction.guild_id)
        data[str(interaction.guild_id)] = bucket
        bucket["channel_id"] = channel.id
        save(HUNT_FILE, data)
        await interaction.response.send_message(
            t("setup_hunt_channel_set_confirm", lang, channel=channel.mention)
        )


class SetupLeadershipRoleSelect(discord.ui.RoleSelect):
    def __init__(self, lang: str):
        self.lang = lang
        super().__init__(
            placeholder=t("setup_leadership_role_select_placeholder", lang),
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        role = self.values[0]
        set_leadership_role_id(interaction.guild_id, role.id)
        await interaction.response.send_message(
            t("setup_leadership_role_set_confirm", lang, role=role.mention)
            
        )


class SetupView(discord.ui.View):
    def __init__(self, lang: str):
        super().__init__(timeout=300)
        self.add_item(SetupLanguageSelect())
        self.add_item(SetupHuntChannelSelect(lang))
        self.add_item(SetupLeadershipRoleSelect(lang))
        self.add_item(SetupDiagnosticsButton(lang))


class SetupDiagnosticsButton(discord.ui.Button):
    """زرار 🩺 فحص الإعدادات: بيتأكد إن كل حاجة اتضبطت فعلاً شغالة، مش بس متسجلة."""

    def __init__(self, lang: str):
        super().__init__(label=t("setup_diagnostics_button_label", lang), style=discord.ButtonStyle.secondary, row=3)

    async def callback(self, interaction: discord.Interaction):
        embed = build_diagnostics_embed(interaction)
        await interaction.response.send_message(embed=embed)


def _check_line(ok: bool, ok_text: str, bad_text: str, warn: bool = False) -> str:
    if ok:
        return f"✅ {ok_text}"
    return f"⚠️ {bad_text}" if warn else f"❌ {bad_text}"


def build_diagnostics_embed(interaction: discord.Interaction) -> discord.Embed:
    """يبني تقرير حالة حقيقي لكل إعداد - بيتحقق من صلاحيات فعلية مش بس إن القيمة متسجلة."""
    guild = interaction.guild
    me = guild.me if guild else None
    lang = get_lang(interaction.guild_id, interaction.user.id)

    lines: list[str] = []

    # 1) اللغة
    lang_label = "العربية 🇪🇬" if lang == "ar" else "English 🇬🇧"
    lines.append(t("setup_diag_lang_line", lang, lang_label=lang_label))

    # 2) قناة تقارير الصيد
    hunt_bucket = load(HUNT_FILE).get(str(interaction.guild_id), {})
    hunt_channel_id = hunt_bucket.get("channel_id")
    if not hunt_channel_id:
        lines.append(t("setup_diag_hunt_channel_not_set", lang))
    else:
        channel = guild.get_channel(hunt_channel_id) if guild else None
        if not channel:
            lines.append(t("setup_diag_hunt_channel_deleted", lang))
        else:
            perms = channel.permissions_for(me) if me else None
            if perms and perms.send_messages and perms.embed_links:
                lines.append(t("setup_diag_hunt_channel_ok", lang, channel=channel.mention))
            else:
                lines.append(t("setup_diag_hunt_channel_perms_missing", lang, channel=channel.mention))

    # 3) رتبة قادة التحالف (R4/R5)
    role_id = get_leadership_role_id(interaction.guild_id)
    if not role_id:
        lines.append(t("setup_diag_role_not_set", lang))
    else:
        role = guild.get_role(role_id) if guild else None
        if not role:
            lines.append(t("setup_diag_role_deleted", lang))
        elif role.mentionable or (me and me.guild_permissions.mention_everyone):
            lines.append(t("setup_diag_role_ok", lang, role=role.mention))
        else:
            lines.append(t("setup_diag_role_warn", lang, role=role.mention))

    # 4) رابط فتح اللعبة
    link = get_game_link(interaction.guild_id) if guild else DEFAULT_GAME_LINK
    if link == DEFAULT_GAME_LINK:
        lines.append(t("setup_diag_link_default", lang))
    else:
        lines.append(t("setup_diag_link_custom", lang, link=link))

    # 5) مفتاح Cohere (/ai و/hunt_log بوضع الصورة)
    if os.getenv("COHERE_API_KEY"):
        lines.append(t("setup_diag_cohere_ok", lang))
    else:
        lines.append(t("setup_diag_cohere_missing", lang))

    # 6) PyNaCl (الصوت وقت تصعيد /shield)
    try:
        import nacl  # noqa: F401
        lines.append(t("setup_diag_nacl_ok", lang))
    except ImportError:
        lines.append(t("setup_diag_nacl_missing", lang))

    # 7) Server Members Intent
    if interaction.client.intents.members:
        lines.append(t("setup_diag_intent_ok", lang))
    else:
        lines.append(t("setup_diag_intent_missing", lang))

    # 8) صلاحيات البوت الأساسية في السيرفر
    if me:
        base_ok = me.guild_permissions.send_messages and me.guild_permissions.embed_links
        voice_ok = me.guild_permissions.connect and me.guild_permissions.speak
        lines.append(_check_line(
            base_ok,
            t("setup_diag_base_perms_ok", lang),
            t("setup_diag_base_perms_bad", lang)
        ))
        lines.append(_check_line(
            voice_ok,
            t("setup_diag_voice_perms_ok", lang),
            t("setup_diag_voice_perms_bad", lang)
        ))

    healthy = sum(1 for l in lines if l.startswith("✅"))
    warnings = sum(1 for l in lines if l.startswith("⚠️"))
    broken = sum(1 for l in lines if l.startswith("❌"))

    color = CRIMSON if broken else GOLD
    embed = styled_embed(
        title=t("setup_diag_title", lang),
        description="\n".join(lines),
        color=color,
        lang=lang
    )
    embed.add_field(
        name=t("setup_diag_summary_field", lang),
        value=t("setup_diag_summary_value", lang, healthy=healthy, warnings=warnings, broken=broken),
        inline=False
    )
    return embed


class SetupCog(commands.Cog):
    """دليل التثبيت السريع للجدد - /setup."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="⚙️ (إدارة) دليل التثبيت السريع: اللغة، قناة الصيد، رتبة القيادة - كله بضغطة زر"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_cmd(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        embed = styled_embed(
            title=t("setup_embed_title", lang),
            description=t("setup_embed_description", lang),
            color=GOLD,
            lang=lang
        )
        current_role_id = get_leadership_role_id(interaction.guild_id)
        if current_role_id and interaction.guild and interaction.guild.get_role(current_role_id):
            embed.add_field(
                name=t("setup_current_role_field", lang),
                value=interaction.guild.get_role(current_role_id).mention,
                inline=False
            )
        await interaction.response.send_message(embed=embed, view=SetupView(lang), ephemeral=False)

    @setup_cmd.error
    async def setup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("bot_channel_admin_only", lang), ephemeral=False)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=False)

    @app_commands.command(
        name="setup_check",
        description="🩺 (إدارة) فحص سريع: هل إعدادات البوت (قناة الصيد، رتبة القيادة، الصوت، الـAI...) شغالة فعلاً؟"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_check(self, interaction: discord.Interaction):
        embed = build_diagnostics_embed(interaction)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @setup_check.error
    async def setup_check_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("bot_channel_admin_only", lang), ephemeral=False)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
