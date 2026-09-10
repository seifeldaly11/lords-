import re
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
from utils.storage import load, save
from utils.i18n import get_lang, t

STORAGE_REPLIES_KEY = "canned_replies"
STORAGE_MACROS_KEY = "canned_macros"

# Default built-in shortcuts
DEFAULT_MACROS = {
    "1": "@everyone",
    "{1}": "@everyone",
    "{everyone}": "@everyone",
    "{الكل}": "@everyone",
    "2": "@here",
    "{2}": "@here",
    "{here}": "@here",
    "{هنا}": "@here",
}

def expand_shortcuts(text: str, guild_id: int, user: discord.User = None, guild: discord.Guild = None) -> str:
    """Expand macros such as '1' or '{everyone}' into @everyone and other dynamic tags."""
    if not text:
        return ""

    macros = dict(DEFAULT_MACROS)
    # Load custom macros for this guild
    data = load(STORAGE_MACROS_KEY)
    custom = data.get(str(guild_id), {})
    macros.update(custom)

    res = text
    # Replace dynamic tags
    if user:
        res = res.replace("{user}", user.mention).replace("{العضو}", user.mention)
    if guild:
        res = res.replace("{server}", guild.name).replace("{السيرفر}", guild.name)

    # Word-boundary or token replacement for macros like '1'
    for k, v in macros.items():
        if k.startswith("{") and k.endswith("}"):
            res = res.replace(k, v)
        else:
            # Replace standalone word or number token (e.g., '1 ' or ' 1' or line starting with '1')
            pattern = rf'(?<!\S){re.escape(k)}(?!\S)'
            res = re.sub(pattern, v, res)

    return res


