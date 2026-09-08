import discord
from discord import app_commands
from discord.ext import commands
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import json
import os

# ============================================================
# ⚙️ إعداد صلاحيات البوت (Intents)
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # ضروري عشان on_member_join يشتغل

bot = commands.Bot(command_prefix="!", intents=intents)

# ============================================================
# 🗄️ قاعدة بيانات بسيطة (ملف JSON) لتخزين إعدادات كل سيرفر
# بيانات كل سيرفر بتتخزن باسم guild.id كمفتاح
# ============================================================
DB_FILE = "guild_settings.json"

def load_db() -> dict:
    """تحميل قاعدة البيانات من الملف، أو إنشاء واحدة جديدة لو مش موجودة"""
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data: dict):
    """حفظ قاعدة البيانات على الملف"""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

db = load_db()

def get_setting(guild_id: int, key: str, default=None):
    return db.get(str(guild_id), {}).get(key, default)

def set_setting(guild_id: int, key: str, value):
    guild_id = str(guild_id)
    if guild_id not in db:
        db[guild_id] = {}
    db[guild_id][key] = value
    save_db(db)

# ============================================================
# 📨 تتبع الدعوات (Invite Tracker)
# invites_cache: guild_id -> { invite_code: uses }
# ============================================================
invites_cache: dict[int, dict[str, int]] = {}

async def cache_guild_invites(guild: discord.Guild):
    """تخزين عدد استخدامات كل دعوة في السيرفر"""
    try:
        guild_invites = await guild.invites()
        invites_cache[guild.id] = {inv.code: inv.uses for inv in guild_invites}
    except discord.Forbidden:
        # البوت محتاج صلاحية Manage Server عشان يشوف الدعوات
        print(f"⚠️ لا توجد صلاحية لجلب دعوات سيرفر: {guild.name}")

# ============================================================
# 🖼️ توليد صورة الترحيب باستخدام Pillow
# ============================================================
async def generate_welcome_image(member: discord.Member, background_url: str | None) -> BytesIO:
    """
    يولّد صورة ترحيب فيها:
    - خلفية (رابط مخصص أو لون افتراضي)
    - أفاتار العضو داخل دائرة بإطار ذهبي
    - اسم العضو + رقم عضويته في السيرفر
    """
    width, height = 1000, 400
    async with aiohttp.ClientSession() as session:

        # 1) تجهيز الخلفية
        base = Image.new("RGBA", (width, height), (43, 45, 49, 255))
        if background_url:
            try:
                async with session.get(background_url) as resp:
                    if resp.status == 200:
                        bg_bytes = await resp.read()
                        bg_img = Image.open(BytesIO(bg_bytes)).convert("RGBA")
                        bg_img = bg_img.resize((width, height))
                        base.paste(bg_img, (0, 0))
            except Exception as e:
                print(f"تعذر تحميل الخلفية: {e}")

        # طبقة تعتيم خفيفة عشان النص يبان بوضوح
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 120))
        base = Image.alpha_composite(base, overlay)

        # 2) تحميل أفاتار العضو
        avatar_url = member.display_avatar.replace(size=256, format="png").url
        async with session.get(str(avatar_url)) as resp:
            avatar_bytes = await resp.read()
        avatar_img = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((180, 180))

        # قص الأفاتار على شكل دائرة
        mask = Image.new("L", (180, 180), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, 180, 180), fill=255)
        avatar_img.putalpha(mask)

        # 3) رسم إطار ذهبي حول مكان الأفاتار
        avatar_x, avatar_y = width // 2 - 90, 50
        draw = ImageDraw.Draw(base)
        draw.ellipse(
            (avatar_x - 8, avatar_y - 8, avatar_x + 188, avatar_y + 188),
            fill=(255, 215, 0, 255)  # ذهبي
        )
        base.paste(avatar_img, (avatar_x, avatar_y), avatar_img)

        # 4) كتابة النصوص
        try:
            font_title = ImageFont.truetype("arial.ttf", 40)
            font_sub = ImageFont.truetype("arial.ttf", 26)
        except IOError:
            # خط افتراضي لو الخط المطلوب مش موجود على السيرفر المستضيف
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()

        welcome_text = f"أهلاً بك {member.name} 🦩"
        member_count_text = f"العضو رقم {member.guild.member_count}"

        title_w = draw.textlength(welcome_text, font=font_title)
        draw.text(((width - title_w) / 2, 260), welcome_text, font=font_title, fill="white")

        sub_w = draw.textlength(member_count_text, font=font_sub)
        draw.text(((width - sub_w) / 2, 315), member_count_text, font=font_sub, fill=(255, 215, 0))

        # 5) تجهيز الصورة للإرسال
        buffer = BytesIO()
        base.convert("RGB").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

