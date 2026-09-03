"""
لمسات التصميم البصري الموحّدة للبوت: باليت ألوان ثابت، أشرطة تقدم بالإيموجي،
وهيلبرز لبناء Embeds بشكل احترافي وموحّد (Footer + Thumbnail شارة التحالف).

الهدف: أي كوج يقدر يستورد من هنا بدل ما يكرر ألوان/فوتر عشوائي في كل ملف،
عشان شكل البوت يبقى متسق بصرياً في كل مكان.
"""
from datetime import datetime, timezone

import discord

# ---------------------------------------------------------------------------
# باليت الألوان الرسمي للبوت
# ---------------------------------------------------------------------------
GOLD = discord.Color.from_str("#FFD700")      # أساسي / حرب
CRIMSON = discord.Color.from_str("#DC143C")   # تنبيهات / دروع
ROYAL_BLUE = discord.Color.from_str("#4169E1")  # معلومات / مساعدة
EMERALD = discord.Color.from_str("#2ECC71")   # نجاح / تأكيد

BOT_NAME = "المعلم صابر"
BOT_CREST_URL: str | None = None  # حط لينك صورة شارة التحالف هنا لو حابب يظهر كـ Thumbnail بكل Embed


def progress_bar(value: float, total: float, length: int = 10) -> str:
    """شريط تقدم مرئي بالإيموجي، زي [████████░░] 80%."""
    total = max(total, 0.0001)
    ratio = max(0.0, min(1.0, value / total))
    filled = round(ratio * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"`[{bar}]` **{ratio * 100:.0f}%**"


def styled_embed(
    title: str,
    description: str | None = None,
    color: discord.Color = GOLD,
    lang: str = "ar",
    thumbnail_url: str | None = None,
) -> discord.Embed:
    """Embed بالباليت الموحّد + Footer فيه اسم البوت ووقت آخر تحديث."""
    embed = discord.Embed(title=title, description=description, color=color)
    ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
    footer_text = (
        f"⚔️ {BOT_NAME} • آخر تحديث {ts}"
        if lang == "ar"
        else f"⚔️ {BOT_NAME} • Last update {ts}"
    )
    embed.set_footer(text=footer_text)
    crest = thumbnail_url or BOT_CREST_URL
    if crest:
        embed.set_thumbnail(url=crest)
    return embed


def loading_embed(text: str, lang: str = "ar") -> discord.Embed:
    """رسالة تحميل مؤقتة (Loading State) قبل إظهار النتيجة النهائية."""
    return styled_embed(
        title="⏳ جاري التحليل..." if lang == "ar" else "⏳ Analyzing...",
        description=text,
        color=ROYAL_BLUE,
        lang=lang,
    )
