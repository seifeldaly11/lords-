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
    # collapse multiple spaces
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

    # Replace '1' or '{1}' or '{everyone}' or '{الكل}' with @everyone
    res = res.replace("{1}", "@everyone").replace("{everyone}", "@everyone").replace("{الكل}", "@everyone")
    res = res.replace("{2}", "@here").replace("{here}", "@here").replace("{هنا}", "@here")

    # Replace standalone number 1 surrounded by space or punctuation or at start/end
    pattern = r'(?<!\S)1(?!\S)'
    res = re.sub(pattern, "@everyone", res)

    pattern_here = r'(?<!\S)2(?!\S)'
    res = re.sub(pattern_here, "@here", res)

    return res


class RepliesCog(commands.Cog):
    """نظام الردود التلقائية للشات (Auto-Responder) واختصارات الردود (عربي & English)"""

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

    # -- /add_reply (إضافة رد تلقائي) --
    @app_commands.command(
        name="add_reply",
        description="💬 [إدارة/Admin] إضافة رد تلقائي للشات | Add auto-reply for chat messages"
    )
    @app_commands.describe(
        trigger="الكلمة أو الجملة (مثال: السلام عليكم أو war) | Trigger phrase (e.g. السلام عليكم or war)",
        response="الرد الذي سيرسله البوت (اكتب 1 لمنشن everyone) | Bot response (write 1 for @everyone)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def add_reply(self, interaction: discord.Interaction, trigger: str, response: str):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        trig = trigger.strip()
        resp = response.strip()

        if not trig or not resp:
            msg = "❌ يجب إدخال الكلمة المفتاحية والرد المطلوب." if lang == "ar" else "❌ Both trigger phrase and response are required."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        replies = self._get_replies(interaction.guild_id)
        # Store under normalized key for matching, but keep display
        replies[trig] = resp
        self._save_replies(interaction.guild_id, replies)

        preview = expand_shortcuts(resp, interaction.user, interaction.guild)
        if lang == "ar":
            embed = discord.Embed(
                title="✅ تم حفظ الرد التلقائي بنجاح",
                description=(
                    f"**عندما يكتب أحد في الشات:**\n`{trig}`\n\n"
                    f"**سيرد البوت فوراً بـ:**\n{preview}\n\n"
                    f"*(ملاحظة: اختصار `1` تم تحويله إلى `@everyone`)*"
                ),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="✅ Auto-Reply Saved Successfully",
                description=(
                    f"**When someone types in chat:**\n`{trig}`\n\n"
                    f"**The bot will reply with:**\n{preview}\n\n"
                    f"*(Note: shortcut `1` is expanded to `@everyone`)*"
                ),
                color=discord.Color.green()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -- /delete_reply (حذف رد تلقائي) --
    @app_commands.command(
        name="delete_reply",
        description="🗑️ [إدارة/Admin] حذف رد تلقائي | Delete an auto-reply"
    )
    @app_commands.describe(trigger="الكلمة أو الرد المراد حذفه | Trigger phrase to delete")
    @app_commands.autocomplete(trigger=reply_autocomplete)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete_reply(self, interaction: discord.Interaction, trigger: str):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        replies = self._get_replies(interaction.guild_id)

        target_key = None
        target_norm = _normalize_trigger(trigger)
        for k in replies.keys():
            if _normalize_trigger(k) == target_norm or k.lower() == trigger.strip().lower():
                target_key = k
                break

        if not target_key:
            msg = f"❌ لم يتم العثور على رد مسجل لـ `{trigger}`." if lang == "ar" else f"❌ No auto-reply found for `{trigger}`."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        del replies[target_key]
        self._save_replies(interaction.guild_id, replies)
        msg = f"🗑️ تم حذف الرد التلقائي لـ `{target_key}` بنجاح." if lang == "ar" else f"🗑️ Auto-reply for `{target_key}` deleted."
        await interaction.response.send_message(msg, ephemeral=True)

    # -- /replies (قائمة الردود التلقائية) --
    @app_commands.command(
        name="replies",
        description="📋 عرض جميع الردود التلقائية المسجلة | View all active auto-replies"
    )
    @app_commands.describe(language="اختر لغة العرض | Display language")
    @app_commands.choices(language=[
        app_commands.Choice(name="العربية", value="ar"),
        app_commands.Choice(name="English", value="en"),
    ])
    async def list_replies(self, interaction: discord.Interaction, language: Optional[app_commands.Choice[str]] = None):
        lang = language.value if language else get_lang(interaction.guild_id, interaction.user.id)
        replies = self._get_replies(interaction.guild_id)

        if not replies:
            msg = "ℹ️ لا توجد ردود تلقائية مسجلة حتى الآن. استخدم `/add_reply` لإضافة أول رد." if lang == "ar" else "ℹ️ No auto-replies registered yet. Use `/add_reply` to create one."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed = discord.Embed(
            title="📋 قائمة الردود التلقائية في الشات" if lang == "ar" else "📋 Active Chat Auto-Replies",
            description="بمجرد كتابة الكلمة في أي روم، سيرد البوت مباشرة:\n" if lang == "ar" else "Whenever a member types the trigger, the bot responds:\n",
            color=discord.Color.blurple()
        )

        for trig, text in list(replies.items())[:20]:
            preview = text[:80] + ("..." if len(text) > 80 else "")
            embed.add_field(name=f"💬 إذا قيل: `{trig}`", value=f"↳ يرد: {preview}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

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

        # Match trigger
        matched_reply = None
        for trig, response_text in replies.items():
            norm_trig = _normalize_trigger(trig)
            # Match exact phrase or message starting with trigger
            if norm_msg == norm_trig or norm_msg.startswith(norm_trig + " ") or norm_msg == "!" + norm_trig:
                matched_reply = response_text
                break

        if matched_reply:
            # Check permissions for mass mentions like @everyone
            if "@everyone" in matched_reply or "1" in matched_reply:
                perms = message.author.guild_permissions
                if not (perms.mention_everyone or perms.manage_messages or perms.administrator):
                    return  # Skip if sender does not have permission to ping everyone

            expanded = expand_shortcuts(matched_reply, message.author, message.guild)
            allowed = discord.AllowedMentions(everyone=True, roles=True, users=True)
            try:
                await message.channel.send(expanded, allowed_mentions=allowed)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(RepliesCog(bot))
