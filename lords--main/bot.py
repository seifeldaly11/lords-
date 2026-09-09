"""
Lords Mobile Companion Bot
بوت ديسكورد متكامل خاص بلعبة Lords Mobile.

طريقة التشغيل:
    1) ثبّت المتطلبات: pip install -r requirements.txt
    2) ضع التوكن في Secret باسم DISCORD_BOT_TOKEN.
    3) شغّل: python bot.py
"""
import asyncio
import logging
import os
import re

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("lordsbot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def apply_english_command_descriptions() -> None:
    """Keep Discord's slash-command metadata permanently in English."""
    from cogs.help_cog import ENGLISH_COMMAND_DESCRIPTIONS

    def walk(command_list, prefix: str = ""):
        for command in command_list:
            path = f"{prefix} {command.name}".strip()
            description = ENGLISH_COMMAND_DESCRIPTIONS.get(path)
            if description is None:
                description = ENGLISH_COMMAND_DESCRIPTIONS.get(command.name)
            if description is None:
                description = f"Open the /{path.replace(' ', ' ') } feature and follow its prompts."
            command.description = description[:100]
            if isinstance(command, app_commands.Group):
                walk(command.commands, path)

    walk(bot.tree.get_commands())

INITIAL_EXTENSIONS = [
    "cogs.components_cog",
    "cogs.settings_cog",
    "cogs.setup_cog",
    "cogs.help_cog",
    "cogs.events_cog",
    "cogs.shield_cog",
    "cogs.war_cog",
    "cogs.guides_cog",
    "cogs.guild_cog",
    "cogs.hunt_cog",
    "cogs.rally_cog",
    "cogs.market_cog",
    "cogs.ai_cog",
    "cogs.intel_cog",
    "cogs.welcome_cog",
]


@bot.event
async def on_message(message: discord.Message):
    """يرد على منشن البوت بنفس مستشار Cohere، مع دعم الصور المرفقة."""
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        components_cog = bot.get_cog("ComponentsCog")
        if components_cog is not None:
            await components_cog.send_test_message(message.channel)
        return

    if bot.user is None or bot.user not in message.mentions:
        await bot.process_commands(message)
        return

    from cogs.ai_cog import ask_ai
    from utils.i18n import get_lang, t

    mention_pattern = rf"<@!?{bot.user.id}>"
    prompt = re.sub(mention_pattern, "", message.content).strip()

    image = next(
        (
            attachment
            for attachment in message.attachments
            if (attachment.content_type or "").lower().startswith("image/")
            or attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
        ),
        None,
    )
    lang = get_lang(message.guild.id if message.guild else None, message.author.id)

    if not prompt and image is None:
        await message.reply(
            t("ai_need_input", lang),
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return

    try:
        async with message.channel.typing():
            answer = await ask_ai(
                prompt,
                image_url=image.url if image else None,
                lang=lang,
                guild_id=message.guild.id if message.guild else None,
            )
        await message.reply(
            answer[:1900],
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except Exception:
        log.exception("فشل رد AI على منشن من %s", message.author)
        await message.reply(
            t("ai_mention_error", lang),
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )


@bot.event
async def on_ready():
    apply_english_command_descriptions()
    log.info(f"✅ سجّل الدخول باسم: {bot.user} (ID: {bot.user.id})")
    try:
        log.info(
            f"📋 عدد الأوامر قبل المزامنة: {len(bot.tree.get_commands())} | "
            f"GUILD_ID مضبوط: {bool(GUILD_ID)}"
        )
        if GUILD_ID:
            # وضع التطوير: أوامر Guild فقط، مع مسح النسخة العالمية القديمة حتى
            # لا يظهر الأمر مرتين (نسخة Global + نسخة Guild).
            guild_obj = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild_obj)
            synced = await bot.tree.sync(guild=guild_obj)
            bot.tree.clear_commands(guild=None)
            await bot.tree.sync()
            log.info(f"🔄 تمت مزامنة {len(synced)} أمر على السيرفر المحدد (GUILD_ID).")
        else:
            # وضع البيع/الإنتاج: نسخة Global واحدة فقط. الأوامر القديمة التي
            # كانت Guild-scoped تُمسح بإرسال قائمة فارغة، بدون نسخ الأوامر
            # العالمية إليها مرة ثانية؛ النسخ كان سبب ظهور /ai وغيره مرتين.
            synced = await bot.tree.sync()
            log.info(f"🔄 تمت مزامنة {len(synced)} أمر عالمياً.")
            for guild in bot.guilds:
                bot.tree.clear_commands(guild=guild)
                guild_synced = await bot.tree.sync(guild=guild)
                log.info(f"🧹 تم تنظيف أوامر Guild القديمة في {guild.name} ({len(guild_synced)} متبقي).")
    except Exception as e:
        log.error(f"فشلت مزامنة الأوامر: {e}")

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="Lords Mobile ⚔️ /event")
    )


async def main():
    if not TOKEN:
        raise SystemExit("❌ لم يتم العثور على DISCORD_BOT_TOKEN. أضفه إلى Secrets.")

    async with bot:
        for ext in INITIAL_EXTENSIONS:
            try:
                await bot.load_extension(ext)
                log.info(f"📦 تم تحميل: {ext}")
            except Exception:
                log.exception(f"❌ فشل تحميل {ext}")
        apply_english_command_descriptions()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())