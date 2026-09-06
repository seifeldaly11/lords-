"""
Lords Mobile Companion Bot
بوت ديسكورد متكامل خاص بلعبة Lords Mobile.

طريقة التشغيل:
    1) ثبّت المتطلبات: pip install -r requirements.txt
    2) انسخ .env.example إلى .env وحط توكن البوت جواه.
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

# Replit Secret name is DISCORD_BOT_TOKEN. Keep DISCORD_TOKEN as a
# backwards-compatible fallback for older .env files.
TOKEN = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("lordsbot")

intents = discord.Intents.default()
intents.members = True  # مطلوب عشان نقدر نعمل mention/DM لأعضاء التحالف
intents.message_content = True  # مطلوب عشان البوت يرد على @mention برسائل وصور

bot = commands.Bot(command_prefix="!lm-unused!", intents=intents, help_command=None)

INITIAL_EXTENSIONS = [
    "cogs.settings_cog",  # /language - يفضّل يتحمّل بدري عشان الأوامر التانية تلاقي التفضيل جاهز
    "cogs.setup_cog",  # /setup - دليل التثبيت السريع للجدد (لغة/قناة صيد/رتبة قيادة بضغطة زر)
    "cogs.help_cog",  # /help - دليل الأوامر الكامل
    "cogs.events_cog",
    "cogs.jewel_calc_cog",  # حاسبة دمج الجواهر /jewel_calc
    "cogs.shield_cog",  # منبه الدرع الذكي /shield و/voice_rescue (يحتاج PyNaCl مثبتة عشان الصوت)
    "cogs.war_cog",
    "cogs.guides_cog",
    "cogs.wiki_cog",
    "cogs.intel_cog",
    "cogs.guild_cog",  # لازم يتحمّل قبل ai_cog وgames_cog عشان get_rank/gf group يكونوا جاهزين
    "cogs.hunt_cog",  # متتبع الصيد اليومي /hunt_log و/hunt_channel و/hunt_list
    "cogs.games_cog",
    "cogs.rally_cog",
    "cogs.market_cog",
    "cogs.ai_cog",
]


@bot.event
async def on_message(message: discord.Message):
    """يرد على منشن البوت بنفس مستشار Cohere، مع دعم الصور المرفقة."""
    if message.author.bot:
        return

    if bot.user is None or bot.user not in message.mentions:
        await bot.process_commands(message)
        return

    # الاستيراد وقت الطلب يمنع تسجيل أوامر /gf مرتين أثناء تحميل الـ cogs.
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
    lang = get_lang(message.guild.id if message.guild else None)

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
            "⚠️ حصل خطأ أثناء معالجة السؤال. جرّب تاني بعد شوية.",
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )


@bot.event
async def on_ready():
    log.info(f"✅ سجّل الدخول باسم: {bot.user} (ID: {bot.user.id})")
    try:
        log.info(f"📋 عدد الأوامر قبل المزامنة: {len(bot.tree.get_commands())} | GUILD_ID مضبوط: {bool(GUILD_ID)}")
        if GUILD_ID:
            guild_obj = discord.Object(id=int(GUILD_ID))
            # Commands are defined globally; copy them to the target guild
            # before syncing so they appear immediately for testing.
            bot.tree.copy_global_to(guild=guild_obj)
            synced = await bot.tree.sync(guild=guild_obj)
            log.info(f"🔄 تمت مزامنة {len(synced)} أمر على السيرفر المحدد (GUILD_ID).")
        else:
            synced = await bot.tree.sync()
            log.info(f"🔄 تمت مزامنة {len(synced)} أمر عالمياً (قد تستغرق حتى ساعة للظهور).")
    except Exception as e:
        log.error(f"فشلت مزامنة الأوامر: {e}")

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="Lords Mobile ⚔️ /event")
    )


async def main():
    if not TOKEN:
        raise SystemExit(
            "❌ لم يتم العثور على DISCORD_BOT_TOKEN. أضف Discord Bot Token إلى Secrets."
        )

    async with bot:
        for ext in INITIAL_EXTENSIONS:
            try:
                await bot.load_extension(ext)
                log.info(f"📦 تم تحميل: {ext}")
            except Exception as e:
                log.error(f"❌ فشل تحميل {ext}: {e}")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
