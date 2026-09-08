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

bot = commands.Bot(command_prefix="!lm-unused!", intents=intents, help_command=None)

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
    log.info(f"✅ سجّل الدخول باسم: {bot.user} (ID: {bot.user.id})")
    try:
        log.info(
            f"📋 عدد الأوامر قبل المزامنة: {len(bot.tree.get_commands())} | "
            f"GUILD_ID مضبوط: {bool(GUILD_ID)}"
        )
        if GUILD_ID:
            guild_obj = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild_obj)
            synced = await bot.tree.sync(guild=guild_obj)
            log.info(f"🔄 تمت مزامنة {len(synced)} أمر على السيرفر المحدد (GUILD_ID).")
        else:
            synced = await bot.tree.sync()
            log.info(f"🔄 تمت مزامنة {len(synced)} أمر عالمياً.")

            # استبدال أوامر السيرفر القديمة فوراً. هذا يمسح أوامر مثل
            # /dict و /heroes إذا لم تعد موجودة في النسخة الحالية.
            for guild in bot.guilds:
                bot.tree.clear_commands(guild=guild)
                bot.tree.copy_global_to(guild=guild)
                guild_synced = await bot.tree.sync(guild=guild)
                log.info(f"🔄 تمت مزامنة {len(guild_synced)} أمر على {guild.name}.")
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
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())