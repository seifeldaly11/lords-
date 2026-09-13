# -*- coding: utf-8 -*-
"""
وحدة إدارة وتجديد اشتراكات السيرفرات (Subscription Cog)
=========================================================
- تم تحويلها للعمل كوحدة (Cog) داخل بوت لوردس
- تستخدم discord.py (Slash Commands & Tasks)
- تستخدم SQLite لتخزين الاشتراكات والأكواد والملاحظات
- أوامر إدارة الاشتراكات مقفلة على مديري الاشتراكات المحددين فقط
- أمر /redeem متاح لأصحاب السيرفرات لتفعيل كود التجديد
"""

import os
import sqlite3
import random
import string
import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks

def _parse_int(val, default: int) -> int:
    if val is None:
        return default
    s = str(val).strip()
    if not s:
        return default
    try:
        return int(s)
    except (ValueError, TypeError):
        return default

SUBSCRIPTION_ADMIN_IDS = frozenset({
    1527692596598804565,
    1527765325221990521,
})
CONTACT_USERNAME = (os.getenv("CONTACT_USERNAME") or "seifeldaly124").strip()
CONTACT_LINE = f"للتجديد يرجى التواصل مع: **{CONTACT_USERNAME}**"
GRACE_PERIOD_DAYS = _parse_int(os.getenv("GRACE_PERIOD_DAYS"), 3)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "storage", "subscriptions.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=60.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 60000;")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            server_id TEXT PRIMARY KEY,
            expires_at TEXT NOT NULL,
            warned_1h INTEGER NOT NULL DEFAULT 0,
            expired_notified INTEGER NOT NULL DEFAULT 0
        )
    """)

    for column_def in ("warned_1h INTEGER NOT NULL DEFAULT 0", "expired_notified INTEGER NOT NULL DEFAULT 0"):
        try:
            cur.execute(f"ALTER TABLE subscriptions ADD COLUMN {column_def}")
        except sqlite3.OperationalError:
            pass

    cur.execute("""
        CREATE TABLE IF NOT EXISTS codes (
            code TEXT PRIMARY KEY,
            days INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id TEXT NOT NULL,
            note_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    clean_invalid_subscriptions()
    conn.commit()
    conn.close()


def is_owner(user_id: int) -> bool:
    return user_id in SUBSCRIPTION_ADMIN_IDS


def is_server_owner_or_bot_owner(interaction: discord.Interaction) -> bool:
    if is_owner(interaction.user.id):
        return True
    if interaction.guild is not None and interaction.user.id == interaction.guild.owner_id:
        return True
    return False


async def deny_if_not_owner(interaction: discord.Interaction) -> bool:
    if not is_owner(interaction.user.id):
        await interaction.response.send_message(
            "🔒 هذا الأمر مخصص لمديري الاشتراكات فقط، لا تملك صلاحية استخدامه.",
            ephemeral=True
        )
        return True
    return False


def get_subscription(server_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT expires_at FROM subscriptions WHERE server_id = ?", (server_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def set_subscription(server_id: str, days: int):
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).isoformat()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO subscriptions (server_id, expires_at, warned_1h, expired_notified)
        VALUES (?, ?, 0, 0)
        ON CONFLICT(server_id) DO UPDATE SET expires_at = excluded.expires_at, warned_1h = 0, expired_notified = 0
    """, (server_id, expires_at))
    conn.commit()
    conn.close()
    return expires_at


def renew_subscription(server_id: str, days: int):
    current = get_subscription(server_id)
    if current:
        current_date = datetime.datetime.fromisoformat(current)
        base_date = max(current_date, datetime.datetime.utcnow())
        new_date = base_date + datetime.timedelta(days=days)
    else:
        new_date = datetime.datetime.utcnow() + datetime.timedelta(days=days)

    expires_at = new_date.isoformat()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO subscriptions (server_id, expires_at, warned_1h, expired_notified)
        VALUES (?, ?, 0, 0)
        ON CONFLICT(server_id) DO UPDATE SET expires_at = excluded.expires_at, warned_1h = 0, expired_notified = 0
    """, (server_id, expires_at))
    conn.commit()
    conn.close()
    return expires_at


