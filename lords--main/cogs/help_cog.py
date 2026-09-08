"""مركز المساعدة الديناميكي للبوت.

القائمة هنا تُبنى من App Command Tree المحمّل فعلياً، وليس من قائمة يدوية
قديمة؛ لذلك أي أمر جديد يظهر في /help تلقائياً، وأي أمر محذوف يختفي منه.
"""
from __future__ import annotations

from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang


CATEGORY_META = {
    "overview": {
        "emoji": "🧭",
        "ar": "نظرة عامة",
        "en": "Overview",
        "color": discord.Color.blurple(),
    },
    "ai": {
        "emoji": "🤖",
        "ar": "الذكاء الاصطناعي والمستشار",
        "en": "AI Advisor",
        "color": discord.Color.purple(),
    },
    "calculators": {
        "emoji": "🧮",
        "ar": "الحواسب والأدلة السريعة",
        "en": "Calculators & Quick Guides",
        "color": discord.Color.gold(),
    },
    "war": {
        "emoji": "⚔️",
        "ar": "الحرب والتكتيك",
        "en": "War & Tactics",
        "color": discord.Color.red(),
    },
    "alliance": {
        "emoji": "🏯",
        "ar": "إدارة التحالف والتتبع",
        "en": "Alliance Management",
        "color": discord.Color.dark_gold(),
    },
    "market": {
        "emoji": "💱",
        "ar": "بورصة الموارد",
        "en": "Resource Market",
        "color": discord.Color.green(),
    },
    "hunt": {
        "emoji": "🐾",
        "ar": "متتبع الصيد",
        "en": "Hunt Tracker",
        "color": discord.Color.dark_green(),
    },
    "shield": {
        "emoji": "🔔",
        "ar": "منبه الدرع",
        "en": "Shield Alarm",
        "color": discord.Color.dark_orange(),
    },
    "settings": {
        "emoji": "⚙️",
        "ar": "الإعدادات واللغة",
        "en": "Settings & Language",
        "color": discord.Color.light_grey(),
    },
    "welcome": {
        "emoji": "👋",
        "ar": "الترحيب والقوانين والـ Embed",
        "en": "Welcome, Rules & Embeds",
        "color": discord.Color.blue(),
    },
    "games": {
        "emoji": "🎮",
        "ar": "الألعاب والتفاعل",
        "en": "Games & Interaction",
        "color": discord.Color.blurple(),
    },
    "general": {
        "emoji": "📚",
        "ar": "أوامر عامة",
        "en": "General",
        "color": discord.Color.dark_teal(),
    },
}

CATEGORY_ORDER = [
    "ai",
    "calculators",
    "war",
    "alliance",
    "market",
    "hunt",
    "shield",
    "settings",
    "welcome",
    "games",
    "general",
]

WELCOME_COMMANDS = {
    "ارسال-امبيد",
    "ارسال-القوانين",
    "استعادة-رسالة-الترحيب",
    "تحديد-رسالة-الترحيب",
    "تحديد-روم-الترحيب",
    "تحديد-روم-القوانين",
    "تحديد-صورة-الترحيب",
}

ADMIN_HINTS = (
    "إدارة",
    "administrator",
    "manage server",
    "admin",
)


def _walk_commands(command_list, prefix: str = ""):
    """Flatten top-level commands and groups into unique display paths."""
    for command in command_list:
        path = f"{prefix} {command.name}".strip()
        if isinstance(command, app_commands.Group):
            yield from _walk_commands(command.commands, path)
        else:
            yield path, command


def loaded_commands(bot: commands.Bot) -> list[tuple[str, app_commands.Command]]:
    """Return the actual current tree, deduplicated by full command path."""
    unique = {}
    for path, command in _walk_commands(bot.tree.get_commands()):
        unique[path] = command
    return sorted(unique.items(), key=lambda item: item[0].casefold())


def command_category(path: str) -> str:
    root = path.split(" ", 1)[0]
    if root in {"ai", "scout", "optimize"} or path.startswith("gf optimize"):
        return "ai"
    if root in {"event", "speedup", "monster", "dict", "info", "add_info", "add_monster", "geartiers"}:
        return "calculators"
    if root in {"counter", "analyze", "report"}:
        return "war"
    if root in {"log_activity", "information", "user_admin_check", "top5", "event_stats", "stats_event", "gf"}:
        return "alliance"
    if root == "market":
        return "market"
    if root in {"hunt_log", "hunt_channel", "hunt_list"}:
        return "hunt"
    if root in {"shield", "voice_rescue", "shelter_done"}:
        return "shield"
    if root in {"setup", "setup_check", "language", "languageme", "bot_channel", "server", "me"}:
        return "settings"
    if root in WELCOME_COMMANDS:
        return "welcome"
    if root in {"quiz", "play"}:
        return "games"
    return "general"


