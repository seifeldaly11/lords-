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
            if description is not None:
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
    "cogs.war_cog",
    "cogs.guides_cog",
    "cogs.guild_cog",
    "cogs.hunt_cog",
    "cogs.rally_cog",
    "cogs.market_cog",
    "cogs.shop_cog",
    "cogs.ai_cog",
    "cogs.intel_cog",
    "cogs.welcome_cog",
    "cogs.subscription_cog",
    "cogs.replies_cog",
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



@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "⚠️ **عذراً، هذا الأمر مخصص لإدارة السيرفر فقط.**"
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ يرجى الانتظار {error.retry_after:.1f} ثانية قبل إعادة استخدام هذا الأمر."
    elif isinstance(error, app_commands.CheckFailure):
        msg = "🔒 **ليس لديك الصلاحية لتنفيذ هذا الأمر أو أن اشتراك السيرفر منتهي.**"
    else:
        log.error(f"خطأ غير متوقع في الأمر {interaction.command}: {error}")
        msg = "⚠️ حدث خطأ أثناء تنفيذ الأمر، يرجى المحاولة لاحقاً."
    
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=False)
        else:
            await interaction.response.send_message(msg, ephemeral=False)
    except Exception:
        pass

@bot.event
async def on_guild_join(guild: discord.Guild):
    """Notify admins and welcome members when the bot is invited to a guild."""
    from cogs.subscription_cog import SUBSCRIPTION_ADMIN_IDS, get_subscription

    owner_text = f"غير معروف (ID: {guild.owner_id})"
    if guild.owner is not None:
        owner_text = f"{guild.owner} (ID: {guild.owner_id})"

    inviter_text = "غير متاح؛ لا توجد صلاحية لسجل التدقيق"
    try:
        me = guild.me
        if me is not None and me.guild_permissions.view_audit_log:
            async for entry in guild.audit_logs(limit=25, action=discord.AuditLogAction.bot_add):
                target_id = getattr(entry.target, "id", None)
                if bot.user is not None and target_id == bot.user.id:
                    inviter_text = f"{entry.user} (ID: {entry.user.id})"
                    break
    except (discord.Forbidden, discord.HTTPException):
        pass

    expires_at = get_subscription(str(guild.id))
    if expires_at:
        subscription_text = f"✅ اشتراك مسجل حتى {expires_at}"
        welcome_color = discord.Color.green()
        welcome_description = "تمت إضافتي إلى هذا السيرفر. الاشتراك مسجل ويمكن استخدام أوامر البوت حسب صلاحيته."
    else:
        subscription_text = "❌ لا يوجد اشتراك مسجل"
        welcome_color = discord.Color.orange()
        welcome_description = "تمت إضافتي إلى هذا السيرفر، لكن لا يوجد اشتراك فعال حالياً. مالك السيرفر يمكنه استخدام /redeem لتفعيل كود اشتراك."

    welcome_embed = discord.Embed(
        title="🤖 تم إضافة LordsMobile إلى السيرفر",
        description=welcome_description,
        color=welcome_color
    )
    welcome_embed.add_field(name="🆔 Server ID", value=str(guild.id), inline=False)
    welcome_embed.add_field(name="📅 حالة الاشتراك", value=subscription_text, inline=False)
    welcome_embed.set_footer(text="للمساعدة استخدم /help")

    welcome_channel = guild.system_channel
    if welcome_channel is None or guild.me is None or not welcome_channel.permissions_for(guild.me).send_messages:
        welcome_channel = next((channel for channel in guild.text_channels if guild.me and channel.permissions_for(guild.me).send_messages), None)
    if welcome_channel is not None:
        try:
            await welcome_channel.send(embed=welcome_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    admin_embed = discord.Embed(
        title="🚨 دخل البوت إلى سيرفر جديد",
        description="تمت إضافة البوت إلى سيرفر جديد. استخدم /قائمة_السيرفرات لرؤية كل السيرفرات أو /طرد_البوت لإخراجه.",
        color=discord.Color.blurple()
    )
    admin_embed.add_field(name="🏰 السيرفر", value=f"{guild.name}\nID: {guild.id}", inline=False)
    admin_embed.add_field(name="👑 المالك", value=owner_text, inline=False)
    admin_embed.add_field(name="📨 الداعي", value=inviter_text, inline=False)
    admin_embed.add_field(name="👥 الأعضاء", value=str(guild.member_count or 0), inline=True)
    admin_embed.add_field(name="📅 الاشتراك", value=subscription_text, inline=False)

    log.info("دخل البوت سيرفراً جديداً: %s (%s)", guild.name, guild.id)
    for admin_id in SUBSCRIPTION_ADMIN_IDS:
        try:
            admin = bot.get_user(admin_id) or await bot.fetch_user(admin_id)
            await admin.send(embed=admin_embed)
        except (discord.Forbidden, discord.HTTPException):
            log.warning("تعذر إرسال إشعار دخول السيرفر إلى مدير الاشتراكات %s", admin_id)

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




@bot.command(name="sync")
async def sync_now(ctx: commands.Context):
    """أمر فوري لمالك البوت لمزامنة الأوامر على هذا السيرفر فوراً في ثانية واحدة."""
    owner_id_env = os.getenv("OWNER_ID")
    owner_id = int(owner_id_env) if owner_id_env and owner_id_env.isdigit() else 1527765325221990521
    if ctx.author.id != owner_id:
        return
    msg = await ctx.send("⏳ جاري مزامنة 68 أمر فورياً على هذا السيرفر...")
    bot.tree.copy_global_to(guild=ctx.guild)
    synced = await bot.tree.sync(guild=ctx.guild)
    await msg.edit(content=f"⚡ **تمت المزامنة الفورية!** أصبح لديك الآن **{len(synced)} أمر** متاح ومباشر في هذا السيرفر دون انتظار كاش ديسكورد.")


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