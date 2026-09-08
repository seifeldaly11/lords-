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
        "en": "𝑨𝑰 𝑨𝒅𝒗𝒊𝒔𝒐𝒓",
        "color": discord.Color.purple(),
    },
    "calculators": {
        "emoji": "🧮",
        "ar": "الحواسب والأدلة السريعة",
        "en": "𝑪𝒂𝒍𝒄𝒖𝒍𝒂𝒕𝒐𝒓𝒔 & 𝑸𝒖𝒊𝒄𝒌 𝑮𝒖𝒊𝒅𝒆𝒔",
        "color": discord.Color.gold(),
    },
    "war": {
        "emoji": "⚔️",
        "ar": "الحرب و 𝑲𝑽𝑲",
        "en": "𝑲𝑽𝑲 & 𝑾𝒂𝒓",
        "color": discord.Color.red(),
    },
    "alliance": {
        "emoji": "🏯",
        "ar": "إدارة التحالف والتتبع",
        "en": "𝑨𝒍𝒍𝒊𝒂𝒏𝒄𝒆 𝑴𝒂𝒏𝒂𝒈𝒆𝒎𝒆𝒏𝒕",
        "color": discord.Color.dark_gold(),
    },
    "market": {
        "emoji": "💱",
        "ar": "بورصة الموارد",
        "en": "𝑹𝒆𝒔𝒐𝒖𝒓𝒄𝒆 𝑴𝒂𝒓𝒌𝒆𝒕",
        "color": discord.Color.green(),
    },
    "hunt": {
        "emoji": "🐾",
        "ar": "متتبع الصيد",
        "en": "𝑯𝒖𝒏𝒕 𝑻𝒓𝒂𝒄𝒌𝒆𝒓",
        "color": discord.Color.dark_green(),
    },
    "shield": {
        "emoji": "🔔",
        "ar": "منبه الدرع",
        "en": "𝑺𝒉𝒊𝒆𝒍𝒅 𝑨𝒍𝒂𝒓𝒎",
        "color": discord.Color.dark_orange(),
    },
    "settings": {
        "emoji": "⚙️",
        "ar": "الإعدادات واللغة",
        "en": "𝑺𝒆𝒕𝒕𝒊𝒏𝒈𝒔 & 𝑳𝒂𝒏𝒈𝒖𝒂𝒈𝒆",
        "color": discord.Color.light_grey(),
    },
    "welcome": {
        "emoji": "👋",
        "ar": "الترحيب والقوانين والـ Embed",
        "en": "𝑾𝒆𝒍𝒄𝒐𝒎𝒆, 𝑹𝒖𝒍𝒆𝒔 & 𝑬𝒎𝒃𝒆𝒅𝒔",
        "color": discord.Color.blue(),
    },
    "games": {
        "emoji": "🎮",
        "ar": "الألعاب والتفاعل",
        "en": "𝑮𝒂𝒎𝒆𝒔 & 𝑰𝒏𝒕𝒆𝒓𝒂𝒄𝒕𝒊𝒐𝒏",
        "color": discord.Color.blurple(),
    },
    "general": {
        "emoji": "📚",
        "ar": "أوامر عامة",
        "en": "𝑮𝒆𝒏𝒆𝒓𝒂𝒍",
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

CATEGORY_BLURBS = {
    "ai": {"ar": "استشارات ذكية وتحليل سريع لأحداث اللعبة.", "en": "Smart advice and fast game analysis."},
    "calculators": {"ar": "حاسبات وأدلة تساعدك تاخد القرار الصح بسرعة.", "en": "Calculators and quick guides for better decisions."},
    "war": {"ar": "خطط الحرب، الكاونترات، وتحليل المعارك.", "en": "War planning, counters, and battle analysis."},
    "alliance": {"ar": "أدوات قيادة ومتابعة نشاط أعضاء التحالف.", "en": "Leadership tools and alliance activity tracking."},
    "market": {"ar": "تابع الموارد والأسعار واتخذ قرارات أذكى.", "en": "Track resources and prices with confidence."},
    "hunt": {"ar": "نظّم الصيد وسجّل النتائج بدون فوضى.", "en": "Organize hunts and track results effortlessly."},
    "shield": {"ar": "تنبيهات الدرع والحماية في الوقت المناسب.", "en": "Shield and protection alerts at the right time."},
    "settings": {"ar": "اضبط اللغة، الإعدادات، وروابط اللعبة.", "en": "Configure language, settings, and game links."},
    "welcome": {"ar": "خلّي دخول الأعضاء الجدد احترافي ومنظم.", "en": "Make every new member feel welcome."},
    "games": {"ar": "ألعاب خفيفة وتفاعل يخلّي التحالف حي.", "en": "Light games and interaction for an active alliance."},
    "general": {"ar": "أدوات يومية مفيدة لكل أعضاء التحالف.", "en": "Everyday utilities for every alliance member."},
}


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
    """Return loaded commands from global and guild-scoped trees.

    Discord can sync commands to a specific guild while the global tree is
    intentionally cleared. The help center must inspect both trees or it will
    incorrectly show 0 commands even though slash commands work normally.
    """
    unique = {}
    command_lists = [bot.tree.get_commands()]
    for guild in getattr(bot, "guilds", []):
        command_lists.append(bot.tree.get_commands(guild=guild))

    for command_list in command_lists:
        for path, command in _walk_commands(command_list):
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

    section_count = sum(1 for key in CATEGORY_ORDER if counts.get(key))
    if lang == "en":
        title = "🏰 𝑳𝒐𝒓𝒅𝒔 𝑴𝒐𝒃𝒊𝒍𝒆 𝑪𝒐𝒎𝒎𝒂𝒏𝒅 𝑪𝒆𝒏𝒕𝒆𝒓"
        description = (
            f"Your alliance tools, organized and ready.\n"
            f"**{len(commands_list)} commands** across **{section_count} sections**.\n\n"
            "Choose a section below to explore what the bot can do."
        )
        count_label = "commands"
        quick_title = "✨ Quick start"
        quick_text = (
            "Start with **/setup** to configure the bot, then use **/language** "
            "to choose Arabic or English replies. Commands marked 🔒 need admin permissions."
        )
        footer = "SeifEldaly • Lords Mobile Alliance Suite • Live command catalog"
        author = "𝑺𝒆𝒊𝒇𝑬𝒍𝒅𝒂𝒍𝒚 • 𝑪𝒐𝒎𝒎𝒂𝒏𝒅 𝑪𝒆𝒏𝒕𝒆𝒓"
    else:
        title = "🏰 مركز أوامر 𝑳𝒐𝒓𝒅𝒔 𝑴𝒐𝒃𝒊𝒍𝒆"
        description = (
            f"كل أدوات تحالفك في مكان واحد، بشكل منظم وسهل.\n"
            f"**{len(commands_list)} أمر** في **{section_count} أقسام**.\n\n"
            "اختار قسم من القائمة تحت عشان تستكشف إمكانيات البوت."
        )
        count_label = "أمر"
        quick_title = "✨ بداية سريعة"
        quick_text = (
            "ابدأ بـ **/setup** لضبط البوت، وبعدها استخدم **/language** لاختيار العربي أو الإنجليزي. "
            "الأوامر التي عليها 🔒 تحتاج صلاحية إدارية."
        )
        footer = "SeifEldaly • Lords Mobile Alliance Suite • كتالوج الأوامر الحي"
        author = "𝑺𝒆𝒊𝒇𝑬𝒍𝒅𝒂𝒍𝒚 • مركز الأوامر"

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(88, 101, 242),
    )
    if bot.user:
        embed.set_author(name=author, icon_url=bot.user.display_avatar.url)
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    for key in CATEGORY_ORDER:
        if not counts.get(key):
            continue
        meta = CATEGORY_META[key]
        blurb = CATEGORY_BLURBS.get(key, {}).get(lang, "")
        category_paths = [
            path for path, _ in commands_list if command_category(path) == key
        ]
        # Show real command names on the landing page; the section view contains
        # the full descriptions. Keep the preview compact for mobile screens.
        preview = "\n".join(f"• `/{path}`" for path in category_paths[:6])
        if len(category_paths) > 6:
            remaining = len(category_paths) - 6
            preview += (
                f"\n• … و{remaining} كمان في القائمة"
                if lang == "ar"
                else f"\n• … and {remaining} more in the menu"
            )
        embed.add_field(
            name=f"{meta['emoji']}  {meta[lang]}",
            value=f"{blurb}\n\n{preview}\n\n**{counts[key]} {count_label}**",
            inline=True,
        )

    embed.add_field(name=quick_title, value=quick_text, inline=False)
    embed.set_footer(text=footer)
    return embed


