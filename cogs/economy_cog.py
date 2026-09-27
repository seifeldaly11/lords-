"""
كوج الاقتصاد (عملات + XP/مستويات) — منقول من bot-updated (utils/coins.js + utils/xp.js
+ commands/economy/*.js).
"""
from __future__ import annotations

import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.security_cog import is_developer
from utils.storage import load, save

COINS_FILE = "coins_data"
XP_FILE = "xp_data"

DAILY_REWARD = 1000
BASE_MESSAGES = 15
MAX_LEVEL = 70


# --------------------------------------------------------------- coins
def _coins() -> dict:
    return load(COINS_FILE)


def get_user_coins(user_id: int) -> dict:
    data = _coins()
    user = data.setdefault(str(user_id), {"coins": 0, "last_daily": None})
    save(COINS_FILE, data)
    return user


def add_coins(user_id: int, amount: int) -> int:
    data = _coins()
    user = data.setdefault(str(user_id), {"coins": 0, "last_daily": None})
    user["coins"] += amount
    save(COINS_FILE, data)
    return user["coins"]


def reset_coins(user_id: int) -> None:
    data = _coins()
    data.pop(str(user_id), None)
    save(COINS_FILE, data)


def reset_all_coins() -> None:
    save(COINS_FILE, {})


def can_claim_daily(user_id: int) -> bool:
    user = get_user_coins(user_id)
    today = datetime.date.today().isoformat()
    return user.get("last_daily") != today


def claim_daily(user_id: int) -> dict:
    data = _coins()
    user = data.setdefault(str(user_id), {"coins": 0, "last_daily": None})
    today = datetime.date.today().isoformat()
    if user.get("last_daily") == today:
        return {"success": False}
    user["last_daily"] = today
    user["coins"] += DAILY_REWARD
    save(COINS_FILE, data)
    return {"success": True, "coins": DAILY_REWARD, "total": user["coins"]}


def get_top_coins(limit: int = 10) -> list:
    data = _coins()
    entries = [{"user_id": uid, **info} for uid, info in data.items()]
    entries.sort(key=lambda e: e.get("coins", 0), reverse=True)
    return entries[:limit]


# ------------------------------------------------------------------ xp
def _xp() -> dict:
    return load(XP_FILE)


def messages_for_level(level: int) -> int:
    if level <= 1:
        return 0
    return int(BASE_MESSAGES * (2 ** (level - 2)))


def level_from_xp(xp: int) -> int:
    level = 1
    total = 0
    while level < MAX_LEVEL:
        needed = messages_for_level(level + 1)
        if total + needed > xp:
            break
        total += needed
        level += 1
    return level


def get_user_xp(user_id: int, guild_id: int) -> dict:
    data = _xp()
    guild = data.setdefault(str(guild_id), {})
    user = guild.setdefault(str(user_id), {"xp": 0, "level": 1, "total_messages": 0})
    save(XP_FILE, data)
    return user


def add_xp(user_id: int, guild_id: int, amount: int) -> dict:
    data = _xp()
    guild = data.setdefault(str(guild_id), {})
    user = guild.setdefault(str(user_id), {"xp": 0, "level": 1, "total_messages": 0})
    old_level = user["level"]
    user["xp"] += amount
    user["total_messages"] += amount
    user["level"] = level_from_xp(user["xp"])
    save(XP_FILE, data)
    return {"old_level": old_level, "new_level": user["level"], "leveled_up": user["level"] > old_level, "user": user}


def get_top_xp(guild_id: int, limit: int = 10) -> list:
    data = _xp()
    guild = data.get(str(guild_id), {})
    entries = [{"user_id": uid, **info} for uid, info in guild.items()]
    entries.sort(key=lambda e: e.get("xp", 0), reverse=True)
    return entries[:limit]


def reset_xp(guild_id: int) -> None:
    data = _xp()
    data[str(guild_id)] = {}
    save(XP_FILE, data)


