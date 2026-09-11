import re
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
from utils.storage import load, save
from utils.i18n import get_lang

STORAGE_REPLIES_KEY = "canned_replies"

def _normalize_trigger(text: str) -> str:
    """Normalize Arabic and English trigger text for reliable matching."""
    s = text.strip().lower()
    for ch in ['أ', 'إ', 'آ', 'ٱ']:
        s = s.replace(ch, 'ا')
    s = s.replace('ة', 'ه').replace('ى', 'ي')
    return ' '.join(s.split())

def expand_shortcuts(text: str, user: discord.User = None, guild: discord.Guild = None) -> str:
    """Replaces '1' or '{everyone}' with @everyone, and handles member/server variables."""
    if not text:
        return ""
    res = text
    if user:
        res = res.replace("{user}", user.mention).replace("{العضو}", user.mention)
    if guild:
        res = res.replace("{server}", guild.name).replace("{السيرفر}", guild.name)

    res = res.replace("{1}", "@everyone").replace("{everyone}", "@everyone").replace("{الكل}", "@everyone")
    res = res.replace("{2}", "@here").replace("{here}", "@here").replace("{هنا}", "@here")

    pattern = r'(?<!\S)1(?!\S)'
    res = re.sub(pattern, "@everyone", res)

    pattern_here = r'(?<!\S)2(?!\S)'
    res = re.sub(pattern_here, "@here", res)

    return res


