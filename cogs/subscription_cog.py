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
import logging
import uuid
import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.command_groups import subscription_group

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

ADMIN_GUILD_ID = _parse_int(os.getenv("ADMIN_GUILD_ID"), 0)
# Keep private admin commands fail-closed when hosting secrets are incomplete.
# Guild ID 0 is never synced, so these commands cannot leak into global commands.
ADMIN_GUILD_OBJECT = discord.Object(id=ADMIN_GUILD_ID or 0)
log = logging.getLogger(__name__)
if not ADMIN_GUILD_ID:
    log.warning("ADMIN_GUILD_ID is missing; subscription admin commands will remain unsynced")

SUBSCRIPTION_ADMIN_IDS = frozenset({
    1527692596598804565,
    1527765325221990521,
})
CONTACT_USERNAME = (os.getenv("CONTACT_USERNAME") or "seifeldaly124").strip()
CONTACT_LINE = f"للتجديد يرجى التواصل مع: **{CONTACT_USERNAME}**"
GRACE_PERIOD_DAYS = _parse_int(os.getenv("GRACE_PERIOD_DAYS"), 3)
SUBSCRIPTION_PLAN_NAME = "VIP"

# Paid plans and wallet defaults. Prices can be changed with /setprice or environment variables.
PLAN_BOT = "bot"
PLAN_PROTECTION = "protection"
PLAN_LABELS = {
    PLAN_BOT: "اشتراك البوت العادي / Regular bot subscription",
    PLAN_PROTECTION: "اشتراك الحماية الإضافي / Extra protection subscription",
}
SUBSCRIPTION_CURRENCY = (os.getenv("SUBSCRIPTION_CURRENCY") or "EGP").strip()
DEFAULT_PLAN_DAYS = 30
DEFAULT_PLAN_PRICES = {
    PLAN_BOT: _parse_int(os.getenv("BASE_SUBSCRIPTION_PRICE"), 100),
    PLAN_PROTECTION: _parse_int(os.getenv("PROTECTION_SUBSCRIPTION_PRICE"), 50),
}
DEFAULT_PLAN_DETAILS = {
    PLAN_BOT: "يشمل تشغيل أوامر البوت العامة في السيرفر.",
    PLAN_PROTECTION: "إضافة اختيارية لتفعيل أوامر الحماية.",
}
PROTECTION_COMMAND_ROOTS = frozenset({"security", "shield", "voice_rescue", "shelter", "shelter_done"})
BILLING_COMMAND_NAMES = frozenset({
    "redeem", "balance", "الرصيد", "pay", "دفع",
    "payment-options", "خيارات_الدفع",
})


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
            expired_notified INTEGER NOT NULL DEFAULT 0,
            protection_expires_at TEXT
        )
    """)

    for column_def in (
        "warned_1h INTEGER NOT NULL DEFAULT 0",
        "expired_notified INTEGER NOT NULL DEFAULT 0",
        "protection_expires_at TEXT",
    ):
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            user_id TEXT PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            kind TEXT NOT NULL,
            actor_id TEXT,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payment_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ar TEXT NOT NULL,
            name_en TEXT NOT NULL,
            details TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            plan_key TEXT PRIMARY KEY,
            price INTEGER NOT NULL CHECK (price >= 0),
            days INTEGER NOT NULL CHECK (days > 0),
            enabled INTEGER NOT NULL DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pricing_catalog (
            plan_key TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            price INTEGER NOT NULL CHECK (price >= 0),
            days INTEGER NOT NULL CHECK (days > 0),
            details TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            is_custom INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)
    for plan_key, price in DEFAULT_PLAN_PRICES.items():
        cur.execute(
            "INSERT OR IGNORE INTO plans (plan_key, price, days, enabled) VALUES (?, ?, ?, 1)",
            (plan_key, max(0, price), DEFAULT_PLAN_DAYS),
        )
        cur.execute(
            """
            INSERT OR IGNORE INTO pricing_catalog
                (plan_key, display_name, price, days, details, enabled, is_custom, created_at)
            VALUES (?, ?, ?, ?, ?, 1, 0, ?)
            """,
            (
                plan_key,
                PLAN_LABELS[plan_key].split(" / ")[0],
                max(0, price),
                DEFAULT_PLAN_DAYS,
                DEFAULT_PLAN_DETAILS[plan_key],
                datetime.datetime.utcnow().isoformat(),
            ),
        )

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




def get_plan_config(plan_key: str) -> dict:
    if plan_key not in (PLAN_BOT, PLAN_PROTECTION):
        raise ValueError("Unknown subscription plan")
    conn = get_connection()
    row = conn.execute(
        "SELECT price, days, enabled FROM plans WHERE plan_key = ?", (plan_key,)
    ).fetchone()
    conn.close()
    if not row:
        return {"price": DEFAULT_PLAN_PRICES[plan_key], "days": DEFAULT_PLAN_DAYS, "enabled": True}
    return {"price": int(row[0]), "days": int(row[1]), "enabled": bool(row[2])}


def get_wallet_balance(user_id: int) -> int:
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?, 0)", (str(user_id),))
    row = conn.execute("SELECT balance FROM wallets WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.commit()
    conn.close()
    return int(row[0]) if row else 0


def credit_wallet(user_id: int, amount: int, actor_id: int) -> int:
    if amount <= 0:
        raise ValueError("Wallet credit must be positive")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        uid = str(user_id)
        conn.execute("INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?, 0)", (uid,))
        conn.execute("UPDATE wallets SET balance = balance + ? WHERE user_id = ?", (amount, uid))
        balance = int(conn.execute("SELECT balance FROM wallets WHERE user_id = ?", (uid,)).fetchone()[0])
        conn.execute(
            "INSERT INTO wallet_transactions (user_id, amount, balance_after, kind, actor_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, amount, balance, "admin_credit", str(actor_id), datetime.datetime.utcnow().isoformat()),
        )
        conn.commit()
        return balance
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_payment_options() -> list[tuple]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name_ar, name_en, details FROM payment_options WHERE enabled = 1 ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return rows


def add_payment_option(name_ar: str, name_en: str, details: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO payment_options (name_ar, name_en, details, created_at) VALUES (?, ?, ?, ?)",
        (name_ar.strip(), name_en.strip(), details.strip(), datetime.datetime.utcnow().isoformat()),
    )
    option_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return option_id


def set_plan_price(plan_key: str, price: int) -> None:
    if plan_key not in (PLAN_BOT, PLAN_PROTECTION) or price < 0:
        raise ValueError("Invalid plan or price")
    conn = get_connection()
    conn.execute(
        "INSERT INTO plans (plan_key, price, days, enabled) VALUES (?, ?, ?, 1) "
        "ON CONFLICT(plan_key) DO UPDATE SET price = excluded.price, enabled = 1",
        (plan_key, price, DEFAULT_PLAN_DAYS),
    )
    conn.execute(
        "UPDATE pricing_catalog SET price = ?, enabled = 1 WHERE plan_key = ?",
        (price, plan_key),
    )
    conn.commit()
    conn.close()


def get_pricing_catalog() -> list[tuple]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT plan_key, display_name, price, days, details
        FROM pricing_catalog
        WHERE enabled = 1
        ORDER BY is_custom ASC, rowid ASC
        """
    ).fetchall()
    conn.close()
    return rows