class RepliesCog(commands.Cog):
    """نظام الردود الجاهزة والاختصارات الذكية (عربي & English)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_replies(self, guild_id: int) -> dict:
        data = load(STORAGE_REPLIES_KEY)
        return data.get(str(guild_id), {})

    def _save_replies(self, guild_id: int, replies: dict):
        data = load(STORAGE_REPLIES_KEY)
        data[str(guild_id)] = replies
        save(STORAGE_REPLIES_KEY, data)

    # -- Autocomplete for replies --
    async def reply_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        replies = self._get_replies(interaction.guild_id)
        choices = []
        for trigger in replies.keys():
            if current.lower() in trigger.lower():
                choices.append(app_commands.Choice(name=trigger[:100], value=trigger))
        return choices[:25]

    # -- /add_reply --
    @app_commands.command(
        name="add_reply",
        description="💬 [إدارة/Admin] إضافة رد جاهز مع دعم الاختصارات | Add canned reply with shortcuts"
    )
    @app_commands.describe(
        trigger="الكلمة المفتاحية أو الاختصار (مثال: war) | Trigger keyword (e.g. war)",
        response="نص الرد الكامل (اكتب 1 لمنشن everyone) | Full response (type 1 for @everyone)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def add_reply(self, interaction: discord.Interaction, trigger: str, response: str):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        trig = trigger.strip().lower()
        if not trig or not response.strip():
            msg = "❌ يجب إدخال الكلمة المفتاحية والرد." if lang == "ar" else "❌ Both trigger and response are required."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        replies = self._get_replies(interaction.guild_id)
        replies[trig] = response.strip()
        self._save_replies(interaction.guild_id, replies)

        preview = expand_shortcuts(response.strip(), interaction.guild_id, interaction.user, interaction.guild)
        if lang == "ar":
            embed = discord.Embed(
                title="✅ تم حفظ الرد الجاهز بنجاح",
                description=f"**الكلمة المفتاحية:** `{trig}`\n**الرد المسجل:**\n{response}\n\n**المعاينة بعد فك الاختصارات:**\n{preview}",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="✅ Canned Reply Saved Successfully",
                description=f"**Trigger:** `{trig}`\n**Stored Response:**\n{response}\n\n**Preview after expansion:**\n{preview}",
                color=discord.Color.green()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -- /delete_reply --
    @app_commands.command(
        name="delete_reply",
        description="🗑️ [إدارة/Admin] حذف رد جاهز | Delete a canned reply"
    )
    @app_commands.describe(trigger="الكلمة المفتاحية المراد حذفها | Trigger keyword to delete")
    @app_commands.autocomplete(trigger=reply_autocomplete)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete_reply(self, interaction: discord.Interaction, trigger: str):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        trig = trigger.strip().lower()
        replies = self._get_replies(interaction.guild_id)

        if trig not in replies:
            msg = f"❌ لم يتم العثور على رد جاهز باسم `{trig}`." if lang == "ar" else f"❌ No canned reply found for `{trig}`."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        del replies[trig]
        self._save_replies(interaction.guild_id, replies)
        msg = f"🗑️ تم حذف الرد الجاهز `{trig}` بنجاح." if lang == "ar" else f"🗑️ Canned reply `{trig}` deleted successfully."
        await interaction.response.send_message(msg, ephemeral=True)

    # -- /replies (List) --
    @app_commands.command(
        name="replies",
        description="📋 عرض قائمة الردود الجاهزة المسجلة | View list of canned replies"
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
            msg = "ℹ️ لا توجد ردود جاهزة مسجلة حالياً. استخدم `/add_reply` لإضافة رد." if lang == "ar" else "ℹ️ No canned replies saved yet. Use `/add_reply` to create one."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed = discord.Embed(
            title="📋 الردود الجاهزة المسجلة" if lang == "ar" else "📋 Registered Canned Replies",
            description="يمكنك كتابة الكلمة المفتاحية في الشات أو استخدام أمر `/reply`:\n" if lang == "ar" else "You can type the trigger in chat or use `/reply`:\n",
            color=discord.Color.blurple()
        )

        for trig, text in list(replies.items())[:20]:
            preview = text[:80] + ("..." if len(text) > 80 else "")
            embed.add_field(name=f"🔑 `{trig}`", value=preview, inline=False)

        embed.set_footer(text="اختصار 1 يتحول إلى @everyone تلقائياً" if lang == "ar" else "Shortcut 1 automatically expands to @everyone")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -- /reply (Send reply command) --
    @app_commands.command(
        name="reply",
        description="🚀 إرسال رد جاهز في الروم الحالي | Send a canned reply to this channel"
    )
    @app_commands.describe(trigger="اختر الرد الجاهز | Choose canned reply")
    @app_commands.autocomplete(trigger=reply_autocomplete)
    async def send_reply_cmd(self, interaction: discord.Interaction, trigger: str):
        trig = trigger.strip().lower()
        replies = self._get_replies(interaction.guild_id)
        lang = get_lang(interaction.guild_id, interaction.user.id)

        if trig not in replies:
            msg = f"❌ الرد الجاهز `{trig}` غير موجود." if lang == "ar" else f"❌ Reply `{trig}` not found."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        raw_text = replies[trig]
        expanded = expand_shortcuts(raw_text, interaction.guild_id, interaction.user, interaction.guild)

        # Allow actual @everyone and role mentions
        allowed = discord.AllowedMentions(everyone=True, roles=True, users=True)
        await interaction.response.send_message(expanded, allowed_mentions=allowed)

    # -- Chat listener for auto-trigger --
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        content = message.content.strip()
        if not content:
            return

        # Check if the message is exactly the trigger, or starts with '!' followed by trigger
        clean_word = content.lower()
        if clean_word.startswith("!"):
            clean_word = clean_word[1:]

        replies = self._get_replies(message.guild.id)
        if clean_word in replies:
            # Check permissions: if response contains @everyone, sender must have mention_everyone or manage_messages
            raw_text = replies[clean_word]
            if "1" in raw_text or "@everyone" in raw_text or "{everyone}" in raw_text:
                perms = message.author.guild_permissions
                if not (perms.mention_everyone or perms.manage_messages or perms.administrator):
                    return  # Prevent unauthorized members from triggering mass pings

            expanded = expand_shortcuts(raw_text, message.guild.id, message.author, message.guild)
            allowed = discord.AllowedMentions(everyone=True, roles=True, users=True)
            try:
                await message.channel.send(expanded, allowed_mentions=allowed)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(RepliesCog(bot))
