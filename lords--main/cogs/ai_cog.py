import asyncio
import logging
import os
import re

import discord
from discord import app_commands
from discord.ext import commands

from utils.knowledge import get_system_prompt
from utils.i18n import get_lang, t
from utils.ui import styled_embed, loading_embed, ROYAL_BLUE
from cogs.guild_cog import gf_group

MAX_INPUT_CHARS = 1500  # حماية ضد الإدخال الطويل جداً
log = logging.getLogger("lordsbot.ai")
TEXT_MODEL = "command-a-03-2025"
VISION_MODEL = "command-a-vision-07-2025"


def _tidy_ai_reply(answer: str) -> str:
    """تنظيف رد الذكاء الاصطناعي والتأكد من صياغة الحسابات بوضوح."""
    answer = (answer or "").strip()
    answer = re.sub(r"ه{4,}", "هههه", answer)
    answer = re.sub(r"(?:ha){4,}", "haha", answer, flags=re.IGNORECASE)
    answer = re.sub(r"(?:ه{2,}[\s!،,.-]*){3,}", "هههه ", answer)
    return answer[:3500]


def _get_cohere_client():
    """يبني عميل Cohere عند الحاجة فقط."""
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        return None
    try:
        import cohere
    except ImportError:
        return None
    return cohere.ClientV2(api_key=api_key)


async def ask_ai(
    user_text: str,
    extra_context: str = "",
    image_url: str | None = None,
    lang: str = "ar",
    guild_id: int | None = None
) -> str:
    """إرسال المطالبة لـ Cohere وحساب الناتج."""
    client = _get_cohere_client()
    if not client:
        return (
            "⚠️ الذكاء الاصطناعي غير متصل حالياً (يرجى التأكد من إضافة COHERE_API_KEY في ملف .env الخاص بالاستضافة)."
            if lang == "ar"
            else "⚠️ AI is not configured. Please ensure COHERE_API_KEY is set in your environment."
        )

    clean_text = (user_text or "").strip()[:MAX_INPUT_CHARS]
    system_prompt = get_system_prompt(guild_id)

    calc_instructions = (
        "\n\n[تعليمات إضافية للمستشار]:\n"
        "- أنت خبير متقدم في حسابات لوردس موبايل (Lords Mobile Calculator).\n"
        "- إذا طُلب منك حساب تسريعات (Speedups): اجمع بدقة كل فئة (أيام، ساعات، دقائق)، ثم أعطِ المجموع الإجمالي بالكامل (مثال: إجمالي الأيام والساعات)، وبيّن هل تكفي للهدف المطلوب أو كم ينقص اللاعب.\n"
        "- إذا طُلب منك حساب أحداث (جحيم Hell، فردي Solo، مهرجان Guild Fest، حرب KvK): احسب نقاط كل مرحلة بدقة، واقترح للاعب هل الموارد/التسريعات تكفي لإكمال المرحلة 3، وأفضل تسلسل للصرف بدون إهدار.\n"
        "- اكتب الناتج مرتباً بنقاط وعناوين واضحة وأرقام واضحة ومباشرة."
    )
    system_prompt += calc_instructions

    messages = [{"role": "system", "content": system_prompt}]

    user_content = []
    full_prompt = clean_text
    if extra_context:
        full_prompt = f"{extra_context}\n\n{clean_text}"

    user_content.append({"type": "text", "text": full_prompt})

    if image_url:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": image_url}
        })

    messages.append({"role": "user", "content": user_content})

    model = VISION_MODEL if image_url else TEXT_MODEL

    try:
        response = await asyncio.to_thread(
            client.chat,
            model=model,
            messages=messages,
            temperature=0.3  # دقة حسابية أعلى
        )
        raw_answer = response.message.content[0].text
        return _tidy_ai_reply(raw_answer)

    except Exception as e:
        log.error("خطأ أثناء استدعاء الذكاء الاصطناعي: %s", e)
        return (
            "حدث خطأ أثناء معالجة الحسابات، يرجى المحاولة بعد لحظات."
            if lang == "ar"
            else "An error occurred while calculating. Please try again."
        )


# ---------------------------------------------------------------------------
# نافذة حاسبة التسريعات (Speedup Calculator Modal)
# ---------------------------------------------------------------------------

