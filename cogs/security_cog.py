"""
كوج الحماية (Anti-Nuke) — منقول من bot-updated (utils/security.js + commands/security/*).
يوفّر: تشغيل/إيقاف حمايات (anti-bot, anti-spam, anti-role-grant, role/channel protection),
وايت ليست متقدم (bypass)، نسخ احتياطي واستعادة للرولات والقنوات، وحدود عقوبات
على حذف الرولات/القنوات.

ملاحظة: هذا الكوج مخصص فقط لمن حددهم DEVELOPER_IDS تحت (زي فكرة isDeveloper في
الأصل الجافاسكريبت). عدّل القائمة دي بأرقام الأيدي بتاعتك، أو زوّد شرط
`interaction.user.guild_permissions.administrator` لو عايز تسمح لمالك السيرفر كمان.
"""
from __future__ import annotations

import time
from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load, save
from cogs.subscription_cog import is_plan_active

SECURITY_FILE = "security_data"

# 🔧 عدّل هنا: أيدي المطورين المسموح لهم بأوامر الحماية.
DEVELOPER_IDS: set[int] = set()

DANGEROUS_PERMISSIONS = [
    "administrator",
    "ban_members",
    "kick_members",
    "manage_roles",
    "manage_channels",
    "manage_guild",
    "mention_everyone",
]

PROTECTION_KEYS = [
    "antiBot",
    "antiSpam",
    "antiRaid",
    "antiRoleGrant",
    "roleProtection",
    "channelProtection",
]

PROTECTION_CHOICES = [
    app_commands.Choice(name="مكافحة البوتات (Anti-Bot)", value="antiBot"),
    app_commands.Choice(name="مكافحة السبام (Anti-Spam)", value="antiSpam"),
    app_commands.Choice(name="مكافحة الريد (Anti-Raid)", value="antiRaid"),
    app_commands.Choice(name="مكافحة منح الرتب (Anti-Role Grant)", value="antiRoleGrant"),
    app_commands.Choice(name="حماية الرتب (Role Protection)", value="roleProtection"),
    app_commands.Choice(name="حماية القنوات (Channel Protection)", value="channelProtection"),
]

BYPASS_CHOICES = [
    app_commands.Choice(name="تجاوز كل الحمايات", value="BYPASS_ALL"),
    app_commands.Choice(name="تجاوز مكافحة البوتات", value="BYPASS_ANTI_BOT"),
    app_commands.Choice(name="تجاوز مكافحة السبام", value="BYPASS_ANTI_SPAM"),
    app_commands.Choice(name="تجاوز مكافحة منح الرتب", value="BYPASS_ANTI_ROLE_GRANT"),
    app_commands.Choice(name="تجاوز حماية الرتب", value="BYPASS_ROLE_PROTECTION"),
    app_commands.Choice(name="تجاوز حماية القنوات", value="BYPASS_CHANNEL_PROTECTION"),
]

ACTION_CHOICES = [
    app_commands.Choice(name="لا شيء (إشعار فقط)", value="none"),
    app_commands.Choice(name="طرد", value="kick"),
    app_commands.Choice(name="حظر", value="ban"),
]


def is_developer(user_id: int) -> bool:
    return user_id in DEVELOPER_IDS


def load_security() -> dict:
    data = load(SECURITY_FILE)
    data.setdefault("guilds", {})
    return data


def init_guild_data(guild_id: int) -> dict:
    data = load_security()
    gid = str(guild_id)
    guild_data = data["guilds"].setdefault(gid, {})
    guild_data.setdefault(
        "protection",
        {key: False for key in PROTECTION_KEYS},
    )
    guild_data.setdefault("advancedWhitelist", {"users": {}, "roles": {}})
    guild_data.setdefault("backups", {"roles": [], "channels": []})
    guild_data.setdefault(
        "limits",
        {
            "channelDelete": {"limit": 5, "action": "none"},
            "roleDelete": {"limit": 5, "action": "none"},
        },
    )
    guild_data.setdefault("violations", {})
    save(SECURITY_FILE, data)
    return guild_data


def save_guild_data(guild_id: int, guild_data: dict) -> None:
    data = load_security()
    data["guilds"][str(guild_id)] = guild_data
    save(SECURITY_FILE, data)


def has_bypass(member: discord.Member, guild_data: dict, permission: str) -> bool:
    if member is None:
        return False
    if is_developer(member.id) or member.id == member.guild.owner_id:
        return True
    wl = guild_data.get("advancedWhitelist", {"users": {}, "roles": {}})
    user_perms = wl.get("users", {}).get(str(member.id), [])
    if "BYPASS_ALL" in user_perms or permission in user_perms:
        return True
    for role in member.roles:
        role_perms = wl.get("roles", {}).get(str(role.id), [])
        if "BYPASS_ALL" in role_perms or permission in role_perms:
            return True
    return False


