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
    "أهلاً وسهلاً بك {العضو} !\n"
    "أتمنى أن تقضي وقتاً ممتعاً معنا 🦋✨\n"
    "تم دعوتك من قبل **{الداعي}** ✨"
)
invites_cache: dict[int, dict[str, int]] = {}


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


async def generate_welcome_image(member: discord.Member, background_url: str | None) -> BytesIO:
    width, height = 1000, 400
    async with aiohttp.ClientSession() as session:
        base = Image.new("RGBA", (width, height), (43, 45, 49, 255))
        if background_url:
            try:
                async with session.get(background_url) as response:
                    if response.status == 200:
                        bg_img = Image.open(BytesIO(await response.read())).convert("RGBA")
                        base.paste(bg_img.resize((width, height)), (0, 0))
            except Exception as error:
                print(f"تعذر تحميل الخلفية: {error}")

        base = Image.alpha_composite(
            base,
            Image.new("RGBA", (width, height), (0, 0, 0, 120)),
        )

        avatar_url = member.display_avatar.replace(size=256, format="png").url
        async with session.get(str(avatar_url)) as response:
            avatar_img = Image.open(BytesIO(await response.read())).convert("RGBA").resize((180, 180))

        mask = Image.new("L", (180, 180), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 180, 180), fill=255)
        avatar_img.putalpha(mask)

        avatar_x, avatar_y = width // 2 - 90, 50
        draw = ImageDraw.Draw(base)
        draw.ellipse(
            (avatar_x - 8, avatar_y - 8, avatar_x + 188, avatar_y + 188),
            fill=(255, 215, 0, 255),
        )
        base.paste(avatar_img, (avatar_x, avatar_y), avatar_img)

        try:
            font_title = ImageFont.truetype("arial.ttf", 40)
            font_sub = ImageFont.truetype("arial.ttf", 26)
        except OSError:
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()

        welcome_text = f"أهلاً بك {member.name} 🦩"
        member_count_text = f"العضو رقم {member.guild.member_count}"
        title_w = draw.textlength(welcome_text, font=font_title)
        draw.text(((width - title_w) / 2, 260), welcome_text, font=font_title, fill="white")
        sub_w = draw.textlength(member_count_text, font=font_sub)
        draw.text(((width - sub_w) / 2, 315), member_count_text, font=font_sub, fill=(255, 215, 0))

        buffer = BytesIO()
        base.convert("RGB").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer


class WelcomeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📜 شاهد القوانين", style=discord.ButtonStyle.blurple, custom_id="view_rules_btn")
    async def view_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        rules_channel_id = get_setting(interaction.guild.id, "rules_channel_id")
        if rules_channel_id:
            await interaction.response.send_message(
                f"يمكنك الاطلاع على القوانين هنا: <#{rules_channel_id}> 📖",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "لم يتم تحديد روم القوانين بعد من قبل الإدارة.",
                ephemeral=True,
            )


class RulesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="موافق على القوانين ✅", style=discord.ButtonStyle.green, custom_id="accept_rules_btn")
    async def button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "شكراً لك! تم تسجيل موافقتك على القوانين بنجاح. 🎉",
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
        if not welcome_channel_id:
            return

        welcome_channel = guild.get_channel(int(welcome_channel_id))
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

        image_buffer = await generate_welcome_image(member, get_setting(guild.id, "background_url"))
        file = discord.File(image_buffer, filename="welcome.png")
        welcome_template = get_setting(guild.id, "welcome_message") or DEFAULT_WELCOME_TEMPLATE
        try:
            welcome_text = welcome_template.format(
                العضو=member.mention,
                الاسم=member.display_name,
                العدد=str(guild.member_count),
                الداعي=inviter_name,
            )
        except (KeyError, IndexError):
            welcome_text = DEFAULT_WELCOME_TEMPLATE.format(
                العضو=member.mention,
                الاسم=member.display_name,
                العدد=str(guild.member_count),
                الداعي=inviter_name,
            )

        embed = discord.Embed(
            title="🦩 عضو جديد انضم إلينا!",
            description=welcome_text,
            color=discord.Color.gold(),
        )
        embed.set_image(url="attachment://welcome.png")
        embed.set_footer(text=f"عضو رقم {guild.member_count} في {guild.name}")
        await welcome_channel.send(embed=embed, file=file, view=WelcomeView())

    @app_commands.command(name="تحديد-روم-الترحيب", description="تحديد الروم اللي هتظهر فيه رسائل ترحيب الأعضاء الجدد")
    @app_commands.describe(القناة="روم الترحيب")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_channel(self, interaction: discord.Interaction, القناة: discord.TextChannel):
        set_setting(interaction.guild.id, "welcome_channel_id", القناة.id)
        await interaction.response.send_message(f"✅ تم تحديد روم الترحيب: {القناة.mention}", ephemeral=True)

    @app_commands.command(name="تحديد-صورة-الترحيب", description="رفع صورة خلفية مخصصة لصورة الترحيب")
    @app_commands.describe(الصورة="ملف الصورة اللي هتبقى خلفية لبطاقة الترحيب")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_background(self, interaction: discord.Interaction, الصورة: discord.Attachment):
        if not الصورة.content_type or not الصورة.content_type.startswith("image/"):
            await interaction.response.send_message("❌ الملف اللي رفعته مش صورة صالحة.", ephemeral=True)
            return
        set_setting(interaction.guild.id, "background_url", الصورة.url)
        await interaction.response.send_message("✅ تم تحديد خلفية صورة الترحيب.", ephemeral=True)

    @app_commands.command(name="تحديد-رسالة-الترحيب", description="كتابة نص رسالة الترحيب بنفسك بدل الرسالة الافتراضية")
    @app_commands.describe(
        الرسالة="نص الرسالة. استخدم: {العضو} لمنشن العضو، {الاسم} لاسمه، {العدد} لرقم عضويته، {الداعي} لاسم من دعاه"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_message(self, interaction: discord.Interaction, الرسالة: str):
        set_setting(interaction.guild.id, "welcome_message", الرسالة)
        preview = الرسالة.format(العضو="@عضو_تجريبي", الاسم="عضو_تجريبي", العدد="42", الداعي="فلان")
        await interaction.response.send_message(
            f"✅ تم تحديد رسالة الترحيب المخصصة.\nمعاينة بعد تعويض المتغيرات:\n{preview}",
            ephemeral=True,
        )

    @app_commands.command(name="استعادة-رسالة-الترحيب", description="الرجوع لرسالة الترحيب الافتراضية")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_welcome_message(self, interaction: discord.Interaction):
        set_setting(interaction.guild.id, "welcome_message", None)
        await interaction.response.send_message("✅ تم الرجوع لرسالة الترحيب الافتراضية.", ephemeral=True)

    @app_commands.command(name="تحديد-روم-القوانين", description="تحديد الروم اللي فيه القوانين (يُستخدم في زر 'شاهد القوانين')")
    @app_commands.describe(القناة="روم القوانين")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_rules_channel(self, interaction: discord.Interaction, القناة: discord.TextChannel):
        set_setting(interaction.guild.id, "rules_channel_id", القناة.id)
        await interaction.response.send_message(f"✅ تم تحديد روم القوانين: {القناة.mention}", ephemeral=True)

    @app_commands.command(name="ارسال-القوانين", description="إرسال لوحة قوانين السيرفر مع زر موافقة تفاعلي")
    @app_commands.checks.has_permissions(administrator=True)
    async def send_rules(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📜 قوانين السيرفر الرسمية",
            description=(
                "أهلاً بك في السيرفر! يرجى قراءة القوانين والالتزام بها لتجنب العقوبات:\n"
                "─────────────────────────\n"
                "1️⃣ **الاحترام المتبادل:** يمنع السب أو الإهانة بجميع أشكالها.\n"
                "2️⃣ **منع الإعلانات:** يمنع نشر روابط سيرفرات أخرى أو إعلانات دون إذن.\n"
                "3️⃣ **الالتزام بالقنوات:** يرجى الكتابة في القناة المخصصة لكل موضوع.\n"
                "4️⃣ **احترام الخصوصية:** يمنع مشاركة معلومات شخصية للأعضاء.\n"
                "─────────────────────────"
            ),
            color=discord.Color.blue(),
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text="اضغط على الزر بالأسفل لتأكيد قراءة القوانين والموافقة عليها")
        await interaction.response.send_message(embed=embed, view=RulesView())

    @app_commands.command(name="ارسال-امبيد", description="إرسال رسالة Embed مخصصة في أي روم تحدده")
    @app_commands.describe(
        الرسالة="نص الرسالة اللي هتظهر داخل الـ Embed",
        القناة="الروم اللي هتتبعت فيه الرسالة",
        الصورة="صورة اختيارية تظهر داخل الـ Embed",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def send_custom_embed(
        self,
        interaction: discord.Interaction,
        الرسالة: str,
        القناة: discord.TextChannel,
        الصورة: discord.Attachment | None = None,
    ):
        embed = discord.Embed(description=الرسالة, color=discord.Color.blurple())
        embed.set_footer(text=f"بواسطة {interaction.user}", icon_url=interaction.user.display_avatar.url)

        file = None
        if الصورة is not None:
            if not الصورة.content_type or not الصورة.content_type.startswith("image/"):
                await interaction.response.send_message("❌ الملف اللي رفعته مش صورة صالحة.", ephemeral=True)
                return
            file = await الصورة.to_file()
            embed.set_image(url=f"attachment://{file.filename}")

        try:
            if file:
                await القناة.send(embed=embed, file=file)
            else:
                await القناة.send(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ ماعنديش صلاحية إرسال رسائل في {القناة.mention}.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(f"✅ تم إرسال الرسالة بنجاح في {القناة.mention}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
    bot.add_view(WelcomeView())
    bot.add_view(RulesView())