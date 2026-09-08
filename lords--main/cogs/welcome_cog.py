"""نظام الترحيب، الدعوات، القوانين، والـ Embed المخصص."""
from __future__ import annotations

import json
import os
from io import BytesIO

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont


DB_FILE = "guild_settings.json"
DEFAULT_WELCOME_TEMPLATE = (
    "أهلاً وسهلاً بك {العضو}!\n"
    "أتمنى أن تقضي وقتاً ممتعاً معنا 🦋✨\n"
    "تم دعوتك من قبل **{الداعي}** ✨\n\n"
    "**Welcome, {الاسم}!**\n"
    "We hope you enjoy your time with us.\n"
    "Invited by **{الداعي}** ✨"
)
invites_cache: dict[int, dict[str, int]] = {}

WELCOME_COLORS = {
    "white": (255, 255, 255),
    "gold": (255, 215, 0),
    "blue": (100, 180, 255),
    "pink": (255, 125, 190),
    "green": (110, 235, 150),
    "red": (255, 105, 105),
}
WELCOME_COLOR_CHOICES = [
    app_commands.Choice(name="White", value="white"),
    app_commands.Choice(name="Gold", value="gold"),
    app_commands.Choice(name="Blue", value="blue"),
    app_commands.Choice(name="Pink", value="pink"),
    app_commands.Choice(name="Green", value="green"),
    app_commands.Choice(name="Red", value="red"),
]
EMBED_COLOR_CHOICES = [
    app_commands.Choice(name="Blurple", value="blurple"),
    app_commands.Choice(name="Blue", value="blue"),
    app_commands.Choice(name="Gold", value="gold"),
    app_commands.Choice(name="Green", value="green"),
    app_commands.Choice(name="Red", value="red"),
    app_commands.Choice(name="Purple", value="purple"),
]