def build_category_embed(bot: commands.Bot, category: str, lang: str, page: int = 0) -> discord.Embed:
    all_commands = loaded_commands(bot)
    if category == "all":
        meta = {
            "emoji": "📚",
            "ar": "كل الأوامر",
            "en": "All Commands",
            "color": discord.Color.blurple(),
        }
        commands_in_category = all_commands
        blurb = (
            "كل أوامر البوت مرتبة أبجديًا. استخدم الأقسام لو عايز شرحًا أكثر تركيزًا."
            if lang == "ar"
            else "Every loaded command, sorted alphabetically. Use a section for focused details."
        )
    else:
        meta = CATEGORY_META[category]
        commands_in_category = [
            (path, command)
            for path, command in all_commands
            if command_category(path) == category
        ]
        blurb = CATEGORY_BLURBS.get(category, {}).get(lang, "")
    count_text = (
        f"{len(commands_in_category)} أمر متاح في هذا القسم."
        if lang == "ar"
        else f"{len(commands_in_category)} commands available in this section."
    )
    embed = discord.Embed(
        title=f"{meta['emoji']}  {meta[lang]}",
        description=f"{blurb}\n\n**{count_text}**",
        color=meta["color"],
    )
    if bot.user:
        author = "𝑺𝒆𝒊𝒇𝑬𝒍𝒅𝒂𝒍𝒚 • مركز الأوامر" if lang == "ar" else "Lords Mobile • Command Center"
        embed.set_author(name=author, icon_url=bot.user.display_avatar.url)
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    # Discord limits embeds to 25 fields and 6000 total characters. Grouping
    # commands into short blocks keeps every section readable as the bot grows.
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

    page_count = max(1, (len(chunks) + 4) // 5)
    page = max(0, min(page, page_count - 1))
    visible_chunks = chunks[page * 5:(page + 1) * 5]
    for index, chunk in enumerate(visible_chunks, start=1):
        field_name = f"{meta['emoji']}  {meta[lang]}"
        if len(chunks) > 1:
            field_name += f"  •  {index}/{len(chunks)}"
        embed.add_field(name=field_name, value=chunk[:1024], inline=False)

    if page_count > 1:
        embed.add_field(
            name="📄 التنقل" if lang == "ar" else "📄 Navigation",
            value=(
                f"صفحة {page + 1} من {page_count} — استخدم الأزرار تحت القائمة."
                if lang == "ar"
                else f"Page {page + 1} of {page_count} — use the buttons below to browse."
            ),
            inline=False,
        )
    footer = (
        "SeifEldaly • استخدم القائمة والأزرار للتنقل بين كل الأوامر"
        if lang == "ar"
        else "SeifEldaly • Use the menu and buttons to browse every command"
    )
    if page_count > 1:
        footer += f" • {page + 1}/{page_count}"
    embed.set_footer(text=footer)
    return embed


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, lang: str):
        self.bot = bot
        self.lang = lang
        options = [
            discord.SelectOption(
                label="كل الأوامر" if lang == "ar" else "All Commands",
                value="all",
                emoji="📚",
            )
        ]
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
        category = self.values[0]
        await interaction.response.edit_message(
            embed=build_category_embed(self.bot, category, self.lang, page=0),
            view=HelpSectionView(self.bot, self.lang, category, page=0),
        )



class HelpHomeButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, lang: str):
        self.bot = bot
        self.lang = lang
        super().__init__(
            label="الرئيسية" if lang == "ar" else "Home",
            emoji="🏠",
            style=discord.ButtonStyle.secondary,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=build_intro_embed(self.bot, self.lang),
            view=HelpView(self.bot, self.lang),
        )


def _category_page_count(bot: commands.Bot, category: str, lang: str) -> int:
    if category == "all":
        commands_in_category = loaded_commands(bot)
    else:
        commands_in_category = [
            (path, command)
            for path, command in loaded_commands(bot)
            if command_category(path) == category
        ]
    chunks = 0
    current_size = 0
    for path, command in commands_in_category:
        line = f"**/{path}**\n{command_description(path, command, lang)}"
        if current_size and current_size + len(line) + 2 > 850:
            chunks += 1
            current_size = 0
        current_size += len(line) + 2
    if current_size or not chunks:
        chunks += 1
    return chunks


class HelpPageButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, lang: str, category: str, page: int, direction: int):
        self.bot = bot
        self.lang = lang
        self.category = category
        self.page = page
        self.direction = direction
        is_next = direction > 0
        super().__init__(
            label=("التالي" if lang == "ar" else "Next") if is_next else ("السابق" if lang == "ar" else "Back"),
            emoji="▶️" if is_next else "◀️",
            style=discord.ButtonStyle.primary,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        next_page = self.page + self.direction
        await interaction.response.edit_message(
            embed=build_category_embed(self.bot, self.category, self.lang, page=next_page),
            view=HelpSectionView(self.bot, self.lang, self.category, page=next_page),
        )


class HelpSectionView(discord.ui.View):
    def __init__(self, bot: commands.Bot, lang: str, category: str, page: int = 0):
        super().__init__(timeout=600)
        self.bot = bot
        self.lang = lang
        self.category = category
        self.page = page
        self.page_count = _category_page_count(bot, category, lang)
        self.add_item(HelpCategorySelect(bot, lang))
        self.add_item(HelpHomeButton(bot, lang))
        if page > 0:
            self.add_item(HelpPageButton(bot, lang, category, page, -1))
        if page < self.page_count - 1:
            self.add_item(HelpPageButton(bot, lang, category, page, 1))


class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot, lang: str):
        super().__init__(timeout=600)
        self.add_item(HelpCategorySelect(bot, lang))