class EconomyCog(commands.Cog):
    """عملات، هدية يومية، XP ومستويات، وتوب."""

    economy_group = app_commands.Group(
        name="economy", description="💰 العملات، الهدية اليومية، XP والتوب | Coins, daily gift, XP & leaderboard",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        add_xp(message.author.id, message.guild.id, 1)

    @economy_group.command(name="coins", description="عرض رصيدك من العملات")
    @app_commands.guild_only()
    async def coins(self, interaction: discord.Interaction):
        user = get_user_coins(interaction.user.id)
        can_claim = can_claim_daily(interaction.user.id)
        status = "✅ متاحة الآن!" if can_claim else "⏳ تم استلامها اليوم بالفعل."
        await interaction.response.send_message(
            f"💰 رصيد {interaction.user.mention}: **{user['coins']:,}** عملة.\nالهدية اليومية: {status}"
        )

    @economy_group.command(name="daily", description="استلام الهدية اليومية")
    @app_commands.guild_only()
    async def daily(self, interaction: discord.Interaction):
        result = claim_daily(interaction.user.id)
        if not result["success"]:
            return await interaction.response.send_message("⏳ لقد استلمت هديتك اليومية بالفعل. حاول غداً!", ephemeral=True)
        embed = discord.Embed(
            title="🎁 تم استلام الهدية اليومية",
            description=f"{interaction.user.mention} حصل على **{result['coins']:,}** عملة!",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="الرصيد الجديد", value=f"{result['total']:,}")
        await interaction.response.send_message(embed=embed)

    @economy_group.command(name="addcoins", description="إضافة عملات لمستخدم (للمطورين)")
    @app_commands.describe(user="المستخدم", amount="الكمية")
    @app_commands.guild_only()
    async def addcoins(self, interaction: discord.Interaction, user: discord.User, amount: app_commands.Range[int, 1]):
        if not is_developer(interaction.user.id) and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين فقط.", ephemeral=True)
        new_balance = add_coins(user.id, amount)
        await interaction.response.send_message(
            f"✅ تم إضافة **{amount:,}** عملة لـ {user.mention}. الرصيد الجديد: **{new_balance:,}**."
        )

    @economy_group.command(name="restartcoins", description="إعادة تعيين العملات (للمطورين)")
    @app_commands.describe(target="اترك فارغاً لإعادة تعيين الكل، أو حدد مستخدم")
    @app_commands.guild_only()
    async def restartcoins(self, interaction: discord.Interaction, target: Optional[discord.User] = None):
        if not is_developer(interaction.user.id) and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين فقط.", ephemeral=True)
        if target is None:
            reset_all_coins()
            await interaction.response.send_message("✅ تم إعادة تعيين عملات الجميع.")
        else:
            reset_coins(target.id)
            await interaction.response.send_message(f"✅ تم إعادة تعيين عملات {target.mention}.")

    @economy_group.command(name="addxp", description="إضافة XP لمستخدم (للمطورين)")
    @app_commands.describe(user="المستخدم", amount="الكمية")
    @app_commands.guild_only()
    async def addxp(self, interaction: discord.Interaction, user: discord.User, amount: app_commands.Range[int, 1]):
        if not is_developer(interaction.user.id) and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين فقط.", ephemeral=True)
        result = add_xp(user.id, interaction.guild.id, amount)
        text = f"✅ تم إضافة **{amount} XP** لـ {user.mention}. المستوى الحالي: **{result['new_level']}**."
        if result["leveled_up"]:
            text += f"\n🎉 ترقّى من المستوى {result['old_level']} إلى {result['new_level']}!"
        await interaction.response.send_message(text)

    top_group = app_commands.Group(
        name="top", description="🏆 لوحة صدارة النشاط الكتابي",
        parent=economy_group,
    )

    @top_group.command(name="show", description="عرض التوب")
    @app_commands.guild_only()
    async def top_show(self, interaction: discord.Interaction):
        entries = get_top_xp(interaction.guild.id, 10)
        if not entries:
            return await interaction.response.send_message("ℹ️ لا توجد بيانات كافية بعد.", ephemeral=True)
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        lines = []
        for i, entry in enumerate(entries):
            member = interaction.guild.get_member(int(entry["user_id"]))
            name = member.mention if member else f"Unknown ({entry['user_id']})"
            lines.append(f"{medals[i]} {name} — المستوى {entry['level']} ({entry['total_messages']} رسالة)")
        embed = discord.Embed(title="🏆 لوحة الصدارة", description="\n".join(lines), color=discord.Color.from_rgb(255, 255, 255))
        await interaction.response.send_message(embed=embed)

    @top_group.command(name="restart", description="إعادة تعيين التوب (للمطورين)")
    @app_commands.guild_only()
    async def top_restart(self, interaction: discord.Interaction):
        if not is_developer(interaction.user.id) and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين فقط.", ephemeral=True)
        reset_xp(interaction.guild.id)
        await interaction.response.send_message("✅ تم إعادة تعيين لوحة الصدارة لهذا السيرفر.")


async def setup(bot: commands.Bot):
    # top_group (class attribute) بيتسجل تلقائياً مع الـ tree عند add_cog.
    await bot.add_cog(EconomyCog(bot))