# ============================================================
# 🔘 أزرار رسالة الترحيب (مثلاً زر "شاهد القوانين")
# ============================================================
class WelcomeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📜 شاهد القوانين", style=discord.ButtonStyle.blurple, custom_id="view_rules_btn")
    async def view_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        rules_channel_id = get_setting(interaction.guild.id, "rules_channel_id")
        if rules_channel_id:
            await interaction.response.send_message(
                f"يمكنك الاطلاع على القوانين هنا: <#{rules_channel_id}> 📖",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "لم يتم تحديد روم القوانين بعد من قبل الإدارة.",
                ephemeral=True
            )

# ============================================================
# 🔘 زر الموافقة على القوانين
# ============================================================
class RulesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # timeout=None يخلي الزر يشتغل للأبد حتى بعد إعادة تشغيل البوت

    @discord.ui.button(label="موافق على القوانين ✅", style=discord.ButtonStyle.green, custom_id="accept_rules_btn")
    async def button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # رد خاص (Ephemeral) يظهر للعضو فقط ولا يظهر لباقي الأعضاء
        await interaction.response.send_message(
            "شكراً لك! تم تسجيل موافقتك على القوانين بنجاح. 🎉",
            ephemeral=True
        )

# ============================================================
# 🚀 عند تشغيل البوت
# ============================================================
@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح بواسطة: {bot.user.name}")

    # تسجيل الـ Views عشان الأزرار تفضل شغالة حتى بعد إعادة تشغيل البوت
    bot.add_view(WelcomeView())
    bot.add_view(RulesView())

    # تخزين الدعوات الحالية لكل سيرفر البوت موجود فيه
    for guild in bot.guilds:
        await cache_guild_invites(guild)

    # مزامنة أوامر السلاش (/) مع ديسكورد عشان تظهر عند المستخدمين
    try:
        synced = await bot.tree.sync()
        print(f"تمت مزامنة {len(synced)} أمر سلاش.")
    except Exception as e:
        print(f"خطأ أثناء مزامنة أوامر السلاش: {e}")

@bot.event
async def on_invite_create(invite: discord.Invite):
    """تحديث الكاش عند إنشاء دعوة جديدة"""
    if invite.guild.id not in invites_cache:
        invites_cache[invite.guild.id] = {}
    invites_cache[invite.guild.id][invite.code] = invite.uses

# ============================================================
# 👋 عند انضمام عضو جديد
# ============================================================
@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild

    welcome_channel_id = get_setting(guild.id, "welcome_channel_id")
    if not welcome_channel_id:
        return  # مفيش روم ترحيب محدد لهذا السيرفر

    welcome_channel = guild.get_channel(int(welcome_channel_id))
    if not welcome_channel:
        return

    background_url = get_setting(guild.id, "background_url")

    # 1) تحديد الشخص الذي قام بالدعوة
    inviter_name = "شخص غير معروف"
    try:
        new_invites = await guild.invites()
        old_invites = invites_cache.get(guild.id, {})

        used_invite = None
        for inv in new_invites:
            old_uses = old_invites.get(inv.code, 0)
            if inv.uses > old_uses:
                used_invite = inv
                break

        if used_invite and used_invite.inviter:
            inviter_name = str(used_invite.inviter)

        # تحديث الكاش بالأرقام الجديدة
        invites_cache[guild.id] = {inv.code: inv.uses for inv in new_invites}
    except discord.Forbidden:
        print(f"⚠️ لا توجد صلاحية Manage Server في سيرفر: {guild.name}")

    # 2) توليد صورة الترحيب
    image_buffer = await generate_welcome_image(member, background_url)
    file = discord.File(image_buffer, filename="welcome.png")

    # 3) تجهيز نص الترحيب — من رسالة الإدارة المخصصة لو موجودة، وإلا الافتراضية
    welcome_template = get_setting(guild.id, "welcome_message") or DEFAULT_WELCOME_TEMPLATE
    try:
        welcome_text = welcome_template.format(
            العضو=member.mention,
            الاسم=member.display_name,
            العدد=str(guild.member_count),
            الداعي=inviter_name
        )
    except (KeyError, IndexError):
        # لو الإدارة كتبت متغير غلط في النص، نرجع للرسالة الافتراضية بدل ما نكسر الترحيب
        welcome_text = DEFAULT_WELCOME_TEMPLATE.format(
            العضو=member.mention, الاسم=member.display_name,
            العدد=str(guild.member_count), الداعي=inviter_name
        )

    # 4) تجهيز الـ Embed
    embed = discord.Embed(
        title="🦩 عضو جديد انضم إلينا!",
        description=welcome_text,
        color=discord.Color.gold()
    )
    embed.set_image(url="attachment://welcome.png")
    embed.set_footer(text=f"عضو رقم {guild.member_count} في {guild.name}")

    # 5) إرسال الرسالة مع زر "شاهد القوانين"
    await welcome_channel.send(embed=embed, file=file, view=WelcomeView())