def command_description(path: str, command: app_commands.Command, lang: str) -> str:
    description = (command.description or "").strip()
    if not description:
        description = "أمر متاح في البوت." if lang == "ar" else "Available bot command."

    if command.name in WELCOME_COMMANDS and lang == "ar":
        welcome_copy = {
            "ارسال-امبيد": "إرسال Embed احترافي مخصص إلى روم تختاره، مع نص وصورة اختيارية.",
            "ارسال-القوانين": "إرسال لوحة القوانين مع زر موافقة تفاعلي للأعضاء.",
            "استعادة-رسالة-الترحيب": "إرجاع رسالة الترحيب الافتراضية.",
            "تحديد-رسالة-الترحيب": "تخصيص نص الترحيب مع متغيرات العضو والداعي والعدد.",
            "تحديد-روم-الترحيب": "اختيار الروم الذي يستقبل رسائل الأعضاء الجدد.",
            "تحديد-روم-القوانين": "تحديد روم القوانين الذي يفتحه زر شاهد القوانين.",
            "تحديد-صورة-الترحيب": "تعيين خلفية بطاقة الترحيب.",
        }
        description = welcome_copy.get(command.name, description)

    if any(hint in description.lower() for hint in ADMIN_HINTS) or command.name in WELCOME_COMMANDS:
        description = f"🔒 {description}"
    return description[:1000]


def build_intro_embed(bot: commands.Bot, lang: str) -> discord.Embed:
    commands_list = loaded_commands(bot)
    counts = defaultdict(int)
    for path, _ in commands_list:
        counts[command_category(path)] += 1

    if lang == "en":
        title = "📖 Lords Mobile Command Center"
        description = (
            f"Everything currently loaded in this bot, organized by function.\n"
            f"**{len(commands_list)} commands** across **{len([c for c in counts if counts[c]])} sections**.\n"
            "Use the menu below to open a focused section."
        )
        count_label = "commands"
    else:
        title = "📖 مركز أوامر Lords Mobile"
        description = (
            f"دي قائمة الأوامر المحمّلة فعلياً في البوت، متقسمة حسب الوظيفة.\n"
            f"**{len(commands_list)} أمر** في **{len([c for c in counts if counts[c]])} أقسام**.\n"
            "اختار قسم من القائمة عشان تشوف التفاصيل."
        )
        count_label = "أمر"

    embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
    overview = []
    for key in CATEGORY_ORDER:
        if counts.get(key):
            meta = CATEGORY_META[key]
            overview.append(f"{meta['emoji']} **{meta[lang]}** — {counts[key]} {count_label}")
    embed.add_field(
        name="الأقسام" if lang == "ar" else "Sections",
        value="\n".join(overview) or ("لا توجد أوامر." if lang == "ar" else "No commands loaded."),
        inline=False,
    )
    embed.add_field(
        name="مهم للإدارة" if lang == "ar" else "For alliance admins",
        value=(
            "ابدأ بـ `/setup`، وبعدها اضبط الترحيب والقوانين من قسم 👋. "
            "الأوامر التي عليها 🔒 تحتاج صلاحية إدارية."
            if lang == "ar"
            else "Start with `/setup`, then configure welcome, rules, and embeds from the 👋 section. "
            "Commands marked 🔒 require admin permissions."
        ),
        inline=False,
    )
    embed.set_footer(
        text="القائمة تتحدث تلقائياً مع الأوامر الفعلية • Lords Mobile Alliance Suite"
        if lang == "ar"
        else "This list is generated from the live command tree • Lords Mobile Alliance Suite"
    )
    return embed


def build_category_embed(bot: commands.Bot, category: str, lang: str) -> discord.Embed:
    meta = CATEGORY_META[category]
    commands_in_category = [
        (path, command)
        for path, command in loaded_commands(bot)
        if command_category(path) == category
    ]
    embed = discord.Embed(
        title=f"{meta['emoji']} {meta[lang]}",
        description=(
            f"{len(commands_in_category)} أمر في هذا القسم."
            if lang == "ar"
            else f"{len(commands_in_category)} commands in this section."
        ),
        color=meta["color"],
    )
    for path, command in commands_in_category:
        embed.add_field(
            name=f"`/{path}`",
            value=command_description(path, command, lang),
            inline=False,
        )
    embed.set_footer(
        text="الأوصاف تتبع الأوامر المحمّلة حالياً • استخدم القائمة للانتقال بين الأقسام"
        if lang == "ar"
        else "Descriptions reflect the commands currently loaded • Use the menu to switch sections"
    )
    return embed


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, lang: str):
        self.bot = bot
        self.lang = lang
        options = []
        available = {command_category(path) for path, _ in loaded_commands(bot)}
        for key in CATEGORY_ORDER:
            if key not in available:
                continue
            meta = CATEGORY_META[key]
            options.append(discord.SelectOption(label=meta[lang][:100], value=key, emoji=meta["emoji"]))
        super().__init__(
            placeholder="اختار قسم الأوامر" if lang == "ar" else "Choose a command section",
            options=options[:25],
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=build_category_embed(self.bot, self.values[0], self.lang),
            view=self.view,
        )


class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot, lang: str):
        super().__init__(timeout=300)
        self.add_item(HelpCategorySelect(bot, lang))


class HelpCog(commands.Cog):
    """/help - مركز أوامر ديناميكي مناسب لتحالفات كبيرة."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="📖 مركز أوامر البوت، منظم حسب الوظيفة والإدارة والحرب والـ AI",
    )
    async def help_cmd(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(
            embed=build_intro_embed(self.bot, lang),
            view=HelpView(self.bot, lang),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))