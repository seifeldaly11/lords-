"""
كوج الإشراف (Moderation) — منقول من بوت JavaScript (bot-updated) إلى Python/discord.py.
يغطي: ban, unban, kick, mute, unmute, timeout, untimeout, vmute, vunmute,
warn, warnings, clear-warnings, clear, lock, unlock, hide, unhide,
slowmode, role, nuke.
"""
from __future__ import annotations

import re
import time
from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load, save

WARNINGS_FILE = "warnings"


def _no_reason() -> str:
    return "لم يُذكر سبب"


def load_warnings() -> dict:
    data = load(WARNINGS_FILE)
    data.setdefault("guilds", {})
    return data


def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    data = load_warnings()
    guild_warns = data["guilds"].setdefault(str(guild_id), {})
    user_warns = guild_warns.setdefault(str(user_id), [])
    user_warns.append(
        {
            "id": str(int(time.time() * 1000)),
            "moderatorId": str(moderator_id),
            "reason": reason,
            "timestamp": time.time(),
        }
    )
    save(WARNINGS_FILE, data)
    return len(user_warns)


def get_warnings(guild_id: int, user_id: int) -> list:
    data = load_warnings()
    return data["guilds"].get(str(guild_id), {}).get(str(user_id), [])


def clear_warnings(guild_id: int, user_id: int) -> int:
    data = load_warnings()
    guild_warns = data["guilds"].get(str(guild_id), {})
    warns = guild_warns.pop(str(user_id), [])
    save(WARNINGS_FILE, data)
    return len(warns)


DURATION_RE = re.compile(r"^(\d+)\s*([smhdw])$", re.IGNORECASE)
DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_duration(text: str) -> Optional[int]:
    """يفسّر مدد زمنية بسيطة زي 10m / 1h / 1d وترجع الثواني."""
    match = DURATION_RE.match(text.strip())
    if not match:
        return None
    amount, unit = match.groups()
    return int(amount) * DURATION_UNITS[unit.lower()]