def is_valid_server_id(value) -> bool:
    """يتأكد أن آيدي السيرفر رقم صحيح / Ensure server id is numeric."""
    return str(value).strip().isdigit()


def clean_invalid_subscriptions():
    """يحذف أي سجلات اشتراك أو ملاحظات آيدي السيرفر فيها نص غير رقمي."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT server_id FROM subscriptions")
    bad = [r[0] for r in cur.fetchall() if not str(r[0]).strip().isdigit()]
    for sid in bad:
        cur.execute("DELETE FROM subscriptions WHERE server_id = ?", (sid,))
    conn.commit()
    conn.close()
    return bad


def delete_subscription(server_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM subscriptions WHERE server_id = ?", (server_id,))
    conn.commit()
    conn.close()


def generate_unique_code(days: int) -> str:
    conn = get_connection()
    cur = conn.cursor()

    while True:
        part1 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        part2 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        code = f"SUB-{part1}-{part2}"

        cur.execute("SELECT 1 FROM codes WHERE code = ?", (code,))
        if not cur.fetchone():
            break

    cur.execute("INSERT INTO codes (code, days) VALUES (?, ?)", (code, days))
    conn.commit()
    conn.close()
    return code


def redeem_code_from_db(code: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT days FROM codes WHERE code = ?", (code,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    days = row[0]
    cur.execute("DELETE FROM codes WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return days


def add_note_to_db(server_id: str, note_text: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO notes (server_id, note_text, created_at) VALUES (?, ?, ?)",
        (server_id, note_text, datetime.datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_notes_from_db(server_id: str = None):
    conn = get_connection()
    cur = conn.cursor()
    if server_id:
        cur.execute(
            "SELECT id, server_id, note_text, created_at FROM notes WHERE server_id = ? ORDER BY id DESC LIMIT 25",
            (server_id,)
        )
    else:
        cur.execute(
            "SELECT id, server_id, note_text, created_at FROM notes ORDER BY id DESC LIMIT 25"
        )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_note_by_id(note_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, server_id, note_text, created_at FROM notes WHERE id = ?",
        (note_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def delete_note_from_db(note_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


async def get_guild_owner(bot: commands.Bot, guild: discord.Guild) -> discord.User | None:
    try:
        return guild.owner or await bot.fetch_user(guild.owner_id)
    except Exception:
        return None


async def send_expiry_warning(bot: commands.Bot, guild: discord.Guild):
    owner = await get_guild_owner(bot, guild)
    if owner is None:
        return
    try:
        msg = f"⚠️ تنبيه: سينتهي اشتراك سيرفرك **{guild.name}** خلال ساعة تقريباً.\nيرجى تجديد الاشتراك قبل توقف البوت في السيرفر.\n{CONTACT_LINE}"
        await owner.send(msg)
    except discord.Forbidden:
        pass


async def notify_and_leave(bot: commands.Bot, guild: discord.Guild):
    channel = guild.system_channel
    if channel is None:
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                channel = ch
                break

    if channel is not None:
        try:
            await channel.send(f"⚠️ انتهت مدة اشتراك هذا السيرفر، وتم إيقاف البوت.\n{CONTACT_LINE}")
        except discord.Forbidden:
            pass

    owner = await get_guild_owner(bot, guild)
    if owner is not None:
        try:
            await owner.send(f"❌ انتهى اشتراك سيرفرك **{guild.name}**.\nتم إيقاف البوت في هذا السيرفر حتى يتم دفع الاشتراك الجديد.\n{CONTACT_LINE}")
        except discord.Forbidden:
            pass

    await guild.leave()


async def send_expiry_notice(bot: commands.Bot, guild: discord.Guild):
    channel = guild.system_channel
    if channel is None:
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                channel = ch
                break

    grace_note = f"سيغادر البوت هذا السيرفر تلقائياً خلال {GRACE_PERIOD_DAYS} يوم إذا لم يتم التجديد."

    if channel is not None:
        try:
            await channel.send(f"⚠️ انتهت مدة اشتراك هذا السيرفر، وتم إيقاف أوامر البوت الآن.\n{grace_note}\n{CONTACT_LINE}")
        except discord.Forbidden:
            pass

    owner = await get_guild_owner(bot, guild)
    if owner is not None:
        try:
            await owner.send(f"❌ انتهى اشتراك سيرفرك **{guild.name}**، وتم إيقاف البوت فيه الآن.\n{grace_note}\nيمكنك تفعيل كود جديد عبر /redeem داخل السيرفر في أي وقت خلال المهلة.\n{CONTACT_LINE}")
        except discord.Forbidden:
            pass


async def leave_after_grace(bot: commands.Bot, guild: discord.Guild):
    channel = guild.system_channel
    if channel is None:
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                channel = ch
                break

    if channel is not None:
        try:
            await channel.send(f"👋 انتهت مهلة السماح ({GRACE_PERIOD_DAYS} يوم) دون تجديد الاشتراك، والبوت يغادر السيرفر الآن.\n{CONTACT_LINE}")
        except discord.Forbidden:
            pass

    owner = await get_guild_owner(bot, guild)
    if owner is not None:
        try:
            await owner.send(f"👋 لم يتم تجديد اشتراك سيرفرك **{guild.name}** خلال مهلة السماح، وتمت مغادرة البوت له.\nيمكنك إعادة دعوة البوت وتفعيل كود عبر /redeem في أي وقت.\n{CONTACT_LINE}")
        except discord.Forbidden:
            pass

    await guild.leave()


async def global_subscription_check(interaction: discord.Interaction) -> bool:
    if is_owner(interaction.user.id):
        return True

    if interaction.command is not None and interaction.command.name == "redeem":
        return True

    if interaction.guild is None:
        return True

    expires_at = get_subscription(str(interaction.guild.id))
    is_active = expires_at is not None and datetime.datetime.fromisoformat(expires_at) > datetime.datetime.utcnow()

    if not is_active:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"🔒 البوت مغلق حتى دفع الاشتراك الجديد.\n{CONTACT_LINE}",
                ephemeral=True
            )
        return False

    return True



class NoteViewSelect(discord.ui.Select):
    def __init__(self, notes):
        options = []
        for row in notes[:25]:
            note_id, sid, text, created = row[0], row[1], row[2], row[3]
            preview = text[:45].strip().replace("\n", " ")
            try:
                date_str = datetime.datetime.fromisoformat(created).strftime('%m-%d %H:%M')
            except Exception:
                date_str = ""
            desc = f"سيرفر: {sid} | {date_str}"[:50]
            options.append(discord.SelectOption(
                label=f"#{note_id}: {preview}"[:100],
                value=str(note_id),
                description=desc,
                emoji="📝"
            ))
        super().__init__(placeholder="اختر ملاحظة من القائمة لعرض تفاصيلها...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("🔒 هذا الأمر مخصص لمالك البوت فقط.", ephemeral=True)
            return
        note_id = int(self.values[0])
        note = get_note_by_id(note_id)
        if not note:
            await interaction.response.send_message("⚠️ لم يتم العثور على الملاحظة، قد تكون حُذفت.", ephemeral=True)
            return
        
        nid, sid, text, created = note[0], note[1], note[2], note[3]
        try:
            date_str = datetime.datetime.fromisoformat(created).strftime('%Y-%m-%d %H:%M UTC')
        except Exception:
            date_str = created
        
        msg = (
            f"📌 **تفاصيل الملاحظة #{nid}:**\n"
            f"▫️ **آيدي السيرفر:** `{sid}`\n"
            f"▫️ **تاريخ التسجيل:** `{date_str}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"**نص الملاحظة:**\n{text}"
        )
        await interaction.response.send_message(msg, ephemeral=True)


class NoteViewUI(discord.ui.View):
    def __init__(self, notes):
        super().__init__(timeout=180)
        self.add_item(NoteViewSelect(notes))


class NoteDeleteSelect(discord.ui.Select):
    def __init__(self, notes):
        options = []
        for row in notes[:25]:
            note_id, sid, text, created = row[0], row[1], row[2], row[3]
            preview = text[:45].strip().replace("\n", " ")
            try:
                date_str = datetime.datetime.fromisoformat(created).strftime('%m-%d %H:%M')
            except Exception:
                date_str = ""
            desc = f"سيرفر: {sid} | {date_str}"[:50]
            options.append(discord.SelectOption(
                label=f"#{note_id}: {preview}"[:100],
                value=str(note_id),
                description=desc,
                emoji="🗑️"
            ))
        super().__init__(placeholder="اختر الملاحظة التي ترغب في مسحها نهائياً...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("🔒 هذا الأمر مخصص لمالك البوت فقط.", ephemeral=True)
            return
        note_id = int(self.values[0])
        note = get_note_by_id(note_id)
        preview_text = note[2][:50] if note else f"#{note_id}"
        
        success = delete_note_from_db(note_id)
        if success:
            await interaction.response.send_message(
                f"🗑️ **تم مسح الملاحظة بنجاح!**\n> {preview_text}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "⚠️ تعذر حذف الملاحظة أو أنها حُذفت مسبقاً.",
                ephemeral=True
            )


class NoteDeleteUI(discord.ui.View):
    def __init__(self, notes):
        super().__init__(timeout=180)
        self.add_item(NoteDeleteSelect(notes))


class SubscriptionCog(commands.Cog):
    """وحدة إدارة اشتراكات السيرفرات وأكواد التفعيل."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_db()
        self.check_subscriptions.start()

    def cog_unload(self):
        self.check_subscriptions.cancel()
        try:
            self.bot.tree.remove_check(global_subscription_check)
        except Exception:
            pass

    @tasks.loop(minutes=10)
    async def check_subscriptions(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT server_id, expires_at, warned_1h, expired_notified FROM subscriptions")
        rows = cur.fetchall()
        conn.close()

        now = datetime.datetime.utcnow()

        for server_id, expires_at, warned_1h, expired_notified in rows:
            if not is_valid_server_id(server_id):
                # سجل تالف (آيدي غير رقمي) - حذفه بدل ايقاف البوت
                delete_subscription(server_id)
                continue
            expiry_date = datetime.datetime.fromisoformat(expires_at)
            guild = self.bot.get_guild(int(server_id))

            if now >= expiry_date:
                grace_deadline = expiry_date + datetime.timedelta(days=GRACE_PERIOD_DAYS)

                if now >= grace_deadline:
                    if guild:
                        await leave_after_grace(self.bot, guild)
                    delete_subscription(server_id)
                    continue

                if expired_notified == 0:
                    if guild:
                        await send_expiry_notice(self.bot, guild)
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE subscriptions SET expired_notified = 1 WHERE server_id = ?", (server_id,))
                    conn.commit()
                    conn.close()
                continue

            remaining = expiry_date - now
            if warned_1h == 0 and remaining <= datetime.timedelta(hours=1):
                if guild:
                    await send_expiry_warning(self.bot, guild)
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("UPDATE subscriptions SET warned_1h = 1 WHERE server_id = ?", (server_id,))
                conn.commit()
                conn.close()

    @check_subscriptions.before_loop
    async def before_check_subscriptions(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="قائمة_السيرفرات", description="🔒 تقرير منظم عن كل السيرفرات وحالة الاشتراك")
    async def servers_list(self, interaction: discord.Interaction):
        if await deny_if_not_owner(interaction):
            return

        guilds = sorted(self.bot.guilds, key=lambda guild: guild.name.lower())
        if not guilds:
            await interaction.response.send_message("البوت لا ينتمي إلى أي سيرفر حالياً.", ephemeral=True)
            return

        now = datetime.datetime.utcnow()
        current_ids = {str(guild.id) for guild in guilds}
        active_count = 0
        inactive_count = 0
        embeds = []

        summary = discord.Embed(
            title="📡 حالة البوت في السيرفرات",
            description=f"البوت موجود حالياً في **{len(guilds)}** سيرفر. هذه القائمة توضح مكانه ومالك كل سيرفر وحالة الاشتراك.",
            color=discord.Color.blue()
        )

        for guild in guilds:
            owner = guild.owner
            if owner is None:
                try:
                    owner = await self.bot.fetch_user(guild.owner_id)
                except Exception:
                    owner = None
            owner_text = f"{owner}" if owner else "غير معروف"

            expires_at = get_subscription(str(guild.id))
            expiry_date = None
            if expires_at:
                try:
                    expiry_date = datetime.datetime.fromisoformat(expires_at)
                except (TypeError, ValueError):
                    expiry_date = None

            if expiry_date is None:
                inactive_count += 1
                subscription_text = "❌ لا يوجد اشتراك مسجل لهذا السيرفر"
                color = discord.Color.red()
            elif expiry_date > now:
                active_count += 1
                remaining_days = max((expiry_date - now).days, 0)
                subscription_text = f"✅ فعال حتى {expiry_date.strftime('%Y-%m-%d %H:%M UTC')} ({remaining_days} يوم متبقٍ)"
                color = discord.Color.green()
            else:
                inactive_count += 1
                subscription_text = f"⚠️ منتهي منذ {expiry_date.strftime('%Y-%m-%d %H:%M UTC')}"
                color = discord.Color.orange()

            server_embed = discord.Embed(
                title=f"🏰 {guild.name[:240]}",
                color=color
            )
            server_embed.add_field(name="🆔 Server ID", value=str(guild.id), inline=False)
            server_embed.add_field(name="👑 المالك / مستفيد الاشتراك", value=f"{owner_text}\nID: {guild.owner_id}", inline=False)
            server_embed.add_field(name="👥 الأعضاء", value=str(guild.member_count or 0), inline=True)
            server_embed.add_field(name="📅 الاشتراك", value=subscription_text, inline=False)
            server_embed.add_field(name="🚪 إخراج البوت", value=f"/طرد_البوت server_id: {guild.id}", inline=False)
            embeds.append(server_embed)

        summary.add_field(name="✅ اشتراك فعال", value=str(active_count), inline=True)
        summary.add_field(name="⚠️ بدون اشتراك / منتهي", value=str(inactive_count), inline=True)
        embeds.insert(0, summary)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT server_id, expires_at FROM subscriptions")
        stored_subscriptions = cur.fetchall()
        conn.close()
        missing = [(server_id, expires_at) for server_id, expires_at in stored_subscriptions if str(server_id) not in current_ids]
        if missing:
            missing_embed = discord.Embed(
                title="🗃️ اشتراكات مسجلة والبوت غير موجود في سيرفراتها",
                description="\n".join(f"• Server ID: {server_id} | ينتهي: {expires_at}" for server_id, expires_at in missing),
                color=discord.Color.dark_gray()
            )
            embeds.append(missing_embed)

        embed_chunks = [embeds[i:i + 5] for i in range(0, len(embeds), 5)]
        await interaction.response.send_message(embeds=embed_chunks[0], ephemeral=True)
        for chunk in embed_chunks[1:]:
            await interaction.followup.send(embeds=chunk, ephemeral=True)


    @app_commands.command(name="حالة_الاشتراكات", description="🔒 عرض حالة اشتراكات جميع السيرفرات المخزنة")
    async def subscriptions_status(self, interaction: discord.Interaction):
        if await deny_if_not_owner(interaction):
            return

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT server_id, expires_at FROM subscriptions")
        rows = cur.fetchall()
        conn.close()

        if not rows:
            await interaction.response.send_message("لا توجد اشتراكات مسجلة حالياً.", ephemeral=True)
            return

        now = datetime.datetime.utcnow()
        lines = []
        for server_id, expires_at in rows:
            expiry_date = datetime.datetime.fromisoformat(expires_at)
            remaining_days = (expiry_date - now).days
            guild = self.bot.get_guild(int(server_id)) if is_valid_server_id(server_id) else None
            guild_name = guild.name if guild else "غير معروف (البوت ليس فيه حالياً)"

            if expiry_date > now:
                status = "✅ فعّال"
                extra_line = f"› الأيام المتبقية: {remaining_days}\n"
            else:
                grace_deadline = expiry_date + datetime.timedelta(days=GRACE_PERIOD_DAYS)
                days_left_to_leave = max((grace_deadline - now).days, 0)
                status = "⏳ منتهي - ضمن مهلة السماح (الأوامر مقفلة)"
                extra_line = f"› سيغادر البوت خلال: {days_left_to_leave} يوم إذا لم يتم التجديد\n"

            lines.append(
                f"**{guild_name}** (`{server_id}`)\n› الحالة: {status}\n› تاريخ الانتهاء: {expiry_date.strftime('%Y-%m-%d %H:%M UTC')}\n{extra_line}"
            )

        text = "\n".join(lines)
        chunks = [text[i:i + 1900] for i in range(0, len(text), 1900)]

        await interaction.response.send_message(chunks[0], ephemeral=True)
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk, ephemeral=True)

    @app_commands.command(name="تحديد_اشتراك", description="🔒 تحديد اشتراك جديد لسيرفر معين")
    @app_commands.describe(server_id="آيدي السيرفر", days="عدد الأيام")
    async def set_subscription_cmd(self, interaction: discord.Interaction, server_id: str, days: int):
        if await deny_if_not_owner(interaction):
            return

        if days <= 0:
            await interaction.response.send_message("❌ عدد الأيام يجب أن يكون أكبر من صفر.", ephemeral=True)
            return

        server_id = str(server_id).strip()
        if not is_valid_server_id(server_id):
            await interaction.response.send_message("❌ آيدي السيرفر غير صحيح. يجب أن يكون رقماً فقط مثل: `123456789012345678`", ephemeral=True)
            return

        expires_at = set_subscription(server_id, days)
        expiry_date = datetime.datetime.fromisoformat(expires_at)
        await interaction.response.send_message(
            f"✅ تم تحديد اشتراك جديد للسيرفر `{server_id}` لمدة {days} يوم.\nينتهي في: {expiry_date.strftime('%Y-%m-%d %H:%M UTC')}",
            ephemeral=True
        )

    @app_commands.command(name="تجديد_اشتراك", description="🔒 تجديد (إضافة أيام) على اشتراك سيرفر معين")
    @app_commands.describe(server_id="آيدي السيرفر", days="عدد الأيام المضافة")
    async def renew_subscription_cmd(self, interaction: discord.Interaction, server_id: str, days: int):
        if await deny_if_not_owner(interaction):
            return

        if days <= 0:
            await interaction.response.send_message("❌ عدد الأيام يجب أن يكون أكبر من صفر.", ephemeral=True)
            return

        server_id = str(server_id).strip()
        if not is_valid_server_id(server_id):
            await interaction.response.send_message("❌ آيدي السيرفر غير صحيح. يجب أن يكون رقماً فقط مثل: `123456789012345678`", ephemeral=True)
            return

        expires_at = renew_subscription(server_id, days)
        expiry_date = datetime.datetime.fromisoformat(expires_at)
        await interaction.response.send_message(
            f"✅ تم تجديد اشتراك السيرفر `{server_id}` بإضافة {days} يوم.\nالاشتراك الآن ينتهي في: {expiry_date.strftime('%Y-%m-%d %H:%M UTC')}",
            ephemeral=True
        )

    @app_commands.command(name="ايقاف_اشتراك", description="🔒 إيقاف اشتراك سيرفر ومغادرته فوراً")
    @app_commands.describe(server_id="آيدي السيرفر")
    async def stop_subscription_cmd(self, interaction: discord.Interaction, server_id: str):
        if await deny_if_not_owner(interaction):
            return

        if not is_valid_server_id(server_id):
            await interaction.response.send_message("❌ آيدي السيرفر غير صحيح. يجب أن يكون رقماً فقط مثل: `123456789012345678`", ephemeral=True)
            return
        guild = self.bot.get_guild(int(server_id.strip()))
        delete_subscription(server_id.strip())

        if guild:
            await interaction.response.send_message(
                f"⏳ جاري إيقاف اشتراك السيرفر **{guild.name}** ومغادرته...", ephemeral=True
            )
            await notify_and_leave(self.bot, guild)
            await interaction.followup.send(f"✅ تم إيقاف الاشتراك ومغادرة السيرفر `{server_id}`.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"⚠️ تم حذف الاشتراك من قاعدة البيانات، لكن البوت غير موجود حالياً في السيرفر `{server_id}`.",
                ephemeral=True
            )

    @app_commands.command(name="انشاء_كود", description="🔒 توليد كود اشتراك جديد بعدد أيام محدد")
    @app_commands.describe(days="عدد الأيام التي يمنحها الكود")
    async def create_code_cmd(self, interaction: discord.Interaction, days: int):
        if await deny_if_not_owner(interaction):
            return

        if days <= 0:
            await interaction.response.send_message("❌ عدد الأيام يجب أن يكون أكبر من صفر.", ephemeral=True)
            return

        code = generate_unique_code(days)
        await interaction.response.send_message(
            f"✅ تم إنشاء الكود التالي بنجاح:\n`{code}`\nيمنح: {days} يوم",
            ephemeral=True
        )

    @app_commands.command(name="redeem", description="🔒 تفعيل كود اشتراك (متاح لصاحب السيرفر فقط)")
    @app_commands.describe(code="الكود المراد تفعيله")
    async def redeem_cmd(self, interaction: discord.Interaction, code: str):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("❌ هذا الأمر يعمل داخل السيرفرات فقط.", ephemeral=True)
            return

        if interaction.user.id != guild.owner_id and not is_owner(interaction.user.id):
            await interaction.response.send_message(
                "❌ هذا الأمر مخصص لمالك السيرفر فقط.", ephemeral=True
            )
            return

        code = (code or "").strip().upper()
        if not code:
            await interaction.response.send_message("❌ يجب إدخال كود صالح.", ephemeral=True)
            return

        days = redeem_code_from_db(code)
        if days is None:
            await interaction.response.send_message("❌ الكود غير صحيح أو تم استخدامه من قبل.", ephemeral=True)
            return

        expires_at = renew_subscription(str(guild.id), days)
        expiry_date = datetime.datetime.fromisoformat(expires_at)
        await interaction.response.send_message(
            f"✅ تم تفعيل الكود بنجاح! تمت إضافة {days} يوم لاشتراك هذا السيرفر.\nالاشتراك الآن ينتهي في: {expiry_date.strftime('%Y-%m-%d %H:%M UTC')}",
            ephemeral=True
        )

    @app_commands.command(name="اضافة_ملاحظة", description="🔒 إضافة ملاحظة بعنوان (عامة للبوت أو خاصة بسيرفر)")
    @app_commands.describe(
        title="عنوان الملاحظة الرئيسي",
        note_text="نص وتفاصيل الملاحظة",
        server_id="آيدي السيرفر (اختياري - اتركه فارغاً لملاحظة عامة عن البوت)"
    )
    async def add_note_cmd(self, interaction: discord.Interaction, title: str, note_text: str, server_id: str = None):
        if await deny_if_not_owner(interaction):
            return

        target_server_id = (server_id or "").strip() or "عام / General" 

        add_note_to_db(target_server_id, note_text)
        await interaction.response.send_message(
            f"✅ تم إضافة الملاحظة للسيرفر {target_server_id}.", ephemeral=True
        )


    @app_commands.command(name="عرض_الملاحظات", description="🔒 عرض قائمة بالملاحظات المسجلة واختيار إحداها")
    @app_commands.describe(server_id="آيدي السيرفر (اختياري - اتركه فارغاً لعرض كل الملاحظات)")
    async def view_notes_cmd(self, interaction: discord.Interaction, server_id: str = None):
        if await deny_if_not_owner(interaction):
            return

        notes = get_notes_from_db(server_id)
        if not notes:
            msg = f"لا توجد ملاحظات مسجلة للسيرفر `{server_id}`." if server_id else "لا توجد أي ملاحظات مسجلة حالياً."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        view = NoteViewUI(notes)
        count = len(notes)
        scope = f"للسيرفر `{server_id}`" if server_id else "(أحدث الملاحظات المسجلة)"
        await interaction.response.send_message(
            f"📋 **تم العثور على {count} ملاحظة {scope}:**\nاختر من القائمة المنسدلة أدناه للاطلاع على نص الملاحظة الكامل:",
            view=view,
            ephemeral=True
        )

    @app_commands.command(name="مسح_ملاحظة", description="🔒 مسح ملاحظة مسجلة باختيارها من القائمة")
    @app_commands.describe(server_id="آيدي السيرفر (اختياري لتصفية الملاحظات)")
    async def delete_note_cmd(self, interaction: discord.Interaction, server_id: str = None):
        if await deny_if_not_owner(interaction):
            return

        notes = get_notes_from_db(server_id)
        if not notes:
            msg = f"لا توجد ملاحظات لحذفها للسيرفر `{server_id}`." if server_id else "لا توجد أي ملاحظات مسجلة حالياً لحذفها."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        view = NoteDeleteUI(notes)
        await interaction.response.send_message(
            "🗑️ **اختر الملاحظة التي ترغب في مسحها من القائمة المنسدلة أدناه:**",
            view=view,
            ephemeral=True
        )

    async def _leave_guild_by_id(self, interaction: discord.Interaction, server_id: str):
        try:
            guild_id = int(str(server_id).strip())
        except (TypeError, ValueError):
            await interaction.response.send_message("❌ آيدي السيرفر غير صحيح.", ephemeral=True)
            return

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            await interaction.response.send_message(f"⚠️ البوت غير موجود حالياً في السيرفر {guild_id}.", ephemeral=True)
            return

        await interaction.response.send_message(f"⏳ جاري إخراج البوت من السيرفر {guild.name}...", ephemeral=True)
        await guild.leave()
        await interaction.followup.send(f"✅ غادر البوت السيرفر {guild.name} (ID: {guild_id}) بدون حذف بيانات الاشتراك.", ephemeral=True)

    @app_commands.command(name="مغادرة_اجبارية", description="🔒 إخراج البوت من سيرفر محدد بدون حذف اشتراكه")
    @app_commands.describe(server_id="آيدي السيرفر الذي سيغادره البوت")
    async def force_leave_cmd(self, interaction: discord.Interaction, server_id: str):
        if await deny_if_not_owner(interaction):
            return
        await self._leave_guild_by_id(interaction, server_id)

    @app_commands.command(name="طرد_البوت", description="🔒 إخراج البوت من سيرفر محدد بدون حذف اشتراكه")
    @app_commands.describe(server_id="آيدي السيرفر الذي سيغادره البوت")
    async def kick_bot_cmd(self, interaction: discord.Interaction, server_id: str):
        if await deny_if_not_owner(interaction):
            return
        await self._leave_guild_by_id(interaction, server_id)


async def setup(bot: commands.Bot):
    bot.tree.interaction_check = global_subscription_check
    await bot.add_cog(SubscriptionCog(bot))