def add_pricing_catalog_item(name: str, price: int, days: int, details: str) -> str:
    name = " ".join(name.strip().split())[:100]
    details = details.strip()[:900]
    if not name or not details or price < 0 or days <= 0:
        raise ValueError("Invalid pricing item")

    plan_key = f"custom_{uuid.uuid4().hex[:12]}"
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO pricing_catalog
            (plan_key, display_name, price, days, details, enabled, is_custom, created_at)
        VALUES (?, ?, ?, ?, ?, 1, 1, ?)
        """,
        (plan_key, name, price, days, details, datetime.datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return plan_key


def delete_pricing_catalog_item(plan_key: str) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM pricing_catalog WHERE plan_key = ? AND is_custom = 1",
        (plan_key.strip(),),
    )
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_plan_expiry(server_id: str, plan_key: str = PLAN_BOT):
    column = "expires_at" if plan_key == PLAN_BOT else "protection_expires_at"
    conn = get_connection()
    row = conn.execute(f"SELECT {column} FROM subscriptions WHERE server_id = ?", (str(server_id),)).fetchone()
    conn.close()
    return row[0] if row else None


def is_plan_active(server_id: int | str, plan_key: str = PLAN_BOT) -> bool:
    expires_at = get_plan_expiry(str(server_id), plan_key)
    if not expires_at:
        return False
    try:
        return datetime.datetime.fromisoformat(expires_at) > datetime.datetime.utcnow()
    except (TypeError, ValueError):
        return False


def purchase_plan(user_id: int, server_id: int, plan_key: str) -> dict:
    if plan_key not in (PLAN_BOT, PLAN_PROTECTION):
        return {"success": False, "reason": "invalid_plan"}
    config = get_plan_config(plan_key)
    if not config["enabled"]:
        return {"success": False, "reason": "disabled", "config": config}

    now = datetime.datetime.utcnow()
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        uid, sid = str(user_id), str(server_id)
        conn.execute("INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?, 0)", (uid,))
        balance = int(conn.execute("SELECT balance FROM wallets WHERE user_id = ?", (uid,)).fetchone()[0])
        price, days = config["price"], config["days"]
        if balance < price:
            conn.rollback()
            return {"success": False, "reason": "insufficient", "balance": balance, "price": price, "missing": price - balance, "config": config}

        row = conn.execute(
            "SELECT expires_at, protection_expires_at FROM subscriptions WHERE server_id = ?", (sid,)
        ).fetchone()
        base_expiry, protection_expiry = (row if row else (None, None))
        if plan_key == PLAN_PROTECTION and not base_expiry:
            conn.rollback()
            return {"success": False, "reason": "base_required", "balance": balance, "price": price, "config": config}
        if plan_key == PLAN_PROTECTION:
            try:
                if datetime.datetime.fromisoformat(base_expiry) <= now:
                    conn.rollback()
                    return {"success": False, "reason": "base_required", "balance": balance, "price": price, "config": config}
            except (TypeError, ValueError):
                conn.rollback()
                return {"success": False, "reason": "base_required", "balance": balance, "price": price, "config": config}

        old_expiry = base_expiry if plan_key == PLAN_BOT else protection_expiry
        try:
            base_date = max(datetime.datetime.fromisoformat(old_expiry), now) if old_expiry else now
        except (TypeError, ValueError):
            base_date = now
        new_expiry = (base_date + datetime.timedelta(days=days)).isoformat()
        if plan_key == PLAN_BOT:
            base_expiry = new_expiry
        else:
            protection_expiry = new_expiry

        conn.execute(
            "INSERT INTO subscriptions (server_id, expires_at, protection_expires_at, warned_1h, expired_notified) VALUES (?, ?, ?, 0, 0) "
            "ON CONFLICT(server_id) DO UPDATE SET expires_at = excluded.expires_at, protection_expires_at = excluded.protection_expires_at, warned_1h = 0, expired_notified = 0",
            (sid, base_expiry or now.isoformat(), protection_expiry),
        )
        changed = conn.execute(
            "UPDATE wallets SET balance = balance - ? WHERE user_id = ? AND balance >= ?", (price, uid, price)
        ).rowcount
        if changed != 1:
            conn.rollback()
            return {"success": False, "reason": "insufficient", "balance": balance, "price": price, "missing": price - balance, "config": config}
        new_balance = balance - price
        conn.execute(
            "INSERT INTO wallet_transactions (user_id, amount, balance_after, kind, actor_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, -price, new_balance, f"purchase_{plan_key}", uid, now.isoformat()),
        )
        conn.commit()
        return {"success": True, "balance": new_balance, "price": price, "days": days, "expires_at": new_expiry, "config": config}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def payment_options_text() -> str:
    rows = get_payment_options()
    if not rows:
        return "لا توجد وسائل دفع مضافة حالياً. تواصل مع مدير الاشتراكات.\nNo payment methods are configured yet. Contact a subscription manager."
    lines = ["📲 وسائل الدفع / Payment methods:"]
    for option_id, name_ar, name_en, details in rows:
        lines.append(f"**{option_id}. {name_ar} / {name_en}**\n{details}")
    return "\n\n".join(lines)


def pricing_embed() -> discord.Embed:
    rows = get_pricing_catalog()
    embed = discord.Embed(
        title="💳 تسعيرة اشتراكات البوت",
        description="الأسعار الحالية ومدة كل خطة. استخدم `/subscription pay` للدفع من رصيد المحفظة.",
        color=discord.Color.gold(),
    )
    if not rows:
        embed.description = "لا توجد تسعيرات مفعلة حالياً. تواصل مع مدير الاشتراكات."
        return embed

    for plan_key, display_name, price, days, details in rows[:25]:
        embed.add_field(
            name=f"📦 {display_name}",
            value=f"**السعر:** {price:,} {SUBSCRIPTION_CURRENCY}\n"
                  f"**المدة:** {days} يوم\n"
                  f"{details}",
            inline=False,
        )
    embed.set_footer(text="الأسعار قابلة للتغيير بواسطة مديري الاشتراكات.")
    return embed


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

    command = interaction.command
    command_name = getattr(command, "name", "")
    root = command
    while getattr(root, "parent", None) is not None:
        root = root.parent
    root_name = getattr(root, "name", command_name)

    # Billing and redemption must remain available when a guild has no active plan.
    if command_name in BILLING_COMMAND_NAMES or root_name in BILLING_COMMAND_NAMES:
        return True
    if interaction.guild is None:
        return True

    if not is_plan_active(interaction.guild.id, PLAN_BOT):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "🔒 اشتراك البوت العادي غير مفعل لهذا السيرفر. استخدم /pay لاختيار الاشتراك.\n"
                "🔒 The regular bot subscription is not active here. Use /pay to subscribe.",
                ephemeral=True,
            )
        return False

    if root_name in PROTECTION_COMMAND_ROOTS and not is_plan_active(interaction.guild.id, PLAN_PROTECTION):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "🛡️ اشتراك الحماية الإضافي غير مفعل. استخدم /pay واختر Protection.\n"
                "🛡️ The extra protection subscription is not active. Use /pay and choose Protection.",
                ephemeral=True,
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



    async def _send_balance(self, interaction: discord.Interaction):
        balance = get_wallet_balance(interaction.user.id)
        await interaction.response.send_message(
            f"💰 رصيد محفظتك: **{balance:,} {SUBSCRIPTION_CURRENCY}**\n"
            f"💰 Wallet balance: **{balance:,} {SUBSCRIPTION_CURRENCY}**",
            ephemeral=True,
        )

    @subscription_group.command(name="balance", description="💰 عرض رصيد المحفظة / View wallet balance")
    async def balance(self, interaction: discord.Interaction):
        await self._send_balance(interaction)

    @subscription_group.command(name="الرصيد", description="💰 عرض رصيد المحفظة / View wallet balance")
    async def balance_ar(self, interaction: discord.Interaction):
        await self._send_balance(interaction)

    async def _send_payment_options(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            payment_options_text(),
            ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="payment-options", description="📲 عرض وسائل الدفع / View payment methods")
    async def payment_options(self, interaction: discord.Interaction):
        await self._send_payment_options(interaction)

    @app_commands.command(name="خيارات_الدفع", description="📲 عرض وسائل الدفع / View payment methods")
    async def payment_options_ar(self, interaction: discord.Interaction):
        await self._send_payment_options(interaction)

    async def _send_pricing(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=pricing_embed(),
            ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @subscription_group.command(name="pricing", description="💳 عرض تسعيرة الاشتراكات الحالية")
    async def pricing(self, interaction: discord.Interaction):
        await self._send_pricing(interaction)

    @subscription_group.command(name="التسعيرة", description="💳 عرض تسعيرة الاشتراكات الحالية")
    async def pricing_ar(self, interaction: discord.Interaction):
        await self._send_pricing(interaction)

    async def _add_pricing(
        self,
        interaction: discord.Interaction,
        plan_name: str,
        price: int,
        days: int,
        details: str,
    ):
        if await deny_if_not_owner(interaction):
            return
        try:
            plan_key = add_pricing_catalog_item(plan_name, price, days, details)
        except ValueError:
            await interaction.response.send_message(
                "❌ اكتب اسم التسعيرة والمبلغ والمدة والمعلومة بشكل صحيح.",
                ephemeral=False,
            )
            return
        await interaction.response.send_message(
            f"✅ تمت إضافة التسعيرة **{plan_name.strip()[:100]}** بسعر "
            f"**{price:,} {SUBSCRIPTION_CURRENCY}** لمدة **{days} يوم**.\n"
            f"المعرف الإداري: `{plan_key}`",
            ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @subscription_group.command(name="addpricing", description="➕ إضافة تسعيرة مخصصة للكتالوج")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(
        plan_name="اسم التسعيرة",
        price="السعر",
        days="عدد الأيام",
        details="المعلومة التي ستظهر للناس",
    )
    async def add_pricing(
        self,
        interaction: discord.Interaction,
        plan_name: str,
        price: app_commands.Range[int, 0, 100000000],
        days: app_commands.Range[int, 1, 3650],
        details: str,
    ):
        await self._add_pricing(interaction, plan_name, price, days, details)

    @subscription_group.command(name="إضافة_تسعيرة", description="➕ إضافة تسعيرة مخصصة للكتالوج")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(
        plan_name="اسم التسعيرة",
        price="السعر",
        days="عدد الأيام",
        details="المعلومة التي ستظهر للناس",
    )
    async def add_pricing_ar(
        self,
        interaction: discord.Interaction,
        plan_name: str,
        price: app_commands.Range[int, 0, 100000000],
        days: app_commands.Range[int, 1, 3650],
        details: str,
    ):
        await self._add_pricing(interaction, plan_name, price, days, details)

    async def _delete_pricing(self, interaction: discord.Interaction, plan_key: str):
        if await deny_if_not_owner(interaction):
            return
        if delete_pricing_catalog_item(plan_key):
            msg = f"✅ تم حذف التسعيرة المخصصة `{plan_key.strip()}`."
        else:
            msg = "❌ لم يتم العثور على تسعيرة مخصصة بهذا المعرف؛ لا يمكن حذف الخطط الأساسية."
        await interaction.response.send_message(msg, ephemeral=False)

    @subscription_group.command(name="deletepricing", description="🗑️ حذف تسعيرة مخصصة")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(plan_key="المعرف الإداري الظاهر في أمر إضافة التسعيرة")
    async def delete_pricing(self, interaction: discord.Interaction, plan_key: str):
        await self._delete_pricing(interaction, plan_key)

    @subscription_group.command(name="حذف_تسعيرة", description="🗑️ حذف تسعيرة مخصصة")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(plan_key="المعرف الإداري الظاهر في أمر إضافة التسعيرة")
    async def delete_pricing_ar(self, interaction: discord.Interaction, plan_key: str):
        await self._delete_pricing(interaction, plan_key)

    async def handle_admin_dm(self, message: discord.Message) -> bool:
        """Handle a small, explicit command set for subscription managers in DMs."""
        if message.guild is not None or not is_owner(message.author.id):
            return False

        raw = message.content.strip()
        text = raw.lstrip("!").strip()
        if not text:
            return True

        parts = text.split(maxsplit=3)
        command = parts[0].lower()
        aliases = {
            "التسعيرة": "pricing",
            "تسعيره": "pricing",
            "الاسعار": "pricing",
            "الأسعار": "pricing",
            "pricing": "pricing",
            "help": "help",
            "مساعدة": "help",
            "السيرفرات": "servers",
            "سيرفرات": "servers",
            "servers": "servers",
            "الرصيد": "balance",
            "balance": "balance",
            "اضافة_رصيد": "addbalance",
            "إضافة_رصيد": "addbalance",
            "addbalance": "addbalance",
            "تحديد_سعر": "setprice",
            "setprice": "setprice",
            "إضافة_تسعيرة": "addpricing",
            "اضافة_تسعيرة": "addpricing",
            "addpricing": "addpricing",
            "حذف_تسعيرة": "deletepricing",
            "حذف_تسعيره": "deletepricing",
            "deletepricing": "deletepricing",
        }
        command = aliases.get(command, command)

        if command == "pricing":
            await message.channel.send(embed=pricing_embed(), allowed_mentions=discord.AllowedMentions.none())
            return True

        if command == "help":
            await message.channel.send(
                "🛠️ أوامر مدير الاشتراكات في الخاص:\n"
                "`التسعيرة` — عرض الأسعار\n"
                "`السيرفرات` — حالة السيرفرات والاشتراكات\n"
                "`الرصيد USER_ID` — رصيد مستخدم\n"
                "`اضافة_رصيد USER_ID AMOUNT` — إضافة رصيد\n"
                "`تحديد_سعر bot AMOUNT` — تعديل سعر البوت\n"
                "`إضافة_تسعيرة الاسم | السعر | الأيام | المعلومة` — إضافة تسعيرة\n"
                "`حذف_تسعيرة CUSTOM_KEY` — حذف تسعيرة مخصصة\n"
                "يمكن كتابة `!` قبل الأمر أيضاً."
            )
            return True

        if command == "servers":
            now = datetime.datetime.utcnow()
            lines = []
            for guild in sorted(self.bot.guilds, key=lambda item: item.name.lower()):
                expires_at = get_subscription(str(guild.id))
                status = "❌ بدون اشتراك"
                if expires_at:
                    try:
                        expiry = datetime.datetime.fromisoformat(expires_at)
                        status = (
                            f"✅ حتى {expiry.strftime('%Y-%m-%d %H:%M UTC')}"
                            if expiry > now
                            else f"⚠️ منتهي {expiry.strftime('%Y-%m-%d %H:%M UTC')}"
                        )
                    except (TypeError, ValueError):
                        status = "⚠️ تاريخ اشتراك غير صالح"
                lines.append(f"• **{guild.name[:80]}** (`{guild.id}`): {status}")
            if not lines:
                lines.append("لا يوجد أي سيرفر متصل حالياً.")
            await message.channel.send("\n".join(lines)[:1900])
            return True

        if command == "balance":
            if len(parts) != 2 or not parts[1].isdigit():
                await message.channel.send("❌ الاستخدام: `الرصيد USER_ID`")
            else:
                balance = get_wallet_balance(int(parts[1]))
                await message.channel.send(
                    f"💰 رصيد `{parts[1]}` هو **{balance:,} {SUBSCRIPTION_CURRENCY}**."
                )
            return True

        if command == "addbalance":
            if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
                await message.channel.send("❌ الاستخدام: `اضافة_رصيد USER_ID AMOUNT`")
            else:
                amount = int(parts[2])
                if amount <= 0 or amount > 100000000:
                    await message.channel.send("❌ المبلغ يجب أن يكون بين 1 و100,000,000.")
                else:
                    balance = credit_wallet(int(parts[1]), amount, message.author.id)
                    await message.channel.send(
                        f"✅ تمت إضافة **{amount:,} {SUBSCRIPTION_CURRENCY}** إلى `{parts[1]}`.\n"
                        f"الرصيد الجديد: **{balance:,} {SUBSCRIPTION_CURRENCY}**"
                    )
            return True

        if command == "setprice":
            if len(parts) != 3 or not parts[2].isdigit():
                await message.channel.send("❌ الاستخدام: `تحديد_سعر bot AMOUNT`")
            else:
                plan_key = parts[1].lower()
                if plan_key not in (PLAN_BOT, PLAN_PROTECTION):
                    await message.channel.send("❌ الخطة يجب أن تكون `bot` أو `protection`.")
                else:
                    amount = int(parts[2])
                    if amount > 100000000:
                        await message.channel.send("❌ السعر أكبر من الحد المسموح.")
                    else:
                        set_plan_price(plan_key, amount)
                        await message.channel.send(
                            f"✅ تم ضبط سعر {PLAN_LABELS[plan_key]} إلى "
                            f"**{amount:,} {SUBSCRIPTION_CURRENCY}**."
                        )
            return True

        if command == "addpricing":
            payload = text.split(maxsplit=1)[1] if " " in text else ""
            fields = [field.strip() for field in payload.split("|", 3)]
            if (
                len(fields) != 4
                or not fields[1].isdigit()
                or not fields[2].isdigit()
                or int(fields[1]) > 100000000
                or int(fields[2]) > 3650
            ):
                await message.channel.send(
                    "❌ الاستخدام: `إضافة_تسعيرة الاسم | السعر | الأيام | المعلومة`"
                )
            else:
                try:
                    plan_key = add_pricing_catalog_item(
                        fields[0], int(fields[1]), int(fields[2]), fields[3]
                    )
                except ValueError:
                    await message.channel.send("❌ تحقق من الاسم والمبلغ والمدة والمعلومة.")
                else:
                    await message.channel.send(
                        f"✅ تمت إضافة التسعيرة **{fields[0][:100]}**.\n"
                        f"المعرف الإداري: `{plan_key}`"
                    )
            return True

        if command == "deletepricing":
            if len(parts) != 2:
                await message.channel.send("❌ الاستخدام: `حذف_تسعيرة CUSTOM_KEY`")
            elif delete_pricing_catalog_item(parts[1]):
                await message.channel.send(f"✅ تم حذف التسعيرة المخصصة `{parts[1]}`.")
            else:
                await message.channel.send("❌ المعرف غير موجود أو يخص خطة أساسية.")
            return True

        await message.channel.send("❓ لم أفهم الطلب. اكتب `مساعدة` لعرض أوامر مدير الاشتراكات.")
        return True

    async def _pay(self, interaction: discord.Interaction, plan: app_commands.Choice[str]):
        if interaction.guild is None:
            return await interaction.response.send_message(
                "❌ الاشتراك يتم من داخل السيرفر.\n❌ Subscriptions must be purchased inside a server.", ephemeral=True
            )
        plan_key = plan.value
        result = purchase_plan(interaction.user.id, interaction.guild.id, plan_key)
        if result["success"]:
            label = PLAN_LABELS[plan_key]
            await interaction.response.send_message(
                f"✅ تم تفعيل {label} لمدة **{result['days']} يوم**.\n"
                f"ينتهي في: {result['expires_at']}\n"
                f"تم الخصم: **{result['price']:,} {SUBSCRIPTION_CURRENCY}** | الرصيد المتبقي: **{result['balance']:,} {SUBSCRIPTION_CURRENCY}**\n"
                f"✅ {label} activated for **{result['days']} days**.\n"
                f"Expires: {result['expires_at']}\n"
                f"Charged: **{result['price']:,} {SUBSCRIPTION_CURRENCY}** | Remaining: **{result['balance']:,} {SUBSCRIPTION_CURRENCY}**",
                ephemeral=True,
            )
            return

        if result["reason"] == "insufficient":
            await interaction.response.send_message(
                f"❌ رصيدك غير كافٍ لاشتراك {PLAN_LABELS.get(plan_key, plan_key)}.\n"
                f"الرصيد الحالي: **{result['balance']:,} {SUBSCRIPTION_CURRENCY}**\n"
                f"السعر: **{result['price']:,} {SUBSCRIPTION_CURRENCY}**\n"
                f"الناقص: **{result['missing']:,} {SUBSCRIPTION_CURRENCY}**\n\n"
                f"❌ Your wallet is not enough.\n"
                f"Current: **{result['balance']:,} {SUBSCRIPTION_CURRENCY}** | Price: **{result['price']:,} {SUBSCRIPTION_CURRENCY}**\n"
                f"Missing: **{result['missing']:,} {SUBSCRIPTION_CURRENCY}**\n\n{payment_options_text()}",
                ephemeral=True,
            )
        elif result["reason"] == "base_required":
            await interaction.response.send_message(
                "⚠️ فعّل اشتراك البوت العادي أولاً ثم اشترِ اشتراك الحماية.\n"
                "⚠️ Activate the regular bot subscription before buying protection.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "⚠️ خطة الاشتراك غير متاحة حالياً.\n⚠️ This subscription plan is currently unavailable.", ephemeral=True
            )

    @subscription_group.command(name="pay", description="💳 ادفع من المحفظة / Pay from wallet")
    @app_commands.describe(plan="الخطة / Plan")
    @app_commands.choices(plan=[
        app_commands.Choice(name="اشتراك البوت / Regular bot", value=PLAN_BOT),
        app_commands.Choice(name="اشتراك الحماية / Extra protection", value=PLAN_PROTECTION),
    ])
    async def pay(self, interaction: discord.Interaction, plan: app_commands.Choice[str]):
        await self._pay(interaction, plan)

    @subscription_group.command(name="دفع", description="💳 ادفع من المحفظة / Pay from wallet")
    @app_commands.describe(plan="الخطة / Plan")
    @app_commands.choices(plan=[
        app_commands.Choice(name="اشتراك البوت / Regular bot", value=PLAN_BOT),
        app_commands.Choice(name="اشتراك الحماية / Extra protection", value=PLAN_PROTECTION),
    ])
    async def pay_ar(self, interaction: discord.Interaction, plan: app_commands.Choice[str]):
        await self._pay(interaction, plan)

    async def _add_balance(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if await deny_if_not_owner(interaction):
            return
        balance = credit_wallet(user.id, amount, interaction.user.id)
        await interaction.response.send_message(
            f"✅ تمت إضافة **{amount:,} {SUBSCRIPTION_CURRENCY}** إلى محفظة {user.mention}.\n"
            f"الرصيد الجديد / New balance: **{balance:,} {SUBSCRIPTION_CURRENCY}**", ephemeral=True
        )

    @subscription_group.command(name="addbalance", description="💰 إضافة رصيد لمستخدم / Credit a wallet")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(user="المستخدم / User", amount="المبلغ / Amount")
    async def addbalance(self, interaction: discord.Interaction, user: discord.User, amount: app_commands.Range[int, 1, 100000000]):
        await self._add_balance(interaction, user, amount)

    @subscription_group.command(name="إضافة_رصيد", description="💰 إضافة رصيد لمستخدم / Credit a wallet")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(user="المستخدم / User", amount="المبلغ / Amount")
    async def addbalance_ar(self, interaction: discord.Interaction, user: discord.User, amount: app_commands.Range[int, 1, 100000000]):
        await self._add_balance(interaction, user, amount)

    async def _add_pay(self, interaction: discord.Interaction, name_ar: str, name_en: str, details: str):
        if await deny_if_not_owner(interaction):
            return
        if not name_ar.strip() or not name_en.strip() or not details.strip():
            return await interaction.response.send_message(
                "❌ اكتب اسم وسيلة الدفع بالعربي والإنجليزي والتفاصيل.\n❌ Provide Arabic name, English name, and payment details.", ephemeral=True
            )
        option_id = add_payment_option(name_ar[:100], name_en[:100], details[:1000])
        await interaction.response.send_message(
            f"✅ تمت إضافة وسيلة الدفع رقم **{option_id}**: {name_ar} / {name_en}\n"
            f"✅ Payment method **{option_id}** added: {name_ar} / {name_en}", ephemeral=True
        )

    @app_commands.command(name="addpay", description="📲 إضافة وسيلة دفع / Add a payment method")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(name_ar="اسم الطريقة بالعربي", name_en="Payment method name", details="رقم التحويل أو التفاصيل / Transfer details")
    async def addpay(self, interaction: discord.Interaction, name_ar: str, name_en: str, details: str):
        await self._add_pay(interaction, name_ar, name_en, details)

    @app_commands.command(name="إضافة_طريقة_دفع", description="📲 إضافة وسيلة دفع / Add a payment method")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(name_ar="اسم الطريقة بالعربي", name_en="Payment method name", details="رقم التحويل أو التفاصيل / Transfer details")
    async def addpay_ar(self, interaction: discord.Interaction, name_ar: str, name_en: str, details: str):
        await self._add_pay(interaction, name_ar, name_en, details)

    async def _set_price(self, interaction: discord.Interaction, plan: app_commands.Choice[str], amount: int):
        if await deny_if_not_owner(interaction):
            return
        set_plan_price(plan.value, amount)
        await interaction.response.send_message(
            f"✅ تم ضبط سعر {PLAN_LABELS[plan.value]} إلى **{amount:,} {SUBSCRIPTION_CURRENCY}** لمدة {DEFAULT_PLAN_DAYS} يوم.\n"
            f"✅ Price updated to **{amount:,} {SUBSCRIPTION_CURRENCY}** for {DEFAULT_PLAN_DAYS} days.", ephemeral=True
        )

    @subscription_group.command(name="setprice", description="⚙️ ضبط سعر الاشتراك / Set subscription price")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(plan="الخطة / Plan", amount="السعر / Price")
    @app_commands.choices(plan=[
        app_commands.Choice(name="اشتراك البوت / Regular bot", value=PLAN_BOT),
        app_commands.Choice(name="اشتراك الحماية / Extra protection", value=PLAN_PROTECTION),
    ])
    async def setprice(self, interaction: discord.Interaction, plan: app_commands.Choice[str], amount: app_commands.Range[int, 0, 100000000]):
        await self._set_price(interaction, plan, amount)

    @subscription_group.command(name="تحديد_سعر", description="⚙️ ضبط سعر الاشتراك / Set subscription price")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(plan="الخطة / Plan", amount="السعر / Price")
    @app_commands.choices(plan=[
        app_commands.Choice(name="اشتراك البوت / Regular bot", value=PLAN_BOT),
        app_commands.Choice(name="اشتراك الحماية / Extra protection", value=PLAN_PROTECTION),
    ])
    async def setprice_ar(self, interaction: discord.Interaction, plan: app_commands.Choice[str], amount: app_commands.Range[int, 0, 100000000]):
        await self._set_price(interaction, plan, amount)


    @subscription_group.command(name="قائمة_السيرفرات", description="🔒 تقرير منظم عن كل السيرفرات وحالة الاشتراك")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
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
                subscription_text = f"✅ {SUBSCRIPTION_PLAN_NAME} فعال حتى {expiry_date.strftime('%Y-%m-%d %H:%M UTC')} ({remaining_days} يوم متبقٍ)"
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


    @subscription_group.command(name="حالة_الاشتراكات", description="🔒 عرض حالة اشتراكات جميع السيرفرات المخزنة")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
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

    @subscription_group.command(name="تحديد_اشتراك", description="🔒 تحديد اشتراك جديد لسيرفر معين")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
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
            f"✅ تم تحديد اشتراك {SUBSCRIPTION_PLAN_NAME} للسيرفر `{server_id}` لمدة {days} يوم.\nينتهي في: {expiry_date.strftime('%Y-%m-%d %H:%M UTC')}",
            ephemeral=True
        )

    @subscription_group.command(name="تجديد_اشتراك", description="🔒 تجديد (إضافة أيام) على اشتراك سيرفر معين")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
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
            f"✅ تم تجديد اشتراك {SUBSCRIPTION_PLAN_NAME} للسيرفر `{server_id}` بإضافة {days} يوم.\nالاشتراك الآن ينتهي في: {expiry_date.strftime('%Y-%m-%d %H:%M UTC')}",
            ephemeral=True
        )

    @subscription_group.command(name="ايقاف_اشتراك", description="🔒 إيقاف اشتراك سيرفر ومغادرته فوراً")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
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

    @subscription_group.command(name="انشاء_كود", description="🔒 توليد كود اشتراك جديد بعدد أيام محدد")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
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
            f"✅ تم تفعيل كود {SUBSCRIPTION_PLAN_NAME} بنجاح! تمت إضافة {days} يوم لاشتراك هذا السيرفر.\nالاشتراك الآن ينتهي في: {expiry_date.strftime('%Y-%m-%d %H:%M UTC')}",
            ephemeral=True
        )

    @subscription_group.command(name="اضافة_ملاحظة", description="🔒 إضافة ملاحظة بعنوان (عامة للبوت أو خاصة بسيرفر)")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
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


    @subscription_group.command(name="عرض_الملاحظات", description="🔒 عرض قائمة بالملاحظات المسجلة واختيار إحداها")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
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

    @subscription_group.command(name="مسح_ملاحظة", description="🔒 مسح ملاحظة مسجلة باختيارها من القائمة")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
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

    @subscription_group.command(name="مغادرة_اجبارية", description="🔒 إخراج البوت من سيرفر محدد بدون حذف اشتراكه")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(server_id="آيدي السيرفر الذي سيغادره البوت")
    async def force_leave_cmd(self, interaction: discord.Interaction, server_id: str):
        if await deny_if_not_owner(interaction):
            return
        await self._leave_guild_by_id(interaction, server_id)

    @subscription_group.command(name="طرد_البوت", description="🔒 إخراج البوت من سيرفر محدد بدون حذف اشتراكه")
    @app_commands.guilds(ADMIN_GUILD_OBJECT)
    @app_commands.describe(server_id="آيدي السيرفر الذي سيغادره البوت")
    async def kick_bot_cmd(self, interaction: discord.Interaction, server_id: str):
        if await deny_if_not_owner(interaction):
            return
        await self._leave_guild_by_id(interaction, server_id)


async def setup(bot: commands.Bot):
    bot.tree.interaction_check = global_subscription_check
    await bot.add_cog(SubscriptionCog(bot))