class ModerationCog(commands.Cog):
    """أوامر الإشراف الأساسية (بان، طرد، إسكات، تحذيرات...) — كلها تحت مجموعة واحدة /mod
    عشان توفّر من عدد الأوامر الرئيسية المسموح بيها في ديسكورد (100 أمر لكل تطبيق)."""

    mod_group = app_commands.Group(
        name="mod",
        description="🛡️ أوامر الإشراف (بان، طرد، إسكات، تحذيرات...) | Moderation tools",
        default_permissions=discord.Permissions(moderate_members=True),
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    async def _require(interaction: discord.Interaction, **perms: bool) -> bool:
        """يتأكد إن العضو معاه الصلاحية المطلوبة، ولو لأ يرد برسالة خطأ ويرجع False."""
        missing = [p for p, needed in perms.items() if needed and not getattr(interaction.user.guild_permissions, p, False)]
        if missing:
            await interaction.response.send_message(
                f"❌ محتاج صلاحية `{', '.join(missing)}` عشان تستخدم الأمر ده.", ephemeral=True
            )
            return False
        return True

    # ---------------------------------------------------------------- ban
    @mod_group.command(name="ban", description="حظر عضو من السيرفر | Ban a user")
    @app_commands.describe(target="العضو", reason="السبب")
    @app_commands.guild_only()
    async def ban(self, interaction: discord.Interaction, target: discord.User, reason: Optional[str] = None):
        if not await self._require(interaction, ban_members=True):
            return
        reason = reason or _no_reason()
        member = interaction.guild.get_member(target.id)
        try:
            if member is not None:
                if member.top_role >= interaction.guild.me.top_role:
                    return await interaction.response.send_message("❌ لا أستطيع حظر هذا العضو.", ephemeral=True)
            await interaction.guild.ban(target, reason=reason)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ لا أملك صلاحية حظر هذا العضو.", ephemeral=True)
        except Exception:
            return await interaction.response.send_message("❌ حدث خطأ أثناء الحظر.", ephemeral=True)

        embed = discord.Embed(title="🔨 تم الحظر", color=discord.Color.from_rgb(255, 255, 255), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="العضو المحظور", value=f"{target} ({target.id})", inline=True)
        embed.add_field(name="بواسطة", value=str(interaction.user), inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    @mod_group.command(name="unban", description="إلغاء حظر عضو | Unban a user")
    @app_commands.describe(user_id="أيدي العضو", reason="السبب")
    @app_commands.guild_only()
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: Optional[str] = None):
        if not await self._require(interaction, ban_members=True):
            return
        reason = reason or _no_reason()
        try:
            await interaction.guild.unban(discord.Object(id=int(user_id)), reason=reason)
        except Exception:
            return await interaction.response.send_message("❌ تعذّر إلغاء الحظر (تأكد من الأيدي).", ephemeral=True)
        embed = discord.Embed(title="✅ تم إلغاء الحظر", color=discord.Color.from_rgb(255, 255, 255), timestamp=discord.utils.utcnow())
        embed.add_field(name="الأيدي", value=user_id, inline=True)
        embed.add_field(name="بواسطة", value=str(interaction.user), inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------------------- kick
    @mod_group.command(name="kick", description="طرد عضو من السيرفر | Kick a user")
    @app_commands.describe(target="العضو", reason="السبب")
    @app_commands.guild_only()
    async def kick(self, interaction: discord.Interaction, target: discord.Member, reason: Optional[str] = None):
        if not await self._require(interaction, kick_members=True):
            return
        reason = reason or _no_reason()
        if target.top_role >= interaction.guild.me.top_role or target.id == interaction.guild.owner_id:
            return await interaction.response.send_message("❌ لا أستطيع طرد هذا العضو.", ephemeral=True)
        try:
            await target.kick(reason=reason)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ لا أملك صلاحية الطرد.", ephemeral=True)
        embed = discord.Embed(title="👢 تم الطرد", color=discord.Color.from_rgb(255, 255, 255), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="العضو المطرود", value=f"{target} ({target.id})", inline=True)
        embed.add_field(name="بواسطة", value=str(interaction.user), inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------- mute (28d)
    @mod_group.command(name="mute", description="إسكات عضو لمدة 28 يوم | Mute a user (28 days)")
    @app_commands.describe(target="العضو", reason="السبب")
    @app_commands.guild_only()
    async def mute(self, interaction: discord.Interaction, target: discord.Member, reason: Optional[str] = None):
        if not await self._require(interaction, moderate_members=True):
            return
        reason = reason or _no_reason()
        try:
            await target.timeout(discord.utils.utcnow() + timedelta(days=28), reason=reason)
        except Exception:
            return await interaction.response.send_message("❌ تعذّر إسكات هذا العضو.", ephemeral=True)
        embed = discord.Embed(title="🔇 تم الإسكات (28 يوم)", color=discord.Color.from_rgb(255, 255, 255), timestamp=discord.utils.utcnow())
        embed.add_field(name="العضو", value=f"{target} ({target.id})", inline=True)
        embed.add_field(name="بواسطة", value=str(interaction.user), inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    @mod_group.command(name="unmute", description="إزالة الإسكات عن عضو | Unmute a user")
    @app_commands.describe(target="العضو", reason="السبب")
    @app_commands.guild_only()
    async def unmute(self, interaction: discord.Interaction, target: discord.Member, reason: Optional[str] = None):
        if not await self._require(interaction, moderate_members=True):
            return
        reason = reason or _no_reason()
        if not target.is_timed_out():
            return await interaction.response.send_message("ℹ️ هذا العضو غير مسكت أصلاً.", ephemeral=True)
        try:
            await target.timeout(None, reason=reason)
        except Exception:
            return await interaction.response.send_message("❌ تعذّر إزالة الإسكات.", ephemeral=True)
        embed = discord.Embed(title="🔊 تم رفع الإسكات", color=discord.Color.from_rgb(255, 255, 255), timestamp=discord.utils.utcnow())
        embed.add_field(name="العضو", value=str(target), inline=True)
        embed.add_field(name="بواسطة", value=str(interaction.user), inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------- timeout
    @mod_group.command(name="timeout", description="إسكات عضو لمدة محددة | Timeout a user for a duration")
    @app_commands.describe(target="العضو", duration="المدة (مثال: 10m, 1h, 1d)", reason="السبب")
    @app_commands.guild_only()
    async def timeout(self, interaction: discord.Interaction, target: discord.Member, duration: str, reason: Optional[str] = None):
        if not await self._require(interaction, moderate_members=True):
            return
        reason = reason or _no_reason()
        seconds = parse_duration(duration)
        if not seconds or seconds < 10 or seconds > 2419200:
            return await interaction.response.send_message(
                "❌ مدة غير صالحة. استخدم صيغة زي 10m أو 1h أو 1d (من 10 ثواني حتى 28 يوم).", ephemeral=True
            )
        try:
            await target.timeout(discord.utils.utcnow() + timedelta(seconds=seconds), reason=reason)
        except Exception:
            return await interaction.response.send_message("❌ تعذّر تنفيذ الإسكات.", ephemeral=True)
        embed = discord.Embed(title="⏳ تم الإسكات المؤقت", color=discord.Color.from_rgb(255, 255, 255), timestamp=discord.utils.utcnow())
        embed.add_field(name="العضو", value=f"{target} ({target.id})", inline=True)
        embed.add_field(name="المدة", value=duration, inline=True)
        embed.add_field(name="بواسطة", value=str(interaction.user), inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    @mod_group.command(name="untimeout", description="إزالة الإسكات المؤقت عن عضو | Remove timeout")
    @app_commands.describe(target="العضو", reason="السبب")
    @app_commands.guild_only()
    async def untimeout(self, interaction: discord.Interaction, target: discord.Member, reason: Optional[str] = None):
        if not await self._require(interaction, moderate_members=True):
            return
        reason = reason or _no_reason()
        if not target.is_timed_out():
            return await interaction.response.send_message("ℹ️ هذا العضو ليس عليه إسكات مؤقت.", ephemeral=True)
        try:
            await target.timeout(None, reason=reason)
        except Exception:
            return await interaction.response.send_message("❌ تعذّر إزالة الإسكات.", ephemeral=True)
        embed = discord.Embed(title="✅ تم إلغاء الإسكات المؤقت", color=discord.Color.from_rgb(255, 255, 255), timestamp=discord.utils.utcnow())
        embed.add_field(name="العضو", value=f"{target} ({target.id})", inline=True)
        embed.add_field(name="بواسطة", value=str(interaction.user), inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------------- voice mute
    @mod_group.command(name="vmute", description="إسكات عضو في الروم الصوتي | Voice mute a user")
    @app_commands.describe(target="العضو", reason="السبب")
    @app_commands.guild_only()
    async def vmute(self, interaction: discord.Interaction, target: discord.Member, reason: Optional[str] = None):
        if not await self._require(interaction, mute_members=True):
            return
        reason = reason or _no_reason()
        if target.voice is None or target.voice.channel is None:
            return await interaction.response.send_message("❌ هذا العضو مش في روم صوتي.", ephemeral=True)
        try:
            await target.edit(mute=True, reason=reason)
        except Exception:
            return await interaction.response.send_message("❌ تعذّر تنفيذ الإسكات الصوتي.", ephemeral=True)
        embed = discord.Embed(title="🔇 إسكات صوتي", color=discord.Color.from_rgb(255, 255, 255), timestamp=discord.utils.utcnow())
        embed.add_field(name="العضو", value=str(target), inline=True)
        embed.add_field(name="بواسطة", value=str(interaction.user), inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    @mod_group.command(name="vunmute", description="إزالة الإسكات الصوتي | Voice unmute a user")
    @app_commands.describe(target="العضو")
    @app_commands.guild_only()
    async def vunmute(self, interaction: discord.Interaction, target: discord.Member):
        if not await self._require(interaction, mute_members=True):
            return
        if target.voice is None or target.voice.channel is None:
            return await interaction.response.send_message("❌ هذا العضو مش في روم صوتي.", ephemeral=True)
        try:
            await target.edit(mute=False, reason="Voice unmute")
        except Exception:
            return await interaction.response.send_message("❌ تعذّر إزالة الإسكات الصوتي.", ephemeral=True)
        await interaction.response.send_message(f"✅ تم إلغاء الإسكات الصوتي عن {target.mention}.")

    # --------------------------------------------------------------- warn
    @mod_group.command(name="warn", description="تحذير عضو | Warn a user")
    @app_commands.describe(target="العضو", reason="السبب")
    @app_commands.guild_only()
    async def warn(self, interaction: discord.Interaction, target: discord.User, reason: str):
        if not await self._require(interaction, moderate_members=True):
            return
        if target.bot:
            return await interaction.response.send_message("❌ لا يمكن تحذير بوت.", ephemeral=True)
        count = add_warning(interaction.guild_id, target.id, interaction.user.id, reason)
        embed = discord.Embed(title="⚠️ تم تسجيل تحذير", color=discord.Color.from_rgb(255, 255, 255), timestamp=discord.utils.utcnow())
        embed.add_field(name="العضو", value=f"{target.mention} ({target.id})", inline=True)
        embed.add_field(name="عدد التحذيرات", value=str(count), inline=True)
        embed.add_field(name="بواسطة", value=str(interaction.user), inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        try:
            await target.send(f"⚠️ تم تحذيرك في **{interaction.guild.name}**.\nالسبب: {reason}\nعدد تحذيراتك الآن: {count}")
        except Exception:
            pass

    @mod_group.command(name="warnings", description="عرض تحذيرات عضو | View a user's warnings")
    @app_commands.describe(target="العضو")
    @app_commands.guild_only()
    async def warnings_cmd(self, interaction: discord.Interaction, target: discord.User):
        if not await self._require(interaction, moderate_members=True):
            return
        warns = get_warnings(interaction.guild_id, target.id)
        if not warns:
            return await interaction.response.send_message(f"ℹ️ لا توجد تحذيرات مسجلة على {target}.", ephemeral=True)
        embed = discord.Embed(
            title=f"تحذيرات {target}",
            description=f"إجمالي التحذيرات: {len(warns)}",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=discord.utils.utcnow(),
        )
        for i, warn in enumerate(warns, start=1):
            ts = int(warn.get("timestamp", 0))
            embed.add_field(
                name=f"تحذير #{i}",
                value=f"السبب: {warn.get('reason')}\nبواسطة: <@{warn.get('moderatorId')}>\n<t:{ts}:R>",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @mod_group.command(name="clear-warnings", description="مسح جميع تحذيرات عضو | Clear all warnings of a user")
    @app_commands.describe(target="العضو")
    @app_commands.guild_only()
    async def clear_warnings_cmd(self, interaction: discord.Interaction, target: discord.User):
        if not await self._require(interaction, moderate_members=True):
            return
        count = clear_warnings(interaction.guild_id, target.id)
        if count == 0:
            return await interaction.response.send_message(f"ℹ️ لا توجد تحذيرات لـ {target}.", ephemeral=True)
        embed = discord.Embed(
            title="🧹 تم مسح التحذيرات",
            description=f"تم مسح {count} تحذير عن {target.mention}.",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="بواسطة", value=str(interaction.user))
        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------------- clear
    @mod_group.command(name="clear", description="حذف عدد من الرسائل | Delete a number of messages")
    @app_commands.describe(amount="عدد الرسائل (1-100)")
    @app_commands.guild_only()
    async def clear(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
        if not await self._require(interaction, manage_messages=True):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=amount)
        except Exception:
            return await interaction.followup.send("❌ حدث خطأ أثناء حذف الرسائل.", ephemeral=True)
        await interaction.followup.send(f"✅ تم حذف {len(deleted)} رسالة بنجاح!", ephemeral=True)

    # --------------------------------------------------------- lock/unlock
    @mod_group.command(name="lock", description="قفل القناة الحالية | Lock the current channel")
    @app_commands.guild_only()
    async def lock(self, interaction: discord.Interaction):
        if not await self._require(interaction, manage_channels=True):
            return
        try:
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        except Exception:
            return await interaction.response.send_message("❌ حدث خطأ أثناء قفل القناة.", ephemeral=True)
        await interaction.response.send_message("🔒 تم قفل القناة!")

    @mod_group.command(name="unlock", description="فتح القناة الحالية | Unlock the current channel")
    @app_commands.guild_only()
    async def unlock(self, interaction: discord.Interaction):
        if not await self._require(interaction, manage_channels=True):
            return
        try:
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=None)
        except Exception:
            return await interaction.response.send_message("❌ حدث خطأ أثناء فتح القناة.", ephemeral=True)
        await interaction.response.send_message("🔓 تم فتح القناة!")

    @mod_group.command(name="hide", description="إخفاء القناة عن الجميع | Hide the current channel")
    @app_commands.guild_only()
    async def hide(self, interaction: discord.Interaction):
        if not await self._require(interaction, manage_channels=True):
            return
        try:
            await interaction.channel.set_permissions(interaction.guild.default_role, view_channel=False)
        except Exception:
            return await interaction.response.send_message("❌ حدث خطأ أثناء إخفاء القناة.", ephemeral=True)
        await interaction.response.send_message("🙈 تم إخفاء القناة عن الجميع بنجاح.")

    @mod_group.command(name="unhide", description="إظهار القناة للجميع | Unhide the current channel")
    @app_commands.guild_only()
    async def unhide(self, interaction: discord.Interaction):
        if not await self._require(interaction, manage_channels=True):
            return
        try:
            await interaction.channel.set_permissions(interaction.guild.default_role, view_channel=True)
        except Exception:
            return await interaction.response.send_message("❌ حدث خطأ أثناء إظهار القناة.", ephemeral=True)
        await interaction.response.send_message("👁️ تم إظهار القناة للجميع بنجاح.")

    # ------------------------------------------------------------ slowmode
    @mod_group.command(name="slowmode", description="ضبط الوضع البطيء | Set slowmode for the channel")
    @app_commands.describe(seconds="المدة بالثواني (0 للتعطيل، حتى 21600)")
    @app_commands.guild_only()
    async def slowmode(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
        if not await self._require(interaction, manage_channels=True):
            return
        try:
            await interaction.channel.edit(slowmode_delay=seconds)
        except Exception:
            return await interaction.response.send_message("❌ حدث خطأ أثناء ضبط الوضع البطيء.", ephemeral=True)
        if seconds == 0:
            await interaction.response.send_message("✅ تم تعطيل الوضع البطيء!")
        else:
            await interaction.response.send_message(f"✅ تم ضبط الوضع البطيء على {seconds} ثانية!")

    # ---------------------------------------------------------------- role
    @mod_group.command(name="role", description="منح/سحب رتبة من عضو | Add or remove a role from a user")
    @app_commands.describe(target="العضو", role="الرتبة")
    @app_commands.guild_only()
    async def role(self, interaction: discord.Interaction, target: discord.Member, role: discord.Role):
        if not await self._require(interaction, manage_roles=True):
            return
        if role.position >= interaction.guild.me.top_role.position:
            return await interaction.response.send_message("❌ لا يمكنني التحكم بهذه الرتبة لأنها أعلى من رتبتي.", ephemeral=True)
        try:
            if role in target.roles:
                await target.remove_roles(role)
                await interaction.response.send_message(f"✅ تم سحب رتبة **{role.name}** من **{target}**.")
            else:
                await target.add_roles(role)
                await interaction.response.send_message(f"✅ تم منح رتبة **{role.name}** لـ **{target}**.")
        except Exception:
            await interaction.response.send_message("❌ حدث خطأ أثناء تعديل الرتب.", ephemeral=True)

    # ---------------------------------------------------------------- nuke
    @mod_group.command(name="nuke", description="مسح كل رسائل القناة بإعادة إنشائها | Clear all messages by recreating the channel")
    @app_commands.guild_only()
    async def nuke(self, interaction: discord.Interaction):
        if not await self._require(interaction, manage_channels=True):
            return
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("❌ هذا الأمر يعمل فقط في القنوات النصية.", ephemeral=True)
        await interaction.response.send_message("💥 جاري تنفيذ النيوك...", ephemeral=True)
        try:
            new_channel = await channel.clone(reason=f"Nuke by {interaction.user}")
            position = channel.position
            await channel.delete(reason=f"Nuke by {interaction.user}")
            await new_channel.edit(position=position)
            await new_channel.send("💥 تم عمل نيوك للقناة بنجاح! | Channel has been nuked!")
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
