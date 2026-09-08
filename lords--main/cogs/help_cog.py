"""مركز المساعدة الديناميكي للبوت.

القائمة هنا تُبنى من App Command Tree المحمّل فعلياً، وليس من قائمة يدوية
قديمة؛ لذلك أي أمر جديد يظهر في /help تلقائياً، وأي أمر محذوف يختفي منه.
"""
from __future__ import annotations

from collections import defaultdict
import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang


log = logging.getLogger("lordsbot.help")

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
    "تحديد-رسالة-القوانين",
    "استعادة-رسالة-القوانين",
}

ADMIN_HINTS = (
    "إدارة",
    "administrator",
    "manage server",
    "admin",
)

# English copy used by /help when the user selects English.
ENGLISH_COMMAND_DESCRIPTIONS = {
    "help": "Open the live command center and browse commands by section.",
    "ai": "Ask the Lords advisor a question or attach an image for analysis.",
    "optimize": "Get an AI plan for completing an Alliance Festival task.",
    "event": "Calculate whether your speedups can complete a Hell or Solo Event stage.",
    "shelter": "Start a shelter timer with a reminder 15 minutes before it ends.",
    "speedup": "Add your speedups and calculate the total time.",
    "monster": "Find the best hunting heroes for a selected monster.",
    "add_monster": "[Admin] Add a monster to the hunting guide.",
    "dict": "Look up a Lords Mobile term in the quick dictionary.",
    "info": "Read a guide about events such as Dragon Arena, KvK, and Hell Events.",
    "add_info": "[Admin] Add a new event guide entry.",
    "task": "[Admin] Add an Alliance Festival task for a member.",
    "done": "[Admin] Mark an Alliance Festival task as completed.",
    "board": "View the Alliance Festival leaderboard.",
    "calc": "Calculate Alliance Festival speedups or ask about resource exchanges.",
    "log_activity": "[Admin] Record a member's participation in an alliance activity.",
    "stats_event": "View interactive member participation statistics.",
    "profile": "View a member profile with alliance participation statistics.",
    "top5": "View the five most active members across tracked activities.",
    "event_stats": "View a participation report for a selected alliance event.",
    "quiz": "Answer a quick Lords Mobile quiz question and earn points.",
    "reset_stats": "[Admin] Reset activity and quiz records for a new week.",
    "hunt_log": "Log hunting results manually, from an image, or as a grouped list.",
    "hunt_channel": "[Admin] Configure the channel and daily target for hunt reports.",
    "hunt_list": "View each member's hunt count and remaining daily target.",
    "scout": "Analyze an enemy gear or profile image with AI.",
    "geartiers": "Browse the complete gear tier guide for war, hunting, and economy.",
    "offer": "Add a resource exchange offer for alliance members.",
    "list": "View active resource exchange offers in this server.",
    "cancel": "Cancel your latest resource exchange offer.",
    "set": "Register or update your main troop type.",
    "open": "Open a rally call and notify members with the required troop type.",
    "rally": "Open a smart rally call for the alliance.",
    "counter": "Find the ideal counter formation for an enemy formation.",
    "analyze": "Analyze a battle report image and its numbers.",
    "shield": "Start a smart shield alarm with a 15-minute warning and voice escalation.",
    "voice_rescue": "Start a shield alarm with voice escalation if nobody responds.",
    "shelter_done": "Stop the active shield or shelter alarm.",
    "setup": "[Admin] Open the guided setup panel for the bot.",
    "setup_check": "[Admin] Check whether the bot settings and integrations are working.",
    "language": "[Admin] Set the bot reply language for this server.",
    "languageme": "Choose your personal bot reply language.",
    "bot_channel": "[Admin] Set the channel or thread where the bot can respond.",
    "report": "Record and review alliance battle reports.",
    "add": "Record a new battle in the server log.",
    "user": "View the battle history of a selected member.",
    "تحديد-روم-الترحيب": "[Admin] Set the channel for new-member welcome messages.",
    "تحديد-صورة-الترحيب": "[Admin] Set a custom background for the welcome card.",
    "تحديد-رسالة-الترحيب": "[Admin] Customize the new-member welcome message.",
    "استعادة-رسالة-الترحيب": "[Admin] Restore the default welcome message.",
    "تحديد-روم-القوانين": "[Admin] Set the channel used by the View Rules button.",
    "ارسال-القوانين": "[Admin] Send the server rules panel with an acceptance button.",
    "ارسال-امبيد": "[Admin] Send a custom embed to a selected channel.",
    "تحديد-رسالة-القوانين": "[Admin] Set the Arabic and English server rules.",
    "استعادة-رسالة-القوانين": "[Admin] Restore the default bilingual server rules.",
}