# ============================================================
# ⚙️ أوامر إعداد نظام الترحيب (سلاش / وللإدارة فقط)
# ============================================================

# متغيرات قالب رسالة الترحيب الافتراضي — تُستخدم لو الإدارة ما حددتش رسالة مخصصة
DEFAULT_WELCOME_TEMPLATE = (
    "أهلاً وسهلاً بك {العضو} !\n"
    "أتمنى أن تقضي وقتاً ممتعاً معنا 🦋✨\n"
    "تم دعوتك من قبل **{الداعي}** ✨"
)

@bot.tree.command(name="تحديد-روم-الترحيب", description="تحديد الروم اللي هتظهر فيه رسائل ترحيب الأعضاء الجدد")
@app_commands.describe(القناة="روم الترحيب")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_channel(interaction: discord.Interaction, القناة: discord.TextChannel):
    set_setting(interaction.guild.id, "welcome_channel_id", القناة.id)
    await interaction.response.send_message(f"✅ تم تحديد روم الترحيب: {القناة.mention}", ephemeral=True)

@bot.tree.command(name="تحديد-صورة-الترحيب", description="رفع صورة خلفية مخصصة لصورة الترحيب")
@app_commands.describe(الصورة="ملف الصورة اللي هتبقى خلفية لبطاقة الترحيب")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_background(interaction: discord.Interaction, الصورة: discord.Attachment):
    if not الصورة.content_type or not الصورة.content_type.startswith("image/"):
        await interaction.response.send_message("❌ الملف اللي رفعته مش صورة صالحة.", ephemeral=True)
        return
    set_setting(interaction.guild.id, "background_url", الصورة.url)
    await interaction.response.send_message("✅ تم تحديد خلفية صورة الترحيب.", ephemeral=True)

@bot.tree.command(name="تحديد-رسالة-الترحيب", description="كتابة نص رسالة الترحيب بنفسك بدل الرسالة الافتراضية")
@app_commands.describe(
    الرسالة=(
        "نص الرسالة. استخدم: {العضو} لمنشن العضو، {الاسم} لاسمه، "
        "{العدد} لرقم عضويته، {الداعي} لاسم من دعاه"
    )
)
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_message(interaction: discord.Interaction, الرسالة: str):
    set_setting(interaction.guild.id, "welcome_message", الرسالة)
    await interaction.response.send_message(
        "✅ تم تحديد رسالة الترحيب المخصصة.\nمعاينة بعد تعويض المتغيرات:\n"
        + الرسالة.format(العضو="@عضو_تجريبي", الاسم="عضو_تجريبي", العدد="42", الداعي="فلان"),
        ephemeral=True
    )

@bot.tree.command(name="استعادة-رسالة-الترحيب", description="الرجوع لرسالة الترحيب الافتراضية")
@app_commands.checks.has_permissions(administrator=True)
async def reset_welcome_message(interaction: discord.Interaction):
    set_setting(interaction.guild.id, "welcome_message", None)
    await interaction.response.send_message("✅ تم الرجوع لرسالة الترحيب الافتراضية.", ephemeral=True)

@bot.tree.command(name="تحديد-روم-القوانين", description="تحديد الروم اللي فيه القوانين (يُستخدم في زر 'شاهد القوانين')")
@app_commands.describe(القناة="روم القوانين")
@app_commands.checks.has_permissions(administrator=True)
async def set_rules_channel(interaction: discord.Interaction, القناة: discord.TextChannel):
    set_setting(interaction.guild.id, "rules_channel_id", القناة.id)
    await interaction.response.send_message(f"✅ تم تحديد روم القوانين: {القناة.mention}", ephemeral=True)

