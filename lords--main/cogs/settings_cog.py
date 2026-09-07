"""
/language server - يضبط لغة واجهة البوت على مستوى السيرفر.
/language me - يضبط لغة ردود البوت لعضو واحد فقط.
"""
import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang, set_lang, set_user_lang, t
from utils.storage import get_game_link, set_game_link


language_group = app_commands.Group(
    name="language",
    description="🌐 إعداد لغة ردود البوت | Configure bot reply language",
)


LANGUAGE_CHOICES = [
    app_commands.Choice(name="🇪🇬 العربية", value="ar"),
    app_commands.Choice(name="🇬🇧 English", value="en"),
]


@language_group.command(
    name="server",
    description="🌐 اختر لغة البوت لكل السيرفر (للمشرفين) | Set the server bot language",
)
@app_commands.describe(lang="اختر اللغة | Choose language")
@app_commands.choices(lang=LANGUAGE_CHOICES)
@app_commands.checks.has_permissions(manage_guild=True)
async def language_server(interaction: discord.Interaction, lang: app_commands.Choice[str]):
    set_lang(interaction.guild_id, lang.value)
    key = "lang_set_ar_full" if lang.value == "ar" else "lang_set_en_full"
    await interaction.response.send_message(t(key, lang.value), ephemeral=True)


@language_server.error
async def language_server_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    current = get_lang(interaction.guild_id, interaction.user.id)
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(t("lang_admin_only", current), ephemeral=True)
    else:
        await interaction.response.send_message(t("unexpected_error", current), ephemeral=True)


async def _set_personal_language(interaction: discord.Interaction, lang: app_commands.Choice[str]):
    set_user_lang(interaction.user.id, lang.value)
    await interaction.response.send_message(t("lang_me_set", lang.value), ephemeral=True)


@language_group.command(
    name="me",
    description="🌐 اختر لغة ردود البوت لك أنت | Choose your personal bot reply language",
)
@app_commands.describe(lang="اختر اللغة | Choose language")
@app_commands.choices(lang=LANGUAGE_CHOICES)
async def language_me(interaction: discord.Interaction, lang: app_commands.Choice[str]):
    await _set_personal_language(interaction, lang)


@app_commands.command(
    name="languageme",
    description="🌐 اختصار لاختيار لغة ردود البوت لك | Shortcut for your personal bot language",
)
@app_commands.describe(lang="اختر اللغة | Choose language")
@app_commands.choices(lang=LANGUAGE_CHOICES)
async def languageme(interaction: discord.Interaction, lang: app_commands.Choice[str]):
    await _set_personal_language(interaction, lang)


class SettingsCog(commands.Cog):
    """إعدادات السيرفر وروابط اللعبة."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="set_game_link",
        description="📲 (إدارة) اضبط رابط فتح اللعبة (Deep Link) المستخدم في أزرار التنبيهات السريعة",
    )
    @app_commands.describe(link="الرابط الكامل (https://...) اللي هيفتح اللعبة أو صفحتها")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_game_link(self, interaction: discord.Interaction, link: str):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if not (link.startswith("http://") or link.startswith("https://")):
            await interaction.response.send_message(t("gamelink_bad_url", lang), ephemeral=True)
            return
        set_game_link(interaction.guild_id, link)
        await interaction.response.send_message(
            t("gamelink_set_confirm", lang, link=link), ephemeral=True
        )

    @set_game_link.error
    async def set_game_link_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("gamelink_admin_only", lang), ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)

    @app_commands.command(name="game_link", description="📲 اعرض رابط فتح اللعبة المضبوط حالياً لهذا السيرفر")
    async def game_link(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        link = get_game_link(interaction.guild_id)
        await interaction.response.send_message(t("gamelink_current", lang, link=link), ephemeral=True)


async def setup(bot: commands.Bot):
    bot.tree.add_command(language_group)
    bot.tree.add_command(languageme)
    await bot.add_cog(SettingsCog(bot))