async def notify_and_log(guild: discord.Guild, embed: discord.Embed) -> None:
    try:
        owner = guild.owner or await guild.fetch_owner()
        if owner:
            await owner.send(embed=embed)
    except Exception:
        pass


def create_backups(guild: discord.Guild) -> None:
    guild_data = init_guild_data(guild.id)
    guild_data["backups"]["roles"] = [
        {
            "id": role.id,
            "name": role.name,
            "color": role.color.value,
            "permissions": role.permissions.value,
            "position": role.position,
            "hoist": role.hoist,
            "mentionable": role.mentionable,
        }
        for role in guild.roles
        if role.name != "@everyone"
    ]
    guild_data["backups"]["channels"] = [
        {
            "id": channel.id,
            "name": channel.name,
            "type": str(channel.type),
            "position": channel.position,
            "parent_id": channel.category_id,
        }
        for channel in guild.channels
    ]
    save_guild_data(guild.id, guild_data)


async def restore_roles(guild: discord.Guild, guild_data: dict) -> int:
    backups = guild_data.get("backups", {}).get("roles", [])
    if not backups:
        return 0
    existing_ids = {role.id for role in guild.roles}
    restored = 0
    for role_data in reversed(backups):
        if role_data["id"] in existing_ids:
            continue
        try:
            await guild.create_role(
                name=role_data["name"],
                permissions=discord.Permissions(role_data["permissions"]),
                colour=discord.Colour(role_data["color"]),
                hoist=role_data["hoist"],
                mentionable=role_data["mentionable"],
                reason="استعادة رتبة من النسخة الاحتياطية",
            )
            restored += 1
        except Exception:
            continue
    return restored


async def restore_channels(guild: discord.Guild, guild_data: dict) -> int:
    backups = guild_data.get("backups", {}).get("channels", [])
    if not backups:
        return 0
    existing_ids = {c.id for c in guild.channels}
    restored = 0
    categories = [c for c in backups if c["type"] == "category"]
    others = [c for c in backups if c["type"] != "category"]
    for channel_data in categories + others:
        if channel_data["id"] in existing_ids:
            continue
        try:
            if channel_data["type"] == "category":
                await guild.create_category(channel_data["name"], reason="استعادة قناة من النسخة الاحتياطية")
            elif channel_data["type"] == "voice":
                await guild.create_voice_channel(channel_data["name"], reason="استعادة قناة من النسخة الاحتياطية")
            else:
                await guild.create_text_channel(channel_data["name"], reason="استعادة قناة من النسخة الاحتياطية")
            restored += 1
        except Exception:
            continue
    return restored