def load_db() -> dict:
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def save_db(data: dict) -> None:
    with open(DB_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


db = load_db()


def get_setting(guild_id: int, key: str, default=None):
    return db.get(str(guild_id), {}).get(key, default)


def set_setting(guild_id: int, key: str, value) -> None:
    guild_key = str(guild_id)
    db.setdefault(guild_key, {})[key] = value
    save_db(db)


async def cache_guild_invites(guild: discord.Guild) -> None:
    try:
        guild_invites = await guild.invites()
        invites_cache[guild.id] = {invite.code: invite.uses or 0 for invite in guild_invites}
    except discord.Forbidden:
        print(f"⚠️ لا توجد صلاحية لجلب دعوات سيرفر: {guild.name}")


def _font(size: int):
    path = next(
        (candidate for candidate in (
            "arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ) if os.path.exists(candidate)),
        None,
    )
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    original = text.strip()
    text = original
    while text and draw.textlength(text, font=font) > max_width:
        text = text[:-1]
    return text + ("…" if text != original else "")


def _color_value(key: str | None, fallback: str = "gold") -> tuple[int, int, int]:
    return WELCOME_COLORS.get(key or fallback, WELCOME_COLORS[fallback])


def render_name_on_image(raw: bytes, name: str, color_key: str = "gold") -> BytesIO:
    """Adds a readable name banner to an admin-provided image."""
    base = Image.open(BytesIO(raw)).convert("RGBA")
    base.thumbnail((1600, 900))
    draw = ImageDraw.Draw(base, "RGBA")
    width, height = base.size
    banner_h = max(90, int(height * 0.18))
    draw.rectangle((0, height - banner_h, width, height), fill=(0, 0, 0, 165))
    font = _font(max(28, min(72, width // 14)))
    safe_name = _fit_text(draw, name, font, width - 80)
    name_w = draw.textlength(safe_name, font=font)
    name_color = _color_value(color_key)
    draw.text(((width - name_w) / 2, height - banner_h + 18), safe_name, font=font, fill=(*name_color, 255))
    output = BytesIO()
    base.convert("RGB").save(output, format="PNG")
    output.seek(0)
    return output


async def generate_welcome_image(
    member: discord.Member, background_url: str | None, name_color: str = "gold"
) -> BytesIO:
    width, height = 1200, 520
    async with aiohttp.ClientSession() as session:
        base = Image.new("RGBA", (width, height), (43, 45, 49, 255))
        if background_url:
            try:
                async with session.get(background_url) as response:
                    if response.status == 200:
                        bg_img = Image.open(BytesIO(await response.read())).convert("RGBA")
                        bg_img = bg_img.resize((width, height))
                        base.alpha_composite(bg_img)
            except Exception as error:
                print(f"تعذر تحميل الخلفية: {error}")

        base.alpha_composite(Image.new("RGBA", (width, height), (0, 0, 0, 105)))
        avatar_url = member.display_avatar.replace(size=256, format="png").url
        async with session.get(str(avatar_url)) as response:
            avatar_img = Image.open(BytesIO(await response.read())).convert("RGBA").resize((220, 220))

        mask = Image.new("L", (220, 220), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 220, 220), fill=255)
        avatar_img.putalpha(mask)
        avatar_x, avatar_y = width // 2 - 110, 45
        draw = ImageDraw.Draw(base)
        accent = _color_value(name_color)
        draw.ellipse((avatar_x - 9, avatar_y - 9, avatar_x + 229, avatar_y + 229), fill=(*accent, 255))
        base.paste(avatar_img, (avatar_x, avatar_y), avatar_img)

        name_font = _font(48)
        sub_font = _font(28)
        display_name = _fit_text(draw, member.display_name, name_font, width - 80)
        name_w = draw.textlength(display_name, font=name_font)
        draw.text(((width - name_w) / 2, 300), display_name, font=name_font, fill=(*accent, 255))
        subtitle = "عضو جديد • New member"
        sub_w = draw.textlength(subtitle, font=sub_font)
        draw.text(((width - sub_w) / 2, 365), subtitle, font=sub_font, fill="white")
        count = f"العضو رقم {member.guild.member_count} • Member #{member.guild.member_count}"
        count_w = draw.textlength(count, font=sub_font)
        draw.text(((width - count_w) / 2, 415), count, font=sub_font, fill=(235, 235, 235))

        output = BytesIO()
        base.convert("RGB").save(output, format="PNG")
        output.seek(0)
        return output


class WelcomeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📜 View Rules • شاهد القوانين", style=discord.ButtonStyle.blurple, custom_id="view_rules_btn")
    async def view_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        rules_channel_id = get_setting(interaction.guild.id, "rules_channel_id")
        if rules_channel_id:
            await interaction.response.send_message(
                f"📖 View the rules here: <#{rules_channel_id}> • يمكنك قراءة القوانين هنا.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Rules channel is not configured yet • لم يتم تحديد روم القوانين بعد.",
                ephemeral=True,
            )


class RulesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Agree to Rules • موافق على القوانين", style=discord.ButtonStyle.green, custom_id="accept_rules_btn")
    async def button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Thank you! Your agreement was recorded. 🎉 • شكراً لك! تم تسجيل موافقتك بنجاح.",
            ephemeral=True,
        )


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await cache_guild_invites(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        invites_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        welcome_channel_id = get_setting(guild.id, "welcome_channel_id")
        welcome_channel = (
            guild.get_channel(int(welcome_channel_id))
            if welcome_channel_id
            else guild.system_channel
        )
        if not welcome_channel:
            return

        inviter_name = "شخص غير معروف"
        try:
            new_invites = await guild.invites()
            old_invites = invites_cache.get(guild.id, {})
            used_invite = next(
                (invite for invite in new_invites if (invite.uses or 0) > old_invites.get(invite.code, 0)),
                None,
            )
            if used_invite and used_invite.inviter:
                inviter_name = str(used_invite.inviter)
            invites_cache[guild.id] = {invite.code: invite.uses or 0 for invite in new_invites}
        except discord.Forbidden:
            print(f"⚠️ لا توجد صلاحية Manage Server في سيرفر: {guild.name}")

        name_color = get_setting(guild.id, "welcome_name_color", "gold")
        image_buffer = await generate_welcome_image(
            member, get_setting(guild.id, "background_url"), name_color
        )
        file = discord.File(image_buffer, filename="welcome.png")

        inviter_name = inviter_name or "Unknown user"
        legacy_template = get_setting(guild.id, "welcome_message")
        arabic_template = get_setting(guild.id, "welcome_message_ar")
        english_template = get_setting(guild.id, "welcome_message_en")
        values = {
            "العضو": member.mention,
            "الاسم": member.display_name,
            "العدد": str(guild.member_count),
            "الداعي": inviter_name,
            "member": member.mention,
            "name": member.display_name,
            "count": str(guild.member_count),
            "inviter": inviter_name,
        }
        try:
            if arabic_template or english_template:
                arabic_text = (arabic_template or "أهلاً وسهلاً بك {العضو}!\nنتمنى لك وقتاً ممتعاً معنا 🦋✨").format(**values)
                english_text = (english_template or "**Welcome, {name}!**\nWe hope you enjoy your time with us. ✨").format(**values)
                welcome_text = f"{arabic_text}\n\n{english_text}"
            elif legacy_template:
                welcome_text = legacy_template.format(**values)
            else:
                welcome_text = DEFAULT_WELCOME_TEMPLATE.format(**values)
        except (KeyError, IndexError):
            welcome_text = DEFAULT_WELCOME_TEMPLATE.format(**values)

        embed = discord.Embed(
            title="🎉 عضو جديد انضم إلينا • A new member joined!",
            description=f"{member.mention}\n\n{welcome_text}",
            color=discord.Color.from_rgb(*_color_value(name_color)),
        )
        embed.set_image(url="attachment://welcome.png")
        embed.set_footer(text=f"عضو رقم {guild.member_count} في {guild.name} • Member #{guild.member_count}")
        await welcome_channel.send(embed=embed, file=file, view=WelcomeView())

    @app_commands.command(name="تحديد-روم-الترحيب", description="Set the channel for bilingual welcome messages")
    @app_commands.describe(channel="Welcome message channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        set_setting(interaction.guild.id, "welcome_channel_id", channel.id)
        await interaction.response.send_message(
            f"✅ Welcome channel set to {channel.mention} • تم تحديد روم الترحيب.", ephemeral=True
        )

    @app_commands.command(name="تحديد-صورة-الترحيب", description="Set the welcome background and name color")
    @app_commands.describe(
        image="Background image for the welcome card",
        name_color="Color of the member name inside the image (optional)",
    )
    @app_commands.choices(name_color=WELCOME_COLOR_CHOICES)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_background(
        self, interaction: discord.Interaction, image: discord.Attachment, name_color: app_commands.Choice[str] | None = None
    ):
        if not (image.content_type or "").startswith("image/"):
            await interaction.response.send_message("❌ The uploaded file is not a valid image • الملف المرفوع ليس صورة صالحة.", ephemeral=True)
            return
        set_setting(interaction.guild.id, "background_url", image.url)
        if name_color:
            set_setting(interaction.guild.id, "welcome_name_color", name_color.value)
        chosen = name_color.value if name_color else get_setting(interaction.guild.id, "welcome_name_color", "gold")
        await interaction.response.send_message(
            f"✅ Welcome background saved. Name color: **{chosen}** • تم حفظ الخلفية ولون الاسم.", ephemeral=True
        )

    @app_commands.command(name="تحديد-لون-اسم-الترحيب", description="Choose the name color inside the welcome image")
    @app_commands.describe(name_color="Color of the member name inside the welcome image")
    @app_commands.choices(name_color=WELCOME_COLOR_CHOICES)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_name_color(self, interaction: discord.Interaction, name_color: app_commands.Choice[str]):
        set_setting(interaction.guild.id, "welcome_name_color", name_color.value)
        await interaction.response.send_message(
            f"✅ Name color set to **{name_color.name}** • تم تحديد لون اسم العضو.", ephemeral=True
        )

    @app_commands.command(name="تحديد-رسالة-الترحيب", description="Set the Arabic and English welcome messages")
    @app_commands.describe(
        message_ar="Arabic welcome message. Use {member}, {name}, {count}, or {inviter}",
        message_en="English welcome message (optional). Use {member}, {name}, {count}, or {inviter}",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_message(
        self, interaction: discord.Interaction, message_ar: str, message_en: str | None = None
    ):
        set_setting(interaction.guild.id, "welcome_message_ar", message_ar)
        set_setting(interaction.guild.id, "welcome_message_en", message_en or "**Welcome, {name}!**\nWe hope you enjoy your time with us. ✨")
        preview = f"{message_ar}\n\n{message_en or '**Welcome, {name}!**'}"
        await interaction.response.send_message(
            f"✅ Bilingual welcome message saved • تم حفظ رسالة الترحيب الثنائية اللغة.\n\n{preview}",
            ephemeral=True,
        )

    @app_commands.command(name="استعادة-رسالة-الترحيب", description="Restore the default bilingual welcome message")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_welcome_message(self, interaction: discord.Interaction):
        set_setting(interaction.guild.id, "welcome_message", None)
        set_setting(interaction.guild.id, "welcome_message_ar", None)
        set_setting(interaction.guild.id, "welcome_message_en", None)
        await interaction.response.send_message(
            "✅ Default bilingual welcome message restored • تم استعادة الرسالة الافتراضية الثنائية اللغة.",
            ephemeral=True,
        )

    @app_commands.command(name="تحديد-روم-القوانين", description="Set the channel used by the View Rules button")
    @app_commands.describe(channel="Rules channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_rules_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        set_setting(interaction.guild.id, "rules_channel_id", channel.id)
        await interaction.response.send_message(
            f"✅ Rules channel set to {channel.mention} • تم تحديد روم القوانين.", ephemeral=True
        )

    @app_commands.command(name="تحديد-رسالة-القوانين", description="Set the Arabic and English server rules")
    @app_commands.describe(
        message_ar="Arabic rules message",
        message_en="English rules message (optional)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_rules_message(
        self, interaction: discord.Interaction, message_ar: str, message_en: str | None = None
    ):
        set_setting(interaction.guild.id, "rules_message_ar", message_ar)
        set_setting(
            interaction.guild.id,
            "rules_message_en",
            message_en or "Welcome! Respect members, do not advertise, use the correct channels, and respect privacy.",
        )
        await interaction.response.send_message(
            "✅ Bilingual rules message saved • تم حفظ رسالة القوانين الثنائية اللغة.",
            ephemeral=True,
        )

    @app_commands.command(name="استعادة-رسالة-القوانين", description="Restore the default bilingual server rules")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_rules_message(self, interaction: discord.Interaction):
        set_setting(interaction.guild.id, "rules_message_ar", None)
        set_setting(interaction.guild.id, "rules_message_en", None)
        await interaction.response.send_message(
            "✅ Default rules restored • تم استعادة القوانين الافتراضية.", ephemeral=True
        )

    @app_commands.command(name="ارسال-القوانين", description="Send your customized bilingual server rules")
    @app_commands.checks.has_permissions(administrator=True)
    async def send_rules(self, interaction: discord.Interaction):
        arabic_rules = get_setting(
            interaction.guild.id,
            "rules_message_ar",
        ) or "أهلاً بك! يرجى احترام الأعضاء، منع الإعلانات، الالتزام بالقنوات، واحترام الخصوصية."
        english_rules = get_setting(
            interaction.guild.id,
            "rules_message_en",
        ) or "Welcome! Respect members, do not advertise, use the correct channels, and respect privacy."
        embed = discord.Embed(
            title="📜 قوانين السيرفر • Server Rules",
            description=(
                f"**العربية:**\n{arabic_rules}\n\n"
                f"**English:**\n{english_rules}\n\n"
                "اضغط الزر بالأسفل للموافقة • Press the button below to agree."
            ),
            color=discord.Color.blue(),
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        await interaction.response.send_message(embed=embed, view=RulesView())

    @app_commands.command(name="ارسال-امبيد", description="Send a bilingual custom embed with an optional named image")
    @app_commands.describe(
        message_ar="Arabic message",
        channel="Target channel",
        title="Optional embed title",
        message_en="Optional English message",
        image="Optional image",
        color="Embed accent color",
        member="Optional member to mention and write inside the image",
    )
    @app_commands.choices(color=EMBED_COLOR_CHOICES)
    @app_commands.checks.has_permissions(administrator=True)
    async def send_custom_embed(
        self,
        interaction: discord.Interaction,
        message_ar: str,
        channel: discord.TextChannel,
        title: str | None = None,
        message_en: str | None = None,
        image: discord.Attachment | None = None,
        color: app_commands.Choice[str] | None = None,
        member: discord.Member | None = None,
    ):
        colors = {
            "blurple": discord.Color.blurple(),
            "blue": discord.Color.blue(),
            "gold": discord.Color.gold(),
            "green": discord.Color.green(),
            "red": discord.Color.red(),
            "purple": discord.Color.purple(),
        }
        embed = discord.Embed(
            title=title or "📢 Announcement • إعلان",
            description=(f"{member.mention}\n\n" if member else "") + message_ar + (f"\n\n{message_en}" if message_en else ""),
            color=colors.get(color.value if color else "blurple", discord.Color.blurple()),
        )
        embed.set_footer(text=f"Posted by {interaction.user} • بواسطة {interaction.user}", icon_url=interaction.user.display_avatar.url)

        file = None
        if image is not None:
            if not (image.content_type or "").startswith("image/"):
                await interaction.response.send_message("❌ The uploaded file is not a valid image • الملف المرفوع ليس صورة صالحة.", ephemeral=True)
                return
            if member:
                file = discord.File(
                    render_name_on_image(await image.read(), member.display_name, (color.value if color else "gold")),
                    filename="named-card.png",
                )
            else:
                file = await image.to_file()
            embed.set_image(url=f"attachment://{file.filename}")

        try:
            await channel.send(embed=embed, file=file) if file else await channel.send(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ I cannot send messages in {channel.mention} • لا أملك صلاحية الإرسال.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"✅ Bilingual embed sent to {channel.mention} • تم إرسال الـEmbed بنجاح.", ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
    bot.add_view(WelcomeView())
    bot.add_view(RulesView())