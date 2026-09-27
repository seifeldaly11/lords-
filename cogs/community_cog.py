"""
كوج المجتمع والأدوات العامة — منقول من bot-updated:
- utility/announce.js, autoresponse.js, review.js, setreviewchannel.js, suggestion.js
- general/avatar.js, banner.js, botinfo.js, emojis.js, invite.js, membercount.js,
  ping.js, roles.js, serverinfo.js, uptime.js, userinfo.js

ملاحظة: صورة "بطاقة الاقتراح" المولّدة بالـ canvas في الأصل الجافاسكريبت
(utils/renderSuggestion.js) اتستبدلت هنا بـ embed نصي بسيط + تفاعلات 👍/👎
لتفادي الاعتماد على مكتبات رسم صور غير متاحة افتراضياً في بيئة بايثون.
"""
from __future__ import annotations

import os
import platform
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load, save

AUTORESPONSES_FILE = "autoresponses"
REVIEW_SETTINGS_FILE = "review_settings"

BOT_START_TIME = time.time()


# ----------------------------------------------------------- autoresponses
def load_autoresponses() -> dict:
    return load(AUTORESPONSES_FILE)


def save_autoresponses(data: dict) -> None:
    save(AUTORESPONSES_FILE, data)


def get_review_channel(guild_id: int) -> Optional[int]:
    settings = load(REVIEW_SETTINGS_FILE)
    cid = settings.get(str(guild_id), {}).get("review_channel_id")
    return int(cid) if cid else None


def set_review_channel(guild_id: int, channel_id: int) -> None:
    settings = load(REVIEW_SETTINGS_FILE)
    settings.setdefault(str(guild_id), {})["review_channel_id"] = channel_id
    save(REVIEW_SETTINGS_FILE, settings)


class ReviewModal(discord.ui.Modal, title="اكتب تقييمك"):
    review_text = discord.ui.TextInput(
        label="رأيك",
        style=discord.TextStyle.paragraph,
        placeholder="شاركنا تجربتك بالتفصيل...",
        required=True,
        min_length=5,
        max_length=1000,
    )

    def __init__(self, stars: int):
        super().__init__()
        self.stars = stars

    async def on_submit(self, interaction: discord.Interaction):
        star_display = "⭐" * self.stars + "☆" * (5 - self.stars)
        color = discord.Color.green() if self.stars >= 4 else (discord.Color.gold() if self.stars >= 2 else discord.Color.red())
        embed = discord.Embed(title="📝 تقييم جديد", color=color, timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="التقييم", value=f"{star_display} ({self.stars}/5)", inline=True)
        embed.add_field(name="العضو", value=interaction.user.mention, inline=True)
        embed.add_field(name="الرأي", value=self.review_text.value, inline=False)
        embed.set_footer(text=f"ID: {interaction.user.id}")

        channel_id = get_review_channel(interaction.guild_id)
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        if channel:
            await channel.send(embed=embed)

        await interaction.response.send_message(f"🙏 شكراً على تقييمك بـ {self.stars} نجوم!", ephemeral=True)


class ReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for stars in range(1, 6):
            self.add_item(self._make_button(stars))

    def _make_button(self, stars: int) -> discord.ui.Button:
        button = discord.ui.Button(label="⭐" * stars, style=discord.ButtonStyle.primary, custom_id=f"lm_rate_{stars}")

        async def callback(interaction: discord.Interaction, stars=stars):
            await interaction.response.send_modal(ReviewModal(stars))

        button.callback = callback
        return button


