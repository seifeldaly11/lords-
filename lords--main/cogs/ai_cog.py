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

MAX_INPUT_CHARS = 1200  # حماية بسيطة ضد الإدخال الطويل جداً/إساءة الاستخدام
log = logging.getLogger("lordsbot.ai")
# command-r-plus was removed by Cohere on 2025-09-15.
# command-a-03-2025 is an active chat model.
TEXT_MODEL = "command-a-03-2025"
VISION_MODEL = "command-a-vision-07-2025"  # موديل Cohere اللي بيقدر يفهم صور (عتاد/تقارير)


def _tidy_ai_reply(answer: str) -> str:
    """يمنع الضحك المتكرر من ابتلاع الرد، مع الإبقاء على لمسة الهزار."""
    answer = (answer or "").strip()
    answer = re.sub(r"ه{4,}", "هههه", answer)
    answer = re.sub(r"(?:ha){4,}", "haha", answer, flags=re.IGNORECASE)
    answer = re.sub(r"(?:ه{2,}[\s!،,.-]*){3,}", "هههه ", answer)
    answer = re.sub(r"(?:(?:ha){1,2}[\s!,.؟?-]*){3,}", "haha ", answer, flags=re.IGNORECASE)
    return answer[:3500]


def _get_cohere_client():
    """يبني عميل Cohere عند الحاجة فقط، ويرجع None لو التوكن مش موجود."""
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        return None
    try:
        import cohere
    except ImportError:
        return None
    return cohere.ClientV2(api_key=api_key)


async def ask_ai(user_text: str, extra_context: str = "", image_url: str | None = None, lang: str = "ar", guild_id: int | None = None) -> str:
    """يبعت سؤال (ونص/صورة اختيارية) لـ Cohere مع الشخصية وقاعدة المعرفة، ويرجع الرد كنص."""
    client = _get_cohere_client()
    if client is None:
        return t("ai_disabled", lang)

    user_text = (user_text or "").strip()[:MAX_INPUT_CHARS]
    system_prompt = get_system_prompt(lang, guild_id=guild_id)
    if extra_context:
        system_prompt += f"\n\n### سياق إضافي للطلب الحالي:\n{extra_context[:MAX_INPUT_CHARS]}"

    if image_url:
        model = VISION_MODEL
        user_content = [
            {"type": "text", "text": user_text or ("حلل الصورة دي" if lang == "ar" else "Analyze this image")},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    else:
        model = TEXT_MODEL
        user_content = user_text

    def _call():
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
        )
        # cohere ClientV2 response: response.message.content هي قائمة أجزاء نصية
        try:
            return "".join(part.text for part in response.message.content if hasattr(part, "text"))
        except Exception:
            return str(response)

    try:
        return _tidy_ai_reply(await asyncio.to_thread(_call))
    except Exception as e:
        # Keep the user-facing message safe while logging enough detail for hosting diagnostics.
        log.exception(
            "Cohere request failed (model=%s, has_image=%s, error=%s)",
            model,
            bool(image_url),
            type(e).__name__
        )
        return t("ai_error", lang, err=type(e).__name__)


# ---------------------------------------------------------------------------
# /ai - محادثة عامة عن اللعبة + تحليل صور عتاد/تقارير
# ---------------------------------------------------------------------------

class AICog(commands.Cog):
    """مساعد ذكي مبني على Cohere يفهم لوردس موبايل ويتكلم بشكل طبيعي (نص وصور)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ai",
        description="🤖 اسأل مستشار لوردس أو أرفق صورة عتاد/تقرير لتحليلها"
    )
    @app_commands.describe(
        question="Your question (optional if attaching an image)",
        image="A gear or battle report screenshot to analyze",
        might="Your account Might, if you want it in context"
    )
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def ai(
        self,
        interaction: discord.Interaction,
        question: str = None,
        image: discord.Attachment = None,
        might: int = None
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)

        if not question and not image:
            await interaction.response.send_message(t("ai_need_input", lang), ephemeral=True)
            return

        if image and not (image.content_type or "").startswith("image/"):
            await interaction.response.send_message(t("ai_bad_image", lang))
            return

        await interaction.response.defer(thinking=True)

        loading_text = (
            "جارٍ فحص التشكيلة والتكتيكات... ⏳" if lang == "ar" else "Analyzing tactics and formations... ⏳"
        )
        loading_msg = await interaction.followup.send(embed=loading_embed(loading_text, lang))

        extra_context = ""
        if might is not None:
            extra_context += t("ai_might_line", lang, might=might)

        answer = await ask_ai(
            question,
            extra_context=extra_context,
            image_url=image.url if image else None,
            lang=lang,
            guild_id=interaction.guild_id
        )

        header = t("ai_header", lang)
        footer = t("ai_footer", lang, user=interaction.user.display_name)
        embed = styled_embed(title=header, description=answer[:3500], color=ROYAL_BLUE, lang=lang)
        embed.set_footer(text=footer)
        try:
            await loading_msg.edit(embed=embed)
        except discord.HTTPException:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @ai.error
    async def ai_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(t("ai_cooldown", lang, s=f"{error.retry_after:.0f}"), ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)


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