class SpeedupCalcModal(discord.ui.Modal, title="⏱️ حاسبة التسريعات الذكية"):
    speedups = discord.ui.TextInput(
        label="⚡ التسريعات المتاحة لديك",
        placeholder="مثال: 15 تسريع 3 أيام، 30 تسريع 24 ساعة، 50 تسريع 3 ساعات، 120 تسريع ساعة...",
        style=discord.TextStyle.paragraph,
        max_length=1000
    )
    goal = discord.ui.TextInput(
        label="🎯 الهدف أو الوقت المطلوب (اختياري)",
        placeholder="مثال: بحث T4 باقي له 75 يوم، أو تطوير قلعة 25، أو حدث تدريب...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        lang = get_lang(interaction.guild_id, interaction.user.id)
        loading_text = "جارٍ جمع التسريعات وحساب الإجمالي بدقة... ⏳" if lang == "ar" else "Calculating total speedups... ⏳"
        loading_msg = await interaction.followup.send(embed=loading_embed(loading_text, lang))

        context = (
            f"[طلب حساب تسريعات]\n"
            f"التسريعات المدخلة:\n{self.speedups.value}\n"
            f"الهدف المطلوب:\n{self.goal.value or 'لا يوجد هدف محدد (المطلوب جمع الإجمالي فقط)'}\n"
            "المطلوب منك:\n"
            "1. تفنيد كل فئة من التسريعات وضربها في عددها.\n"
            "2. إعطاء المجموع الإجمالي بالكامل بوضوح بصيغة: (إجمالي الأيام، والساعات، والدقائق، وما يعادلها بالساعات أو الدقائق الكلية).\n"
            "3. مقارنة المجموع بالهدف المطلوب (إن وجد) وبيان هل يكفي أم لا، وكم الفارق المتبقي أو الزائد.\n"
            "4. تقديم نصيحة ذهبية للاستفادة القصوى أثناء أحداث الجحيم أو التسريع."
        )

        answer = await ask_ai(
            "احسب لي إجمالي التسريعات دي وقارنها بهدفي.",
            extra_context=context,
            lang=lang,
            guild_id=interaction.guild_id
        )

        title = "⏱️ نتيجة حساب التسريعات" if lang == "ar" else "⏱️ Speedup Calculation Result"
        embed = styled_embed(title=title, description=answer[:3500], color=ROYAL_BLUE, lang=lang)
        embed.set_footer(text=f"طلب من: {interaction.user.display_name}")
        try:
            await loading_msg.edit(embed=embed)
        except discord.HTTPException:
            await interaction.followup.send(embed=embed)


# ---------------------------------------------------------------------------
# نافذة حاسبة الأحداث (Event Calculator Modal)
# ---------------------------------------------------------------------------

class EventCalcModal(discord.ui.Modal, title="🏆 حاسبة الأحداث الذكية"):
    event_type = discord.ui.TextInput(
        label="🎪 نوع الحدث والنقاط المطلوبة",
        placeholder="مثال: حدث جحيم تدريب 950 ألف نقطة، أو حدث فردي أبحاث، أو KvK...",
        style=discord.TextStyle.short,
        max_length=200
    )
    resources = discord.ui.TextInput(
        label="📦 ما لديك للصرف (تسريعات / جنود / موارد)",
        placeholder="مثال: 40 يوم تسريعات تدريب، أو 200 ألف جندي T4، أو جواهر...",
        style=discord.TextStyle.paragraph,
        max_length=1000
    )
    goal = discord.ui.TextInput(
        label="🎯 هدفك من الحدث",
        placeholder="مثال: فتح المرحلة 3 (Phase 3)، أو المراكز الأولى، أو أخذ ميداليات الوحش...",
        style=discord.TextStyle.short,
        required=False,
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        lang = get_lang(interaction.guild_id, interaction.user.id)
        loading_text = "جارٍ حساب نقاط الحدث وخطة المرحلة 3... ⏳" if lang == "ar" else "Calculating event points and Phase 3 plan... ⏳"
        loading_msg = await interaction.followup.send(embed=loading_embed(loading_text, lang))

        context = (
            f"[طلب حساب حدث لوردس موبايل]\n"
            f"الحدث والنقاط المطلوبة:\n{self.event_type.value}\n"
            f"المتاح لدى اللاعب:\n{self.resources.value}\n"
            f"هدف اللاعب:\n{self.goal.value or 'إكمال المرحلة 3 بأقل صرف'}\n"
            "المطلوب منك:\n"
            "1. حساب كم نقطة سينال اللاعب بما يملكه بالضبط بناءً على نظام نقاط لوردس موبايل المعروف.\n"
            "2. هل هذا يكفي لإنهاء المرحلة 3 (Phase 3)؟\n"
            "3. إذا كان لا يكفي، كم ينقصه بالضبط؟ وإذا كان يزيد، متى يتوقف حتى لا يهدر موارده؟\n"
            "4. أفضل ترتيب وتنفيذ خطوة بخطوة."
        )

        answer = await ask_ai(
            "احسب لي نقاط هذا الحدث وخطة التنفيذ المناسبة.",
            extra_context=context,
            lang=lang,
            guild_id=interaction.guild_id
        )

        title = "🏆 نتيجة حاسبة الأحداث" if lang == "ar" else "🏆 Event Calculation Result"
        embed = styled_embed(title=title, description=answer[:3500], color=ROYAL_BLUE, lang=lang)
        embed.set_footer(text=f"طلب من: {interaction.user.display_name}")
        try:
            await loading_msg.edit(embed=embed)
        except discord.HTTPException:
            await interaction.followup.send(embed=embed)


# ---------------------------------------------------------------------------
# Cog التعريف والأوامر
# ---------------------------------------------------------------------------

class AICog(commands.Cog):
    """حاسبات ذكية لـ Lords Mobile بالذكاء الاصطناعي."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="حساب_التسريعات",
        description="⏱️ حاسبة التسريعات: تجمع لك التسريعات بدقة وتحسب إجمالي الأيام والساعات"
    )
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def speedup_ar(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SpeedupCalcModal())

    @app_commands.command(
        name="speedup",
        description="⏱️ Speedup calculator: aggregate days, hours and verify against your target"
    )
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def speedup_en(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SpeedupCalcModal())

    @app_commands.command(
        name="حاسبة_الاحداث",
        description="🏆 حاسبة الأحداث: تحسب لك نقاط الجحيم والفردي وتخبرك هل تكفي لإنهاء المرحلة 3"
    )
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def event_ar(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EventCalcModal())

    @app_commands.command(
        name="event_calc",
        description="🏆 Event calculator: calculate Hell/Solo points and Phase 3 completion plan"
    )
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def event_en(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EventCalcModal())


# ---------------------------------------------------------------------------
# /gf optimize - مستشار مهرجان النقابة بالذكاء الاصطناعي
# ---------------------------------------------------------------------------

class GfOptimizeModal(discord.ui.Modal, title="🎉 مستشار مهرجان النقابة"):
    task = discord.ui.TextInput(
        label="📌 المهمة اللي عايز تعملها",
        placeholder="مثال: مهمة تدريب جنود / بناء / بحث",
        style=discord.TextStyle.paragraph
    )
    resources = discord.ui.TextInput(
        label="🎒 اللي معاك (تسريعات/جواهر/أي رقم)",
        placeholder="مثال: 5 ساعات تسريع تدريب، 300 جوهرة، 2 تسريع بناء عام",
        style=discord.TextStyle.paragraph
    )
    goal = discord.ui.TextInput(
        label="🎯 هدفك (اختياري)",
        placeholder="مثال: أعلى نقاط ممكنة بأقل تكلفة",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        lang = get_lang(interaction.guild_id, interaction.user.id)
        loading_text = (
            "جارٍ تحليل مهمة مهرجان النقابة... ⏳" if lang == "ar" else "Analyzing your Guild Festival task... ⏳"
        )
        loading_msg = await interaction.followup.send(embed=loading_embed(loading_text, lang))

        context = (
            f"المهمة المطلوبة: {self.task.value}\n"
            f"الموارد المتاحة لدى اللاعب: {self.resources.value}\n"
            f"الهدف: {self.goal.value or 'أعلى نقاط ممكنة بأقل تكلفة من المخزون'}\n"
            "المطلوب: افهم مهام مهرجان النقابة، واقترح للاعب هل ينفذ المهمة دي بالموارد اللي معاه، "
            "وبكام تقريباً، وإيه أفضل ترتيب لصرف موارده عشان ياخد أعلى نقاط ممكنة."
        )
        answer = await ask_ai(
            "اقترح عليّ أفضل طريقة أنفذ بيها مهمة مهرجان النقابة دي بالموارد اللي معايا.",
            extra_context=context,
            lang=lang,
            guild_id=interaction.guild_id
        )
        header = t("ai_header", lang)
        embed = styled_embed(title=f"🎉 {header}", description=answer[:3500], color=ROYAL_BLUE, lang=lang)
        try:
            await loading_msg.edit(embed=embed)
        except discord.HTTPException:
            await interaction.followup.send(embed=embed)


@gf_group.command(name="optimize", description="🤖 مستشار AI يقترح أفضل طريقة لتنفيذ مهمة مهرجان النقابة بمواردك")
@app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
async def gf_optimize(interaction: discord.Interaction):
    await interaction.response.send_modal(GfOptimizeModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(AICog(bot))
