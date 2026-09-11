"""
/language server - يضبط لغة واجهة البوت على مستوى السيرفر.
/language me - يضبط لغة ردود البوت لعضو واحد فقط.
/bot_channel - يحدد القناة أو الثريد اللي البوت هيتواصل فيه (حسب اختيار الإدارة).
"""
from typing import Union

import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang, set_lang, set_user_lang, t
from utils.storage import set_bot_channel_id


language_group = app_commands.Group(
    name="language",
    description="🌐 إعداد لغة ردود البوت | Configure bot reply language"
)


LANGUAGE_CHOICES = [
    app_commands.Choice(name="🇪🇬 العربية", value="ar"),
    app_commands.Choice(name="🇬🇧 English", value="en"),
]


@language_group.command(
    name="server",
    description="🌐 اختر لغة البوت لكل السيرفر (للمشرفين) | Set the server bot language"
)
@app_commands.describe(lang="Language")
@app_commands.choices(lang=LANGUAGE_CHOICES)
@app_commands.checks.has_permissions(manage_guild=True)
async def language_server(interaction: discord.Interaction, lang: app_commands.Choice[str]):
    set_lang(interaction.guild_id, lang.value)
    key = "lang_set_ar_full" if lang.value == "ar" else "lang_set_en_full"
    await interaction.response.send_message(t(key, lang.value), ephemeral=False)


@language_server.error
async def language_server_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    current = get_lang(interaction.guild_id, interaction.user.id)
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(t("lang_admin_only", current), ephemeral=False)
    else:
        await interaction.response.send_message(t("unexpected_error", current), ephemeral=False)


async def _set_personal_language(interaction: discord.Interaction, lang: app_commands.Choice[str]):
    set_user_lang(interaction.user.id, lang.value)
    await interaction.response.send_message(t("lang_me_set", lang.value), ephemeral=False)


@language_group.command(
    name="me",
    description="🌐 اختر لغة ردود البوت لك أنت | Choose your personal bot reply language"
)
@app_commands.describe(lang="Language")
@app_commands.choices(lang=LANGUAGE_CHOICES)
async def language_me(interaction: discord.Interaction, lang: app_commands.Choice[str]):
    await _set_personal_language(interaction, lang)


@app_commands.command(
    name="languageme",
    description="🌐 اختصار لاختيار لغة ردود البوت لك | Shortcut for your personal bot language"
)
@app_commands.describe(lang="Language")
@app_commands.choices(lang=LANGUAGE_CHOICES)
async def languageme(interaction: discord.Interaction, lang: app_commands.Choice[str]):
    await _set_personal_language(interaction, lang)


@app_commands.command(
    name="bot_channel",
    description="📍 حدد القناة أو الثريد اللي البوت يتواصل فيه (إدارة فقط) | Set the channel/thread the bot talks in"
)
@app_commands.describe(channel="Channel or thread")
@app_commands.checks.has_permissions(manage_guild=True)
async def bot_channel(
    interaction: discord.Interaction,
    channel: Union[discord.TextChannel, discord.Thread]
):
    lang = get_lang(interaction.guild_id, interaction.user.id)
    set_bot_channel_id(interaction.guild_id, channel.id)
    await interaction.response.send_message(
        t("bot_channel_success", lang, channel=channel.mention), ephemeral=False
    )


@bot_channel.error
async def bot_channel_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    lang = get_lang(interaction.guild_id, interaction.user.id)
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(t("bot_channel_admin_only", lang), ephemeral=False)
    else:
        await interaction.response.send_message(t("bot_channel_error", lang), ephemeral=False)


class SettingsCog(commands.Cog):
    """إعدادات السيرفر."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot):
    bot.tree.add_command(language_group)
    bot.tree.add_command(languageme)
    bot.tree.add_command(bot_channel)
    await bot.add_cog(SettingsCog(bot))
