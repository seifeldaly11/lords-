"""
كوج القائمة التفاعلية (/menu) — بيعرض فئات الأوامر الإدارية الجديدة (الإشراف،
الحماية، التذاكر، الاقتصاد، المجتمع، المعلومات العامة) في قائمة منسدلة واحدة،
عشان العضو يقدر يستكشف الأوامر المتاحة قبل ما يكتب أي أمر بنفسه.

ملاحظة: أوامر اللعبة نفسها (Lords Mobile) لسه موجودة ومشروحة في /help الأصلي.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

CATEGORIES: dict[str, dict] = {
    "mod": {
        "label": "🛡️ الإشراف",
        "emoji": "🛡️",
        "root": "/mod",
        "description": "أوامر البان والطرد والإسكات والتحذيرات وإدارة القنوات.",
        "commands": [
            ("/mod ban", "حظر عضو من السيرفر"),
            ("/mod unban", "إلغاء حظر عضو"),
            ("/mod kick", "طرد عضو"),
            ("/mod mute", "إسكات عضو لمدة 28 يوم"),
            ("/mod unmute", "إزالة الإسكات"),
            ("/mod timeout", "إسكات عضو لمدة محددة"),
            ("/mod untimeout", "إزالة الإسكات المؤقت"),
            ("/mod vmute / vunmute", "إسكات/فك إسكات صوتي"),
            ("/mod warn", "تحذير عضو"),
            ("/mod warnings", "عرض تحذيرات عضو"),
            ("/mod clear-warnings", "مسح تحذيرات عضو"),
            ("/mod clear", "حذف عدد من الرسائل"),
            ("/mod lock / unlock", "قفل/فتح القناة"),
            ("/mod hide / unhide", "إخفاء/إظهار القناة"),
            ("/mod slowmode", "ضبط الوضع البطيء"),
            ("/mod role", "منح/سحب رتبة"),
            ("/mod nuke", "مسح كل رسائل القناة"),
        ],
    },
    "security": {
        "label": "🔐 الحماية",
        "emoji": "🔐",
        "root": "/security",
        "description": "نظام مكافحة النيوك: anti-spam, anti-bot، حماية الرولات والقنوات، نسخ احتياطي.",
        "commands": [
            ("/security protection toggle", "تشغيل/إيقاف نوع حماية معين"),
            ("/security protection status", "عرض حالة كل الحمايات"),
            ("/security whitelist grant-user/grant-role", "منح تجاوز للحماية"),
            ("/security whitelist revoke-user", "سحب تجاوز"),
            ("/security whitelist view", "عرض قائمة الوايت ليست"),
            ("/security backup create", "أخذ نسخة احتياطية للرولات/القنوات"),
            ("/security backup restore-roles/restore-channels", "استعادة من النسخة"),
            ("/security backup info", "معلومات آخر نسخة"),
            ("/security limit-settings", "ضبط حد العقوبة على الحذف"),
            ("/security togglepro", "تفعيل/تعطيل كل الحمايات دفعة واحدة"),
        ],
    },
    "ticket": {
        "label": "🎫 التذاكر",
        "emoji": "🎫",
        "root": "/ticket",
        "description": "نظام تذاكر دعم بأزرار فتح/مطالبة/إغلاق.",
        "commands": [
            ("/ticket setup", "إعداد رسالة فتح التذاكر في قناة"),
            ("/ticket category", "تحديد الفئة اللي تُفتح فيها التذاكر"),
            ("/ticket come", "استدعاء عضو داخل التذكرة"),
        ],
    },
    "economy": {
        "label": "💰 الاقتصاد",
        "emoji": "💰",
        "root": "/economy",
        "description": "عملات، هدية يومية، XP، ولوحة صدارة.",
        "commands": [
            ("/economy coins", "عرض رصيدك"),
            ("/economy daily", "استلام الهدية اليومية"),
            ("/economy addcoins", "إضافة عملات (مطورين)"),
            ("/economy restartcoins", "إعادة تعيين العملات (مطورين)"),
            ("/economy addxp", "إضافة XP (مطورين)"),
            ("/economy top show", "عرض لوحة الصدارة"),
            ("/economy top restart", "تصفير لوحة الصدارة (مطورين)"),
        ],
    },
    "community": {
        "label": "📣 المجتمع",
        "emoji": "📣",
        "root": "/community",
        "description": "إعلانات، ردود تلقائية، ونظام تقييمات بأزرار نجوم.",
        "commands": [
            ("/community announce", "إرسال إعلان في القناة الحالية"),
            ("/community review", "إرسال رسالة طلب تقييم"),
            ("/community setreviewchannel", "تحديد قناة عرض التقييمات"),
            ("/community autoresponse add/remove/list/clear", "إدارة الردود التلقائية"),
        ],
    },
    "info": {
        "label": "ℹ️ معلومات عامة",
        "emoji": "ℹ️",
        "root": "/util",
        "description": "أوامر عامة متاحة للجميع (سيرفر، أعضاء، البوت نفسه).",
        "commands": [
            ("/util avatar", "صورة عضو"),
            ("/util banner", "بنر عضو"),
            ("/util botinfo", "معلومات البوت"),
            ("/util emojis", "إيموجيات السيرفر"),
            ("/util invite", "رابط دعوة البوت"),
            ("/util membercount", "عدد الأعضاء"),
            ("/util ping", "سرعة استجابة البوت"),
            ("/util roles", "قائمة الرتب"),
            ("/util serverinfo", "معلومات السيرفر"),
            ("/util uptime", "مدة تشغيل البوت"),
            ("/util userinfo", "معلومات عضو"),
        ],
    },
}


def build_overview_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📋 قائمة الأوامر الإدارية",
        description=(
            "اختر فئة من القائمة تحت عشان تشوف كل الأوامر المتاحة فيها.\n\n"
            "ℹ️ أوامر اللعبة نفسها (الوحوش، النقابة، الحرب...) موجودة في `/help`."
        ),
        color=discord.Color.from_rgb(255, 255, 255),
    )
    for key, cat in CATEGORIES.items():
        embed.add_field(name=f"{cat['label']} — {cat['root']}", value=cat["description"], inline=False)
    return embed


def build_category_embed(key: str) -> discord.Embed:
    cat = CATEGORIES[key]
    embed = discord.Embed(
        title=f"{cat['label']} ({cat['root']})",
        description=cat["description"],
        color=discord.Color.from_rgb(255, 255, 255),
    )
    for cmd, desc in cat["commands"]:
        embed.add_field(name=cmd, value=desc, inline=False)
    return embed


class MenuSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=cat["label"], value=key, description=cat["root"], emoji=cat["emoji"])
            for key, cat in CATEGORIES.items()
        ]
        options.append(discord.SelectOption(label="🔙 الرجوع للقائمة الرئيسية", value="__overview__"))
        super().__init__(placeholder="اختر فئة لعرض أوامرها...", options=options, custom_id="lm_menu_select")

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        if value == "__overview__":
            await interaction.response.edit_message(embed=build_overview_embed(), view=self.view)
        else:
            await interaction.response.edit_message(embed=build_category_embed(value), view=self.view)


class MenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(MenuSelect())


class MenuCog(commands.Cog):
    """أمر /menu التفاعلي لاستعراض كل الأوامر الإدارية الجديدة."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="menu", description="📋 عرض قائمة تفاعلية بكل أوامر الإدارة المتاحة")
    @app_commands.guild_only()
    async def menu(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_overview_embed(), view=MenuView(), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MenuCog(bot))