class SecurityCog(commands.Cog):
    """أوامر الحماية وأنظمة مكافحة النيوك (anti-nuke)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._spam_map: dict[int, list[float]] = {}

    async def cog_check(self, ctx):  # not used for app commands, kept for clarity
        return True

    def _dev_only(self, interaction: discord.Interaction) -> bool:
        return is_developer(interaction.user.id) or interaction.user.id == interaction.guild.owner_id

    # ------------------------------------------------------------ /security
    # كل أوامر الحماية اتلمّت تحت مجموعة واحدة (/security) عشان توفّر من عدد
    # الأوامر الرئيسية المسموح بيها في ديسكورد (100 أمر لكل تطبيق).
    security_group = app_commands.Group(
        name="security", description="🛡️ نظام الحماية ومكافحة النيوك | Anti-nuke security system",
        default_permissions=discord.Permissions(administrator=True),
    )

    # -------------------------------------------------------- /protection
    protection_group = app_commands.Group(
        name="protection", description="⚙️ إعدادات الحماية | Protection settings",
        parent=security_group,
    )

    @protection_group.command(name="toggle", description="تشغيل/إيقاف نوع حماية | Toggle a protection")
    @app_commands.describe(type="نوع الحماية | Protection type")
    @app_commands.choices(type=PROTECTION_CHOICES)
    @app_commands.guild_only()
    async def protection_toggle(self, interaction: discord.Interaction, type: app_commands.Choice[str]):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        guild_data = init_guild_data(interaction.guild.id)
        guild_data["protection"][type.value] = not guild_data["protection"].get(type.value, False)
        save_guild_data(interaction.guild.id, guild_data)
        state = "مفعّلة ✅" if guild_data["protection"][type.value] else "متوقفة ❌"
        await interaction.response.send_message(f"الحماية `{type.value}` أصبحت {state}.\nProtection `{type.value}` is now {state}.", ephemeral=True)

    @protection_group.command(name="status", description="عرض حالة الحماية الحالية | View current protection status")
    @app_commands.guild_only()
    async def protection_status(self, interaction: discord.Interaction):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        guild_data = init_guild_data(interaction.guild.id)
        embed = discord.Embed(title="🛡️ حالة الحماية", color=discord.Color.from_rgb(255, 255, 255))
        for key, value in guild_data["protection"].items():
            embed.add_field(name=key, value="مفعّلة ✅" if value else "متوقفة ❌", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --------------------------------------------------------- /whitelist
    whitelist_group = app_commands.Group(
        name="whitelist", description="🔑 إدارة صلاحيات تجاوز الحماية | Advanced whitelist",
        parent=security_group,
    )

    @whitelist_group.command(name="grant-user", description="منح صلاحية تجاوز لمستخدم | Grant a bypass permission to a user")
    @app_commands.choices(permission=BYPASS_CHOICES)
    @app_commands.guild_only()
    async def whitelist_grant_user(self, interaction: discord.Interaction, user: discord.Member, permission: app_commands.Choice[str]):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        guild_data = init_guild_data(interaction.guild.id)
        perms = guild_data["advancedWhitelist"]["users"].setdefault(str(user.id), [])
        if permission.value in perms:
            return await interaction.response.send_message("ℹ️ هذه الصلاحية ممنوحة له بالفعل.\nℹ️ This permission is already granted.", ephemeral=True)
        perms.append(permission.value)
        save_guild_data(interaction.guild.id, guild_data)
        await interaction.response.send_message(f"✅ تم منح `{permission.value}` لـ {user.mention}.\n✅ Granted `{permission.value}` to {user.mention}.", ephemeral=True)

    @whitelist_group.command(name="grant-role", description="منح صلاحية تجاوز لرتبة | Grant a bypass permission to a role")
    @app_commands.choices(permission=BYPASS_CHOICES)
    @app_commands.guild_only()
    async def whitelist_grant_role(self, interaction: discord.Interaction, role: discord.Role, permission: app_commands.Choice[str]):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        guild_data = init_guild_data(interaction.guild.id)
        perms = guild_data["advancedWhitelist"]["roles"].setdefault(str(role.id), [])
        if permission.value in perms:
            return await interaction.response.send_message("ℹ️ هذه الصلاحية ممنوحة بالفعل.", ephemeral=True)
        perms.append(permission.value)
        save_guild_data(interaction.guild.id, guild_data)
        await interaction.response.send_message(f"✅ تم منح `{permission.value}` لرتبة {role.mention}.\n✅ Granted `{permission.value}` to role {role.mention}.", ephemeral=True)

    @whitelist_group.command(name="revoke-user", description="سحب صلاحية تجاوز من مستخدم | Revoke a user bypass permission")
    @app_commands.choices(permission=BYPASS_CHOICES)
    @app_commands.guild_only()
    async def whitelist_revoke_user(self, interaction: discord.Interaction, user: discord.Member, permission: app_commands.Choice[str]):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        guild_data = init_guild_data(interaction.guild.id)
        perms = guild_data["advancedWhitelist"]["users"].get(str(user.id), [])
        if permission.value not in perms:
            return await interaction.response.send_message("ℹ️ هذه الصلاحية غير ممنوحة أصلاً.\nℹ️ This permission is not currently granted.", ephemeral=True)
        perms.remove(permission.value)
        save_guild_data(interaction.guild.id, guild_data)
        await interaction.response.send_message(f"✅ تم سحب `{permission.value}` من {user.mention}.", ephemeral=True)

    @whitelist_group.command(name="view", description="عرض صلاحيات الوايت ليست الحالية | View current whitelist permissions")
    @app_commands.guild_only()
    async def whitelist_view(self, interaction: discord.Interaction):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        guild_data = init_guild_data(interaction.guild.id)
        wl = guild_data["advancedWhitelist"]
        embed = discord.Embed(title="🔑 صلاحيات الوايت ليست", color=discord.Color.from_rgb(255, 255, 255))
        users_text = "\n".join(f"<@{uid}>: `{', '.join(perms)}`" for uid, perms in wl["users"].items()) or "لا يوجد"
        roles_text = "\n".join(f"<@&{rid}>: `{', '.join(perms)}`" for rid, perms in wl["roles"].items()) or "لا يوجد"
        embed.add_field(name="المستخدمون", value=users_text, inline=False)
        embed.add_field(name="الرتب", value=roles_text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------ /backup
    backup_group = app_commands.Group(
        name="backup", description="💾 إدارة النسخ الاحتياطي | Manage backups",
        parent=security_group,
    )

    @backup_group.command(name="create", description="إنشاء نسخة احتياطية للرولات والقنوات | Back up roles and channels")
    @app_commands.guild_only()
    async def backup_create(self, interaction: discord.Interaction):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        create_backups(interaction.guild)
        await interaction.followup.send("✅ تم إنشاء نسخة احتياطية.\n✅ Backup created.")

    @backup_group.command(name="restore-roles", description="استعادة الرولات المفقودة من آخر نسخة | Restore missing roles from the latest backup")
    @app_commands.guild_only()
    async def backup_restore_roles(self, interaction: discord.Interaction):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        guild_data = init_guild_data(interaction.guild.id)
        count = await restore_roles(interaction.guild, guild_data)
        await interaction.followup.send(f"✅ تم استعادة {count} رتبة.")

    @backup_group.command(name="restore-channels", description="استعادة القنوات المفقودة من آخر نسخة | Restore missing channels from the latest backup")
    @app_commands.guild_only()
    async def backup_restore_channels(self, interaction: discord.Interaction):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        guild_data = init_guild_data(interaction.guild.id)
        count = await restore_channels(interaction.guild, guild_data)
        await interaction.followup.send(f"✅ تم استعادة {count} قناة.")

    @backup_group.command(name="info", description="معلومات عن آخر نسخة احتياطية | View the latest backup details")
    @app_commands.guild_only()
    async def backup_info(self, interaction: discord.Interaction):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        guild_data = init_guild_data(interaction.guild.id)
        roles_count = len(guild_data["backups"]["roles"])
        channels_count = len(guild_data["backups"]["channels"])
        embed = discord.Embed(
            title="💾 معلومات النسخة الاحتياطية",
            description=f"عدد الرولات المحفوظة: **{roles_count}**\nعدد القنوات المحفوظة: **{channels_count}**",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=discord.utils.utcnow(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------ /limit-settings
    @security_group.command(name="limit-settings", description="ضبط حدود العقوبة على حذف الرولات/القنوات | Configure deletion limits and punishments")
    @app_commands.describe(type="نوع الإجراء | Action type", limit="العدد المسموح خلال ساعة | Allowed count per hour", action="العقوبة عند تجاوز الحد | Punishment after the limit")
    @app_commands.choices(
        type=[
            app_commands.Choice(name="حذف القنوات", value="channelDelete"),
            app_commands.Choice(name="حذف الرولات", value="roleDelete"),
        ],
        action=ACTION_CHOICES,
    )
    @app_commands.guild_only()
    async def limit_settings(
        self,
        interaction: discord.Interaction,
        type: app_commands.Choice[str],
        limit: app_commands.Range[int, 1, 1000],
        action: app_commands.Choice[str],
    ):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        guild_data = init_guild_data(interaction.guild.id)
        guild_data["limits"][type.value] = {"limit": limit, "action": action.value}
        save_guild_data(interaction.guild.id, guild_data)
        await interaction.response.send_message(
            f"✅ تم ضبط `{type.value}`: الحد {limit} والعقوبة `{action.value}`.", ephemeral=True
        )

    # ---------------------------------------------------------- /togglepro
    @security_group.command(name="togglepro", description="تفعيل/تعطيل كل الحمايات دفعة واحدة | Enable or disable all protections")
    @app_commands.describe(enable="تفعيل أو تعطيل | Enable or disable")
    @app_commands.guild_only()
    async def togglepro(self, interaction: discord.Interaction, enable: bool):
        if not self._dev_only(interaction):
            return await interaction.response.send_message("🔒 هذا الأمر للمطورين/مالك السيرفر فقط.\n🔒 Developer/server owner only.", ephemeral=True)
        guild_data = init_guild_data(interaction.guild.id)
        for key in guild_data["protection"]:
            guild_data["protection"][key] = enable
        save_guild_data(interaction.guild.id, guild_data)
        if enable:
            create_backups(interaction.guild)
        title = "✅ تم تفعيل الحماية الكاملة" if enable else "❌ تم تعطيل الحماية الكاملة"
        embed = discord.Embed(title=title, description=f"بواسطة: {interaction.user}", color=discord.Color.from_rgb(255, 255, 255))
        await interaction.response.send_message(embed=embed)
        await notify_and_log(interaction.guild, embed)

    # ------------------------------------------------------- event listeners
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if not is_plan_active(message.guild.id, "protection"):
            return
        guild_data = init_guild_data(message.guild.id)
        if not guild_data["protection"].get("antiSpam"):
            return
        member = message.guild.get_member(message.author.id)
        if member and has_bypass(member, guild_data, "BYPASS_ANTI_SPAM"):
            return
        now = time.time()
        history = self._spam_map.setdefault(message.author.id, [])
        history.append(now)
        recent = [t for t in history if now - t < 5]
        self._spam_map[message.author.id] = recent
        if len(recent) > 5:
            try:
                await member.timeout(discord.utils.utcnow() + timedelta(minutes=5), reason="مكافحة السبام")
                embed = discord.Embed(
                    title="🚫 مكافحة السبام",
                    description=f"تم إسكات {member.mention} لمدة 5 دقائق بسبب السبام.",
                    color=discord.Color.from_rgb(255, 255, 255),
                )
                await notify_and_log(message.guild, embed)
                self._spam_map[message.author.id] = []
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot:
            return
        if not is_plan_active(member.guild.id, "protection"):
            return
        guild_data = init_guild_data(member.guild.id)
        if not guild_data["protection"].get("antiBot"):
            return
        try:
            async for entry in member.guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
                if entry.target and entry.target.id == member.id:
                    inviter = member.guild.get_member(entry.user.id)
                    if inviter and not has_bypass(inviter, guild_data, "BYPASS_ANTI_BOT"):
                        await member.ban(reason="مكافحة البوتات: بوت غير موثوق")
                        roles = [r for r in inviter.roles if not r.managed and r.name != "@everyone"]
                        if roles:
                            await inviter.remove_roles(*roles, reason="مكافحة البوتات: سحب الرولات من الداعي")
                        embed = discord.Embed(
                            title="🚫 مكافحة البوتات",
                            description=f"تم حظر البوت {member} وسحب رتب {inviter.mention} لأنه دعاه.",
                            color=discord.Color.from_rgb(255, 255, 255),
                        )
                        await notify_and_log(member.guild, embed)
                    break
        except Exception:
            pass

    async def _handle_dangerous_delete(self, guild: discord.Guild, action_key: str, protection_key: str, audit_action, target_id: int, target_name: str):
        if not is_plan_active(guild.id, "protection"):
            return
        guild_data = init_guild_data(guild.id)
        if not guild_data["protection"].get(protection_key):
            return
        try:
            async for entry in guild.audit_logs(limit=5, action=audit_action):
                if entry.target and getattr(entry.target, "id", None) == target_id:
                    deleter = guild.get_member(entry.user.id)
                    if not deleter or has_bypass(deleter, guild_data, f"BYPASS_{protection_key.upper()}"):
                        return
                    settings = guild_data["limits"][action_key]
                    violations = guild_data["violations"].setdefault(str(deleter.id), {"channelDelete": [], "roleDelete": []})
                    now = time.time()
                    violations[action_key] = [t for t in violations[action_key] if now - t < 3600] + [now]
                    count = len(violations[action_key])
                    save_guild_data(guild.id, guild_data)

                    embed = discord.Embed(
                        title="🚨 تنبيه حماية",
                        description=f"تم حذف **{target_name}** بواسطة {deleter.mention}.\nعدد المخالفات: {count}/{settings['limit']}",
                        color=discord.Color.from_rgb(255, 255, 255),
                    )
                    await notify_and_log(guild, embed)

                    if count >= settings["limit"] and settings["action"] != "none":
                        try:
                            if settings["action"] == "kick":
                                await deleter.kick(reason="تجاوز حد الحذف المسموح")
                            elif settings["action"] == "ban":
                                await deleter.ban(reason="تجاوز حد الحذف المسموح")
                            violations[action_key] = []
                            save_guild_data(guild.id, guild_data)
                        except Exception:
                            pass
                    break
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        await self._handle_dangerous_delete(
            channel.guild, "channelDelete", "channelProtection",
            discord.AuditLogAction.channel_delete, channel.id, channel.name,
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await self._handle_dangerous_delete(
            role.guild, "roleDelete", "roleProtection",
            discord.AuditLogAction.role_delete, role.id, role.name,
        )


async def setup(bot: commands.Bot):
    # ملاحظة: الـ app_commands.Group المعرّفة كـ class attribute (protection_group,
    # whitelist_group, backup_group) بتتسجّل تلقائياً مع الـ tree لما نعمل add_cog،
    # فمفيش داعي لاستدعاء bot.tree.add_command يدوياً هنا.
    await bot.add_cog(SecurityCog(bot))
