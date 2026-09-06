"""
/language - يضبط لغة واجهة البوت (عربي/إنجليزي) على مستوى السيرفر.
التفضيل بيتخزن لكل guild_id وبيتحترم في ردود البوت الفعلية (راجع utils/i18n.py
لنطاق التغطية الحالي والحدود اللي فارضاها ديسكورد على أسماء/وصف الأوامر نفسها).
"""
import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang, set_lang, t, SUPPORTED_LANGS
from utils.storage import get_game_link, set_game_link


class SettingsCog(commands.Cog):
    """إعدادات السيرفر (اللغة)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="language", description="🌐 اختر لغة البوت للسيرفر ده (عربي/إنجليزي) | Set the bot's language for this server")
    @app_commands.describe(lang="اختر اللغة | Choose language")
    @app_commands.choices(
        lang=[
            app_commands.Choice(name="🇪🇬 العربية", value="ar"),
            app_commands.Choice(name="🇬🇧 English", value="en"),
        ]
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def language(self, interaction: discord.Interaction, lang: app_commands.Choice[str]):
        set_lang(interaction.guild_id, lang.value)
        key = "lang_set_ar_full" if lang.value == "ar" else "lang_set_en_full"
        await interaction.response.send_message(t(key, lang.value), ephemeral=True)

    @language.error
    async def language_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        current = get_lang(interaction.guild_id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("lang_admin_only", current), ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", current), ephemeral=True)

    @app_commands.command(
        name="set_game_link",
        description="📲 (إدارة) اضبط رابط فتح اللعبة (Deep Link) المستخدم في أزرار التنبيهات السريعة",
    )
    @app_commands.describe(link="الرابط الكامل (https://...) اللي هيفتح اللعبة أو صفحتها")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_game_link(self, interaction: discord.Interaction, link: str):
        lang = get_lang(interaction.guild_id)
        if not (link.startswith("http://") or link.startswith("https://")):
            await interaction.response.send_message(t("gamelink_bad_url", lang), ephemeral=True)
            return
        set_game_link(interaction.guild_id, link)
        await interaction.response.send_message(
            t("gamelink_set_confirm", lang, link=link), ephemeral=True
        )

    @set_game_link.error
    async def set_game_link_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("gamelink_admin_only", lang), ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)

    @app_commands.command(name="game_link", description="📲 اعرض رابط فتح اللعبة المضبوط حالياً لهذا السيرفر")
    async def game_link(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        link = get_game_link(interaction.guild_id)
        await interaction.response.send_message(t("gamelink_current", lang, link=link), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsCog(bot))