ARABIC_COMMAND_DESCRIPTIONS = {
    "help": "📖 مركز أوامر البوت، منظم حسب الوظيفة والإدارة والحرب والـ AI",
    "ai": "🤖 اسأل مستشار لوردس أو أرفق صورة عتاد أو تقرير لتحليلها",
    "optimize": "🤖 مستشار AI يقترح أفضل طريقة لتنفيذ مهمة مهرجان التحالف",
    "event": "🧮 احسب هل التسريعات تكفي لإكمال مرحلة من حدث الجحيم أو الحدث الفردي",
    "shelter": "🛡️ مؤقت حماية الجيش مع تنبيه قبل الانتهاء بـ15 دقيقة",
    "speedup": "🚀 اجمع التسريعات واحسب إجمالي الوقت المتاح",
    "monster": "🐾 اعرف أفضل أبطال الصيد حسب اسم الوحش",
    "add_monster": "🐾 [إدارة] أضف وحشًا جديدًا إلى دليل الصيد",
    "dict": "📖 ابحث عن معنى مصطلح من مصطلحات Lords Mobile",
    "info": "ℹ️ اقرأ شرح الأحداث مثل ساحة التنين وKvK وحدث الجحيم",
    "add_info": "ℹ️ [إدارة] أضف شرحًا جديدًا لأحد الأحداث",
    "task": "🎉 [إدارة] أضف مهمة لمهرجان التحالف لعضو محدد",
    "done": "✅ [إدارة] علّم مهمة مهرجان التحالف كمكتملة",
    "board": "🏅 اعرض لوحة صدارة مهرجان التحالف",
    "calc": "🧮 احسب تسريعات مهرجان التحالف أو اسأل عن تبادل الموارد",
    "log_activity": "📋 [إدارة] سجّل مشاركة عضو في نشاط من أنشطة التحالف",
    "stats_event": "📊 اعرض إحصائيات تفاعلية لمشاركة الأعضاء",
    "profile": "🪪 اعرض ملف عضو وإحصائيات مشاركته في التحالف",
    "top5": "🏆 اعرض أكثر خمسة أعضاء نشاطًا في الفعاليات والحشود",
    "event_stats": "📊 اعرض تقرير مشاركة الأعضاء في فعالية محددة",
    "quiz": "🧠 جاوب على سؤال سريع عن Lords Mobile واجمع نقاطًا",
    "reset_stats": "🔄 [إدارة] صفّر سجلات النشاط والمسابقة لأسبوع جديد",
    "hunt_log": "🐾 سجّل نتائج الصيد يدويًا أو من صورة أو من قائمة مجمعة",
    "hunt_channel": "📍 [إدارة] حدد قناة تقارير الصيد والهدف اليومي",
    "hunt_list": "📊 اعرض عدد الوحوش التي اصطادها كل عضو والمتبقي من هدفه",
    "scout": "🔍 أرفق صورة عتاد الخصم أو بروفايله ليحللها الذكاء الاصطناعي",
    "geartiers": "🧰 اعرض تصنيف العتاد للحرب والصيد والاقتصاد",
    "offer": "💱 أضف عرض تبادل موارد لأعضاء التحالف",
    "list": "📋 اعرض عروض تبادل الموارد النشطة في السيرفر",
    "cancel": "🗑️ ألغِ آخر عرض تبادل موارد أضفته",
    "set": "🪖 سجّل أو حدّث نوع قواتك الأساسي",
    "open": "📯 افتح نداء حشد ونبّه الأعضاء بالنوع المطلوب",
    "rally": "📯 افتح نداء حشد ذكي للتحالف",
    "counter": "⚔️ اعرف التشكيلة المضادة الأفضل لتشكيلة العدو",
    "analyze": "🖼️ حلّل صورة تقرير المعركة والأرقام الموجودة بها",
    "shield": "🛡️ شغّل منبه الدرع مع تنبيه قبل 15 دقيقة وتصعيد صوتي",
    "voice_rescue": "🔊 شغّل منبه الدرع مع تصعيد صوتي إذا لم يرد أحد",
    "shelter_done": "✅ أوقف منبه الدرع أو الحماية الحالي",
    "setup": "⚙️ [إدارة] افتح لوحة الإعداد السريع للبوت",
    "setup_check": "🩺 [إدارة] افحص إعدادات البوت والتكاملات والصلاحيات",
    "language": "🌐 [إدارة] حدد لغة ردود البوت في هذا السيرفر",
    "languageme": "🌐 اختر لغة ردود البوت الخاصة بك",
    "bot_channel": "📍 [إدارة] حدد القناة أو الثريد الذي يتحدث فيه البوت",
    "report": "📝 سجّل واستعرض تقارير معارك التحالف",
    "add": "📝 سجّل معركة جديدة في سجل السيرفر",
    "user": "🔍 اعرض سجل معارك عضو محدد",
    "تحديد-روم-الترحيب": "👋 [إدارة] حدد قناة رسائل الأعضاء الجدد",
    "تحديد-صورة-الترحيب": "🖼️ [إدارة] حدد خلفية بطاقة الترحيب",
    "تحديد-رسالة-الترحيب": "✍️ [إدارة] خصص رسالة الترحيب للأعضاء الجدد",
    "استعادة-رسالة-الترحيب": "🔄 [إدارة] أعد رسالة الترحيب الافتراضية",
    "تحديد-روم-القوانين": "📜 [إدارة] حدد قناة زر شاهد القوانين",
    "ارسال-القوانين": "📜 [إدارة] أرسل لوحة القوانين مع زر الموافقة",
    "ارسال-امبيد": "🎨 [إدارة] أرسل Embed مخصصًا إلى قناة تختارها",
}

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
    if lang == "en":
        description = ENGLISH_COMMAND_DESCRIPTIONS.get(path)
        if description is None:
            description = ENGLISH_COMMAND_DESCRIPTIONS.get(command.name)
        if description is None:
            description = f"Open the {path.replace(' ', ' / ')} feature and follow its interactive prompts."
    else:
        description = ARABIC_COMMAND_DESCRIPTIONS.get(path)
        if description is None:
            description = ARABIC_COMMAND_DESCRIPTIONS.get(command.name)
        if description is None:
            meta = CATEGORY_META[command_category(path)]
            description = f"{meta['emoji']} أمر متاح في قسم {meta['ar']}."

        if command.name in WELCOME_COMMANDS:
            welcome_copy = {
                "ارسال-امبيد": "🎨 [إدارة] إرسال Embed احترافي مخصص إلى روم تختاره، مع نص وصورة اختيارية.",
                "ارسال-القوانين": "📜 [إدارة] إرسال لوحة القوانين مع زر موافقة تفاعلي للأعضاء.",
                "استعادة-رسالة-الترحيب": "🔄 [إدارة] إرجاع رسالة الترحيب الافتراضية.",
                "تحديد-رسالة-الترحيب": "✍️ [إدارة] تخصيص نص الترحيب مع متغيرات العضو والداعي والعدد.",
                "تحديد-روم-الترحيب": "👋 [إدارة] اختيار الروم الذي يستقبل رسائل الأعضاء الجدد.",
                "تحديد-روم-القوانين": "📜 [إدارة] تحديد روم القوانين الذي يفتحه زر شاهد القوانين.",
                "تحديد-صورة-الترحيب": "🖼️ [إدارة] تعيين خلفية بطاقة الترحيب.",
        "تحديد-رسالة-القوانين": "📜 [إدارة] تخصيص رسالة القوانين بالعربي والإنجليزي.",
        "استعادة-رسالة-القوانين": "🔄 [إدارة] استعادة رسالة القوانين الافتراضية.",
            }
            description = welcome_copy.get(command.name, description)

    if any(hint in description.lower() for hint in ADMIN_HINTS) or command.name in WELCOME_COMMANDS:
        if not description.startswith("🔒"):
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

    # Discord limits embeds to 25 fields and 6000 total characters. Grouping
    # commands into short blocks prevents /help from silently failing as the
    # command list grows.
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for path, command in commands_in_category:
        line = f"**/{path}**\n{command_description(path, command, lang)}"
        if current and current_size + len(line) + 2 > 850:
            chunks.append("\n\n".join(current))
            current = []
            current_size = 0
        current.append(line)
        current_size += len(line) + 2
    if current:
        chunks.append("\n\n".join(current))

    visible_chunks = chunks[:5]
    for index, chunk in enumerate(visible_chunks, start=1):
        field_name = f"{meta['emoji']} {meta[lang]}"
        if len(chunks) > 1:
            field_name += f" • {index}/{len(chunks)}"
        embed.add_field(name=field_name, value=chunk[:1024], inline=False)

    if len(chunks) > len(visible_chunks):
        remaining = len(commands_in_category) - sum(chunk.count("**/") for chunk in visible_chunks)
        embed.add_field(
            name="📌 المزيد" if lang == "ar" else "📌 More",
            value=(
                f"يوجد {remaining} أمر إضافي في هذا القسم."
                if lang == "ar"
                else f"There are {remaining} more commands in this section."
            ),
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
        description="Open the live command center, organized by function, administration, war, and AI.",
    )
    async def help_cmd(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        try:
            # Build both parts before acknowledging the interaction so Discord
            # receives one valid response even if a newly loaded command is malformed.
            embed = build_intro_embed(self.bot, lang)
            view = HelpView(self.bot, lang)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception:
            log.exception("Failed to render /help")
            fallback = (
                "تعذر تحميل القائمة التفاعلية مؤقتًا. جرّب الأمر مرة أخرى بعد لحظات."
                if lang == "ar"
                else "The interactive help menu could not be loaded. Please try again in a moment."
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(fallback, ephemeral=True)
            else:
                await interaction.followup.send(fallback, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))