# رد موحّد على أخطاء صلاحيات كل أوامر السلاش الخاصة بالترحيب والقوانين
async def _welcome_admin_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة فقط.", ephemeral=True)
    else:
        print(f"خطأ في أمر إعداد الترحيب: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ حصل خطأ غير متوقع أثناء تنفيذ الأمر.", ephemeral=True)

set_welcome_channel.error(_welcome_admin_error)
set_welcome_background.error(_welcome_admin_error)
set_welcome_message.error(_welcome_admin_error)
reset_welcome_message.error(_welcome_admin_error)
set_rules_channel.error(_welcome_admin_error)

# ============================================================
# 📜 أمر إرسال لوحة القوانين (Embed + زر الموافقة)
# ============================================================
@bot.tree.command(name="ارسال-القوانين", description="إرسال لوحة قوانين السيرفر مع زر موافقة تفاعلي")
@app_commands.checks.has_permissions(administrator=True)
async def send_rules(interaction: discord.Interaction):
    """يرسل لوحة قوانين منسقة بالـ Embed مع زر موافقة تفاعلي"""

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
        color=discord.Color.blue()
    )

    # صورة مصغرة للسيرفر (لوجو)
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)

    embed.set_footer(text="اضغط على الزر بالأسفل لتأكيد قراءة القوانين والموافقة عليها")

    # إرسال اللوحة مع زر الموافقة (رسالة عامة يشوفها الكل في الروم)
    await interaction.response.send_message(embed=embed, view=RulesView())

send_rules.error(_welcome_admin_error)

# ============================================================
# 📢 أمر سلاش عام لإرسال أي رسالة Embed (نص + صورة + تحديد الروم)
# بدل ما تطلب كود مخصص كل مرة، الأمر ده بيغنيك عن ده تماماً
# استخدامه: /ارسال-امبيد الرسالة:<نصك> القناة:#روم الصورة:<مرفق اختياري>
# ============================================================
@bot.tree.command(name="ارسال-امبيد", description="إرسال رسالة Embed مخصصة في أي روم تحدده")
@app_commands.describe(
    الرسالة="نص الرسالة اللي هتظهر داخل الـ Embed",
    القناة="الروم اللي هتتبعت فيه الرسالة",
    الصورة="صورة اختيارية تظهر داخل الـ Embed"
)
@app_commands.checks.has_permissions(administrator=True)
async def send_custom_embed(
    interaction: discord.Interaction,
    الرسالة: str,
    القناة: discord.TextChannel,
    الصورة: discord.Attachment | None = None
):
    # تجهيز الـ Embed بالنص المكتوب
    embed = discord.Embed(
        description=الرسالة,
        color=discord.Color.blurple()
    )
    embed.set_footer(
        text=f"بواسطة {interaction.user}",
        icon_url=interaction.user.display_avatar.url
    )

    file = None
    if الصورة is not None:
        # تحقق إن المرفق فعلاً صورة قبل الإرسال
        if not الصورة.content_type or not الصورة.content_type.startswith("image/"):
            await interaction.response.send_message("❌ الملف اللي رفعته مش صورة صالحة.", ephemeral=True)
            return
        file = await الصورة.to_file()
        embed.set_image(url=f"attachment://{file.filename}")

    # إرسال الرسالة في الروم المحدد
    try:
        if file:
            await القناة.send(embed=embed, file=file)
        else:
            await القناة.send(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message(f"❌ ماعنديش صلاحية إرسال رسائل في {القناة.mention}.", ephemeral=True)
        return

    # تأكيد خاص (Ephemeral) للشخص اللي نفذ الأمر بس
    await interaction.response.send_message(f"✅ تم إرسال الرسالة بنجاح في {القناة.mention}", ephemeral=True)

@send_custom_embed.error
async def send_custom_embed_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة فقط.", ephemeral=True)
    else:
        print(f"خطأ في أمر /ارسال-امبيد: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ حصل خطأ غير متوقع أثناء تنفيذ الأمر.", ephemeral=True)

# ============================================================
# ▶️ تشغيل البوت
# ============================================================
# استخدم Secret المشروع، مع دعم الاسم القديم DISCORD_TOKEN.
bot.run(os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN", "ضع_التوكن_هنا"))