class CommunityCog(commands.Cog):
    """أدوات إشراف عامة + معلومات السيرفر/الأعضاء + الردود التلقائية والتقييمات."""

    community_group = app_commands.Group(
        name="community", description="📣 إعلانات، ردود تلقائية، وتقييمات | Announcements, autoresponses & reviews",
        default_permissions=discord.Permissions(manage_messages=True),
    )
    info_group = app_commands.Group(
        name="util", description="🧰 معلومات عامة (السيرفر/الأعضاء/البوت) | General utility commands",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(ReviewView())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        responses = load_autoresponses()
        guild_responses = responses.get(str(message.guild.id), {})
        if not guild_responses:
            return
        content = message.content.lower()
        for trigger, response in guild_responses.items():
            if trigger.lower() in content:
                try:
                    await message.reply(response)
                except Exception:
                    pass
                break

    # ----------------------------------------------------------- announce
    @community_group.command(name="announce", description="إرسال إعلان في القناة الحالية")
    @app_commands.describe(message="نص الإعلان")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def announce(self, interaction: discord.Interaction, message: str):
        embed = discord.Embed(title="📢 إعلان", description=message, color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.set_footer(text=f"بواسطة {interaction.user}")
        await interaction.response.send_message("✅ تم إرسال الإعلان.", ephemeral=True)
        await interaction.channel.send(embed=embed)

    # ------------------------------------------------------- autoresponse
    autoresponse_group = app_commands.Group(
        name="autoresponse", description="🤖 إدارة الردود التلقائية",
        parent=community_group,
    )

    @autoresponse_group.command(name="add", description="إضافة رد تلقائي جديد")
    @app_commands.describe(trigger="الكلمة المفتاحية", response="الرد التلقائي")
    @app_commands.guild_only()
    async def autoresponse_add(self, interaction: discord.Interaction, trigger: str, response: str):
        data = load_autoresponses()
        data.setdefault(str(interaction.guild.id), {})[trigger.lower()] = response
        save_autoresponses(data)
        await interaction.response.send_message(f"✅ تمت إضافة رد تلقائي على **{trigger}**.", ephemeral=True)

    @autoresponse_group.command(name="remove", description="حذف رد تلقائي")
    @app_commands.describe(trigger="الكلمة المفتاحية")
    @app_commands.guild_only()
    async def autoresponse_remove(self, interaction: discord.Interaction, trigger: str):
        data = load_autoresponses()
        guild_responses = data.setdefault(str(interaction.guild.id), {})
        if trigger.lower() not in guild_responses:
            return await interaction.response.send_message("ℹ️ لا يوجد رد بهذه الكلمة.", ephemeral=True)
        del guild_responses[trigger.lower()]
        save_autoresponses(data)
        await interaction.response.send_message(f"✅ تم حذف الرد التلقائي لـ **{trigger}**.", ephemeral=True)

    @autoresponse_group.command(name="list", description="عرض كل الردود التلقائية")
    @app_commands.guild_only()
    async def autoresponse_list(self, interaction: discord.Interaction):
        data = load_autoresponses()
        guild_responses = data.get(str(interaction.guild.id), {})
        if not guild_responses:
            return await interaction.response.send_message("ℹ️ لا توجد ردود تلقائية مسجلة.", ephemeral=True)
        lines = [f"{i+1}. **{trig}** → {resp}" for i, (trig, resp) in enumerate(guild_responses.items())]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @autoresponse_group.command(name="clear", description="حذف كل الردود التلقائية")
    @app_commands.guild_only()
    async def autoresponse_clear(self, interaction: discord.Interaction):
        data = load_autoresponses()
        data[str(interaction.guild.id)] = {}
        save_autoresponses(data)
        await interaction.response.send_message("✅ تم حذف جميع الردود التلقائية.", ephemeral=True)

    # ----------------------------------------------------------- review
    @community_group.command(name="review", description="إرسال رسالة طلب تقييم بأزرار نجوم")
    @app_commands.describe(channel="القناة (اختياري، الافتراضي القناة الحالية)")
    @app_commands.guild_only()
    async def review(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ محتاج صلاحية `administrator` عشان تستخدم الأمر ده.", ephemeral=True)
        target_channel = channel or interaction.channel
        embed = discord.Embed(
            title="⭐ قيّمنا!",
            description="اضغط على عدد النجوم اللي تحب تقيّمنا بيه، وبعدين اكتب رأيك.",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=discord.utils.utcnow(),
        )
        await target_channel.send(embed=embed, view=ReviewView())
        await interaction.response.send_message(f"✅ تم إرسال رسالة التقييم في {target_channel.mention}.", ephemeral=True)

    @community_group.command(name="setreviewchannel", description="تحديد قناة عرض التقييمات")
    @app_commands.describe(channel="القناة")
    @app_commands.guild_only()
    async def setreviewchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ محتاج صلاحية `administrator` عشان تستخدم الأمر ده.", ephemeral=True)
        set_review_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(f"✅ ستُعرض التقييمات الآن في {channel.mention}.", ephemeral=True)

    # -------------------------------------------------------- general info
    @info_group.command(name="avatar", description="عرض صورة العضو الرمزية")
    @app_commands.describe(target="العضو (اختياري)")
    async def avatar(self, interaction: discord.Interaction, target: Optional[discord.User] = None):
        user = target or interaction.user
        embed = discord.Embed(title=f"صورة {user.display_name}", color=discord.Color.blurple(), timestamp=discord.utils.utcnow())
        embed.set_image(url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @info_group.command(name="banner", description="عرض بنر العضو")
    @app_commands.describe(target="العضو (اختياري)")
    async def banner(self, interaction: discord.Interaction, target: Optional[discord.User] = None):
        user = target or interaction.user
        fetched = await self.bot.fetch_user(user.id)
        if not fetched.banner:
            return await interaction.response.send_message(f"ℹ️ {user} ليس لديه بنر.", ephemeral=True)
        embed = discord.Embed(title=f"بنر {user.display_name}", color=discord.Color.blurple(), timestamp=discord.utils.utcnow())
        embed.set_image(url=fetched.banner.url)
        await interaction.response.send_message(embed=embed)

    @info_group.command(name="botinfo", description="عرض معلومات البوت التقنية")
    async def botinfo(self, interaction: discord.Interaction):
        uptime_seconds = int(time.time() - BOT_START_TIME)
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        embed = discord.Embed(title="🤖 معلومات البوت", color=discord.Color.blurple(), timestamp=discord.utils.utcnow())
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="المكتبة", value=f"discord.py", inline=True)
        embed.add_field(name="مدة التشغيل", value=f"`{days}d {hours}h {minutes}m {seconds}s`", inline=True)
        embed.add_field(name="عدد السيرفرات", value=f"`{len(self.bot.guilds)}`", inline=True)
        embed.add_field(name="نظام التشغيل", value=f"`{platform.system()} {platform.machine()}`", inline=True)
        await interaction.response.send_message(embed=embed)

    @info_group.command(name="emojis", description="عرض قائمة إيموجيات السيرفر")
    @app_commands.guild_only()
    async def emojis(self, interaction: discord.Interaction):
        emojis = " ".join(str(e) for e in interaction.guild.emojis) or "لا توجد إيموجيات مخصصة."
        if len(emojis) > 2000:
            return await interaction.response.send_message("❌ عدد الإيموجيات كبير جداً لعرضه في رسالة واحدة.", ephemeral=True)
        embed = discord.Embed(title=f"إيموجيات {interaction.guild.name}", description=emojis, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed)

    @info_group.command(name="invite", description="رابط دعوة البوت")
    async def invite(self, interaction: discord.Interaction):
        link = discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions(administrator=True))
        embed = discord.Embed(title="📨 دعوة البوت", description="اضغط الزر لدعوة البوت لسيرفرك.", color=discord.Color.blurple())
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="دعوة البوت", url=link, style=discord.ButtonStyle.link))
        await interaction.response.send_message(embed=embed, view=view)

    @info_group.command(name="membercount", description="عرض عدد أعضاء السيرفر بالتفصيل")
    @app_commands.guild_only()
    async def membercount(self, interaction: discord.Interaction):
        guild = interaction.guild
        total = guild.member_count
        bots = sum(1 for m in guild.members if m.bot)
        humans = total - bots
        embed = discord.Embed(title=f"👥 أعضاء {guild.name}", color=discord.Color.blurple())
        embed.add_field(name="الإجمالي", value=f"`{total}`", inline=True)
        embed.add_field(name="بشر", value=f"`{humans}`", inline=True)
        embed.add_field(name="بوتات", value=f"`{bots}`", inline=True)
        await interaction.response.send_message(embed=embed)

    @info_group.command(name="ping", description="عرض سرعة استجابة البوت")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🏓 البنج: `{round(self.bot.latency * 1000)}ms`")

    @info_group.command(name="roles", description="عرض قائمة رتب السيرفر")
    @app_commands.guild_only()
    async def roles(self, interaction: discord.Interaction):
        roles = [r.mention for r in sorted(interaction.guild.roles, key=lambda r: r.position, reverse=True) if r.name != "@everyone"]
        text = ", ".join(roles) or "لا توجد رتب."
        if len(text) > 2000:
            return await interaction.response.send_message("❌ عدد الرتب كبير جداً لعرضه في رسالة واحدة.", ephemeral=True)
        embed = discord.Embed(title=f"رتب {interaction.guild.name}", description=text, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed)

    @info_group.command(name="serverinfo", description="عرض معلومات السيرفر")
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        owner = guild.owner or await guild.fetch_owner()
        embed = discord.Embed(title=f"ℹ️ معلومات {guild.name}", color=discord.Color.blurple(), timestamp=discord.utils.utcnow())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="المالك", value=str(owner), inline=True)
        embed.add_field(name="الأيدي", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="تاريخ الإنشاء", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="الأعضاء", value=str(guild.member_count), inline=True)
        embed.add_field(name="القنوات", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="الرتب", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="مستوى البوست", value=f"{guild.premium_subscription_count or 0} (Tier {guild.premium_tier})", inline=True)
        await interaction.response.send_message(embed=embed)

    @info_group.command(name="uptime", description="عرض مدة تشغيل البوت")
    async def uptime(self, interaction: discord.Interaction):
        uptime_seconds = int(time.time() - BOT_START_TIME)
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        await interaction.response.send_message(f"⏱️ البوت شغّال منذ: `{days}d {hours}h {minutes}m {seconds}s`")

    @info_group.command(name="userinfo", description="عرض معلومات عضو")
    @app_commands.describe(target="العضو (اختياري)")
    @app_commands.guild_only()
    async def userinfo(self, interaction: discord.Interaction, target: Optional[discord.Member] = None):
        member = target or interaction.user
        embed = discord.Embed(title=f"معلومات {member.display_name}", color=discord.Color.blurple(), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="التاق", value=f"`{member}`", inline=True)
        embed.add_field(name="الأيدي", value=f"`{member.id}`", inline=True)
        embed.add_field(name="انضم لديسكورد", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        if member.joined_at:
            embed.add_field(name="انضم للسيرفر", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        embed.add_field(name="الرتب", value=" ".join(roles) or "لا توجد", inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    # autoresponse_group (class attribute) بيتسجل تلقائياً مع الـ tree عند add_cog.
    await bot.add_cog(CommunityCog(bot))