class RepliesCog(commands.Cog):
    """نظام الردود التلقائية للشات (Auto-Responder) والردود الجاهزة /reply (عربي & English)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_replies(self, guild_id: int) -> dict:
        data = load(STORAGE_REPLIES_KEY)
        return data.get(str(guild_id), {})

    def _save_replies(self, guild_id: int, replies: dict):
        data = load(STORAGE_REPLIES_KEY)
        data[str(guild_id)] = replies
        save(STORAGE_REPLIES_KEY, data)

    # -- Autocomplete for triggers --
    async def reply_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        replies = self._get_replies(interaction.guild_id)
        choices = []
        cur_norm = _normalize_trigger(current)
        for trig in replies.keys():
            if not current or cur_norm in _normalize_trigger(trig):
                choices.append(app_commands.Choice(name=trig[:100], value=trig))
        return choices[:25]

    # -- Core Add Logic --
    async def _handle_add(self, interaction: discord.Interaction, trigger: str, response: str):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        trig = trigger.strip()
        resp = response.strip()

        if not trig or not resp:
            msg = "❌ يجب إدخال الكلمة والرد المطلوب." if lang == "ar" else "❌ Both trigger and response are required."
            await interaction.response.send_message(msg, ephemeral=False)
            return

        replies = self._get_replies(interaction.guild_id)
        replies[trig] = resp
        self._save_replies(interaction.guild_id, replies)

        preview = expand_shortcuts(resp, interaction.user, interaction.guild)
        if lang == "ar":
            embed = discord.Embed(
                title="✅ تم حفظ الرد بنجاح",
                description=(
                    f"**الكلمة المفتاحية:** `{trig}`\n\n"
                    f"**الرد المحفوظ:**\n{preview}\n\n"
                    f"💡 *يعمل كأمر `/reply` وتلقائياً في الشات عند كتابة الكلمة.*"
                ),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="✅ Reply Saved Successfully",
                description=(
                    f"**Trigger phrase:** `{trig}`\n\n"
                    f"**Response:**\n{preview}\n\n"
                    f"💡 *Works via `/reply` and automatically when typed in chat.*"
                ),
                color=discord.Color.green()
            )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # -- Core Delete Logic --
    async def _handle_delete(self, interaction: discord.Interaction, trigger: str):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        replies = self._get_replies(interaction.guild_id)

        target_key = None
        target_norm = _normalize_trigger(trigger)
        for k in replies.keys():
            if _normalize_trigger(k) == target_norm or k.lower() == trigger.strip().lower():
                target_key = k
                break

        if not target_key:
            msg = f"❌ لم يتم العثور على رد مسجل لـ `{trigger}`." if lang == "ar" else f"❌ No reply found for `{trigger}`."
            await interaction.response.send_message(msg, ephemeral=False)
            return

        del replies[target_key]
        self._save_replies(interaction.guild_id, replies)
        msg = f"🗑️ تم حذف الرد لـ `{target_key}` بنجاح." if lang == "ar" else f"🗑️ Reply for `{target_key}` deleted."
        await interaction.response.send_message(msg, ephemeral=False)

    # -- Core List Logic --
    async def _handle_list(self, interaction: discord.Interaction, language: Optional[app_commands.Choice[str]] = None):
        lang = language.value if language else get_lang(interaction.guild_id, interaction.user.id)
        replies = self._get_replies(interaction.guild_id)

        if not replies:
            msg = "ℹ️ لا توجد ردود مسجلة حتى الآن. استخدم `/add_reply` أو `/اضافة_رد`." if lang == "ar" else "ℹ️ No replies registered yet. Use `/add_reply` to create one."
            await interaction.response.send_message(msg, ephemeral=False)
            return

        embed = discord.Embed(
            title="📋 قائمة الردود المسجلة" if lang == "ar" else "📋 Active Replies",
            description="يمكن إرسالها عبر `/reply` أو تُرسل تلقائياً في الشات عند كتابة الكلمة:\n" if lang == "ar" else "Usable via `/reply` or triggered in chat:\n",
            color=discord.Color.blurple()
        )

        for trig, text in list(replies.items())[:25]:
            preview = text[:80] + ("..." if len(text) > 80 else "")
            embed.add_field(name=f"💬 `{trig}`", value=f"↳ {preview}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=False)

    # -- Core Send Reply Logic --
    async def _handle_send_reply(self, interaction: discord.Interaction, trigger: str):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        replies = self._get_replies(interaction.guild_id)

        target_text = None
        target_norm = _normalize_trigger(trigger)
        for k, v in replies.items():
            if _normalize_trigger(k) == target_norm or k.lower() == trigger.strip().lower():
                target_text = v
                break

        if not target_text:
            msg = f"❌ لم يتم العثور على رد مسجل لـ `{trigger}`. استخدم `/replies` لعرض الردود." if lang == "ar" else f"❌ No reply found for `{trigger}`. Use `/replies` to view available replies."
            await interaction.response.send_message(msg, ephemeral=False)
            return

        if "@everyone" in target_text or "1" in target_text:
            perms = interaction.user.guild_permissions
            if not (perms.mention_everyone or perms.manage_messages or perms.administrator):
                msg = "❌ ليس لديك صلاحية إرسال منشن الكل (@everyone)." if lang == "ar" else "❌ You do not have permission to mention everyone."
                await interaction.response.send_message(msg, ephemeral=False)
                return

        expanded = expand_shortcuts(target_text, interaction.user, interaction.guild)
        allowed = discord.AllowedMentions(everyone=True, roles=True, users=True)
        await interaction.response.send_message(expanded, allowed_mentions=allowed)

    # ================= English & Arabic Slash Commands =================

    @app_commands.command(name="reply", description="💬 Send a canned reply to this channel | إرسال رد جاهز")
    @app_commands.describe(trigger="اختر الرد المسجل | Choose registered reply")
    @app_commands.autocomplete(trigger=reply_autocomplete)
    async def reply(self, interaction: discord.Interaction, trigger: str):
        await self._handle_send_reply(interaction, trigger)

    @app_commands.command(name="replies", description="📋 View all active auto-replies | عرض جميع الردود المسجلة")
    @app_commands.describe(language="Display language | لغة العرض")
    @app_commands.choices(language=[
        app_commands.Choice(name="العربية", value="ar"),
        app_commands.Choice(name="English", value="en"),
    ])
    async def replies(self, interaction: discord.Interaction, language: Optional[app_commands.Choice[str]] = None):
        await self._handle_list(interaction, language)

    @app_commands.command(name="add_reply", description="➕ [Admin] Add an auto-reply or canned reply | إضافة رد تلقائي")
    @app_commands.describe(
        trigger="الكلمة أو الجملة (مثال: السلام عليكم أو war) | Trigger phrase",
        response="الرد الذي سيرسله البوت (1 لمنشن everyone) | Bot response (1 for @everyone)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def add_reply(self, interaction: discord.Interaction, trigger: str, response: str):
        await self._handle_add(interaction, trigger, response)

    @app_commands.command(name="delete_reply", description="🗑️ [Admin] Delete a registered reply | حذف رد مسجل")
    @app_commands.describe(trigger="الكلمة المراد حذفها | Trigger phrase to delete")
    @app_commands.autocomplete(trigger=reply_autocomplete)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete_reply(self, interaction: discord.Interaction, trigger: str):
        await self._handle_delete(interaction, trigger)

    # -- Chat Listener (الرد التلقائي الفعلي في الشات) --
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        content = message.content.strip()
        if not content:
            return

        replies = self._get_replies(message.guild.id)
        if not replies:
            return

        norm_msg = _normalize_trigger(content)

        matched_reply = None
        for trig, response_text in replies.items():
            norm_trig = _normalize_trigger(trig)
            if norm_msg == norm_trig or norm_msg.startswith(norm_trig + " ") or norm_msg == "!" + norm_trig:
                matched_reply = response_text
                break

        if matched_reply:
            if "@everyone" in matched_reply or "1" in matched_reply:
                perms = message.author.guild_permissions
                if not (perms.mention_everyone or perms.manage_messages or perms.administrator):
                    return

            expanded = expand_shortcuts(matched_reply, message.author, message.guild)
            allowed = discord.AllowedMentions(everyone=True, roles=True, users=True)
            try:
                await message.channel.send(expanded, allowed_mentions=allowed)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(RepliesCog(bot))