class HelpCog(commands.Cog):
    """/help - مركز أوامر ديناميكي مناسب لتحالفات كبيرة."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help")
    async def text_help_cmd(self, ctx: commands.Context):
        """Compatibility alias for servers that use the !help prefix command."""
        lang = get_lang(ctx.guild.id if ctx.guild else None, ctx.author.id)
        try:
            # Send the polished card first. Attach the interactive menu separately so
            # a component validation issue never hides the actual help content.
            embed = build_intro_embed(self.bot, lang)
            message = await ctx.send(embed=embed)
            try:
                await message.edit(view=HelpView(self.bot, lang))
            except Exception:
                log.exception("Failed to attach !help menu view")
        except Exception:
            log.exception("Failed to render !help")
            fallback = (
                "تعذر تحميل القائمة التفاعلية مؤقتًا. جرّب الأمر مرة أخرى بعد لحظات."
                if lang == "ar"
                else "The interactive help menu could not be loaded. Please try again in a moment."
            )
            await ctx.send(fallback)

    @app_commands.command(
        name="help",
        description="Open the live command center, organized by function, administration, war, and AI.",
    )
    async def help_cmd(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        try:
            # Acknowledge with the polished card first. The menu is attached in a
            # second request so Discord component errors cannot erase the response.
            embed = build_intro_embed(self.bot, lang)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            try:
                await interaction.edit_original_response(view=HelpView(self.bot, lang))
            except Exception:
                log.exception("Failed to attach /help menu view")
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