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

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("lordsbot")

intents = discord.Intents.default()
intents.members = True  # مطلوب عشان نقدر نعمل mention/DM لأعضاء التحالف
intents.message_content = False  # البوت بيعتمد بالكامل على Slash Commands

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
async def on_ready():
    log.info(f"✅ سجّل الدخول باسم: {bot.user} (ID: {bot.user.id})")
    try:
        if GUILD_ID:
            guild_obj = discord.Object(id=int(GUILD_ID))
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
            "❌ لم يتم العثور على DISCORD_TOKEN. تأكد من إنشاء ملف .env بناءً على .env.example"
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
