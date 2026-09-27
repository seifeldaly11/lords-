"""
كوج نظام التذاكر (Tickets) — منقول من bot-updated (commands/tickets/*.js).
"""
from __future__ import annotations

import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load, save

TICKET_SETTINGS_FILE = "ticket_settings"


def load_settings() -> dict:
    return load(TICKET_SETTINGS_FILE)


def save_settings(data: dict) -> None:
    save(TICKET_SETTINGS_FILE, data)


def get_ticket_category(guild_id: int) -> Optional[int]:
    settings = load_settings()
    cat = settings.get(str(guild_id), {}).get("ticket_category")
    return int(cat) if cat else None


class TicketPanelView(discord.ui.View):
    """الأزرار الدائمة (persistent) اللي بتظهر تحت رسالة إعداد التذاكر."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 فتح تذكرة", style=discord.ButtonStyle.primary, custom_id="lm_create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        existing = discord.utils.find(
            lambda c: c.name.startswith("ticket-") and c.topic and str(member.id) in c.topic,
            guild.text_channels,
        )
        if existing:
            return await interaction.response.send_message(f"❌ لديك تذكرة مفتوحة بالفعل: {existing.mention}", ephemeral=True)

        category_id = get_ticket_category(guild.id)
        category = guild.get_channel(category_id) if category_id else None
        ticket_number = random.randint(1000, 9999)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        try:
            ticket_channel = await guild.create_text_channel(
                f"ticket-{ticket_number}",
                category=category if isinstance(category, discord.CategoryChannel) else None,
                topic=f"تذكرة الخاصة بـ {member} ({member.id})",
                overwrites=overwrites,
            )
        except Exception:
            return await interaction.response.send_message("❌ حدث خطأ أثناء إنشاء التذكرة.", ephemeral=True)

        embed = discord.Embed(
            title=f"🎫 تذكرة #{ticket_number}",
            description="أهلاً بك! فريق الدعم هيتواصل معك قريباً.\nاضغط **مطالبة** لتولّي التذكرة أو **إغلاق** لإنهائها.",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        await ticket_channel.send(member.mention)
        await ticket_channel.send(embed=embed, view=TicketActionsView())
        await interaction.response.send_message(f"✅ تم فتح تذكرتك: {ticket_channel.mention}", ephemeral=True)


class TicketActionsView(discord.ui.View):
    """أزرار المطالبة والإغلاق داخل قناة التذكرة."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🙋 مطالبة", style=discord.ButtonStyle.primary, custom_id="lm_claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        if not channel.name.startswith("ticket-"):
            return await interaction.response.send_message("❌ هذا الزر يعمل فقط داخل قنوات التذاكر.", ephemeral=True)
        if channel.topic and "Claimed by" in channel.topic:
            return await interaction.response.send_message("ℹ️ التذكرة تمت مطالبتها بالفعل.", ephemeral=True)
        try:
            await channel.edit(topic=f"{channel.topic} | Claimed by: {interaction.user.id}")
        except Exception:
            pass
        embed = discord.Embed(
            title="✅ تمت مطالبة التذكرة",
            description=f"{interaction.user.mention} هيتابع طلبك الآن.",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=discord.utils.utcnow(),
        )
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="🔒 إغلاق", style=discord.ButtonStyle.danger, custom_id="lm_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        if not channel.name.startswith("ticket-"):
            return await interaction.response.send_message("❌ هذا الزر يعمل فقط داخل قنوات التذاكر.", ephemeral=True)

        member = interaction.user
        is_owner = channel.topic and str(member.id) in channel.topic
        if not member.guild_permissions.manage_channels and not is_owner:
            return await interaction.response.send_message("❌ ليس لديك صلاحية إغلاق هذه التذكرة.", ephemeral=True)

        embed = discord.Embed(
            title="🔒 سيتم إغلاق التذكرة",
            description="سيتم حذف هذه القناة خلال 5 ثوانٍ...",
            color=discord.Color.from_rgb(255, 255, 255),
        )
        await interaction.response.send_message(embed=embed)
        import asyncio

        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"تم إغلاق التذكرة بواسطة {member}")
        except Exception:
            pass


class TicketsCog(commands.Cog):
    """أوامر إعداد وإدارة نظام التذاكر — كلها تحت مجموعة واحدة /ticket."""

    ticket_group = app_commands.Group(
        name="ticket", description="🎫 نظام التذاكر | Ticket system",
        default_permissions=discord.Permissions(manage_channels=True),
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(TicketPanelView())
        bot.add_view(TicketActionsView())

    @ticket_group.command(name="setup", description="إعداد نظام التذاكر في قناة")
    @app_commands.describe(channel="القناة", title="عنوان الرسالة", description="وصف الرسالة", color="لون الإمبيد (hex اختياري)")
    @app_commands.guild_only()
    async def ticket_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str,
        color: Optional[str] = None,
    ):
        try:
            embed_color = discord.Color(int(color.lstrip("#"), 16)) if color else discord.Color.blue()
        except ValueError:
            embed_color = discord.Color.blue()

        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        try:
            await channel.send(embed=embed, view=TicketPanelView())
        except Exception:
            return await interaction.response.send_message("❌ حدث خطأ أثناء إرسال رسالة التذاكر.", ephemeral=True)

        await interaction.response.send_message(f"✅ تم إعداد نظام التذاكر في {channel.mention}.", ephemeral=True)

    @ticket_group.command(name="category", description="تحديد الفئة (Category) التي تفتح بها التذاكر")
    @app_commands.describe(category="الفئة")
    @app_commands.guild_only()
    async def ticket_category(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        settings = load_settings()
        settings.setdefault(str(interaction.guild.id), {})["ticket_category"] = category.id
        save_settings(settings)
        await interaction.response.send_message(f"✅ سيتم فتح التذاكر داخل فئة **{category.name}**.", ephemeral=True)

    @ticket_group.command(name="come", description="استدعاء عضو إلى التذكرة الحالية")
    @app_commands.describe(target="العضو المطلوب استدعاؤه")
    @app_commands.guild_only()
    async def come(self, interaction: discord.Interaction, target: discord.Member):
        if "ticket-" not in interaction.channel.name:
            return await interaction.response.send_message("❌ هذا الأمر يعمل فقط داخل قنوات التذاكر.", ephemeral=True)
        embed = discord.Embed(
            title="📣 استدعاء",
            description=f"تم استدعاء {target.mention} بواسطة {interaction.user.mention}.",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=discord.utils.utcnow(),
        )
        await interaction.response.send_message(content=target.mention, embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
