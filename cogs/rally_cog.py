"""
نداء الحشود الذكي: /troop set (تسجيل نوع قواتك) و /rally set (نداء حشد
بيستدعي الأعضاء أصحاب النوع المطلوب فقط، مع عد تنازلي حي وزرار يفتح التطبيق)،
بالإضافة لـ /rally_log (إدارة) لتسجيل حضور ونتيجة الحشود الفعلية في سجل دائم
يتقرا منه بعدين في /information.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load, save, get_game_link
from utils.i18n import get_lang, t

TROOP_FILE = "member_troops"
RALLY_LOG_FILE = "rally_log"
DEFAULT_APP_LINK = os.getenv("GAME_APP_LINK", "https://www.lordsmobile.com/")

RALLY_TYPE_LABELS = {"attack": "⚔️ هجوم", "defense": "🛡️ دفاع"}
RALLY_RESULT_LABELS = {"win": "🏆 فوز", "loss": "❌ خسارة", "draw": "🤝 تعادل"}

TROOP_LABELS = {
    "infantry": {"ar": "🛡️ مشاة", "en": "🛡️ Infantry"},
    "ranged": {"ar": "🏹 رماة", "en": "🏹 Ranged"},
    "cavalry": {"ar": "🐎 فرسان", "en": "🐎 Cavalry"},
    "siege": {"ar": "🏰 حصار", "en": "🏰 Siege"},
    "hybrid": {"ar": "🔀 هجين (كل الأنواع)", "en": "🔀 Hybrid (all types)"},
}


def troop_label(troop: str, lang: str) -> str:
    return TROOP_LABELS.get(troop, {}).get(lang, troop)


# ---------------------------------------------------------------------------
# /troop set
# ---------------------------------------------------------------------------

troop_group = app_commands.Group(name="troop", description="🪖 تسجيل/عرض نوع قواتك الأساسي | Register/view your main troop type")


@troop_group.command(name="set", description="سجّل نوع قواتك الأساسي عشان توصلك تنبيهات /rally المناسبة | Register your main troop type")
@app_commands.choices(
    troop=[app_commands.Choice(name=TROOP_LABELS[k]["ar"] + " / " + TROOP_LABELS[k]["en"], value=k) for k in TROOP_LABELS]
)
async def troop_set(interaction: discord.Interaction, troop: app_commands.Choice[str]):
    lang = get_lang(interaction.guild_id)
    data = load(TROOP_FILE)
    gid = str(interaction.guild_id)
    data.setdefault(gid, {})
    data[gid][str(interaction.user.id)] = {"troop": troop.value, "name": str(interaction.user)}
    save(TROOP_FILE, data)
    await interaction.response.send_message(
        t("troop_set_success", lang, troop=troop_label(troop.value, lang)), ephemeral=True
    )


# ---------------------------------------------------------------------------
# /rally set
# ---------------------------------------------------------------------------

rally_group = app_commands.Group(name="rally", description="📯 نداء حشود يستهدف الأعضاء بالنوع المطلوب | Smart rally calls")


@rally_group.command(name="set", description="افتح نداء حشد وينبّه بس أصحاب القوات المتوافقة | Open a rally ping for matching troop owners")
@app_commands.describe(
    troop="نوع القوات المطلوبة للحشد | Troop type needed",
    minutes="بعد كام دقيقة هيتقفل الحشد تقريباً (افتراضي 5) | Minutes until the rally closes (default 5)",
    note="ملاحظة اختيارية (هدف الحشد مثلاً) | Optional note (rally target, etc.)",
)
@app_commands.choices(
    troop=[app_commands.Choice(name=TROOP_LABELS[k]["ar"] + " / " + TROOP_LABELS[k]["en"], value=k) for k in TROOP_LABELS if k != "hybrid"]
)
async def rally_set(interaction: discord.Interaction, troop: app_commands.Choice[str], minutes: int = 5, note: str = None):
    lang = get_lang(interaction.guild_id)
    data = load(TROOP_FILE)
    gid = str(interaction.guild_id)
    members = data.get(gid, {})

    matched_ids = [uid for uid, info in members.items() if info.get("troop") in (troop.value, "hybrid")]
    mentions = " ".join(f"<@{uid}>" for uid in matched_ids[:50])

    deadline = datetime.now(timezone.utc) + timedelta(minutes=max(1, minutes))
    countdown = discord.utils.format_dt(deadline, style="R")

    desc = t(
        "rally_desc",
        lang,
        leader=interaction.user.mention,
        troop=troop_label(troop.value, lang),
        countdown=countdown,
    )
    if note:
        desc += f"\n\n**{t('rally_note_field', lang)}:** {note}"
    if not mentions:
        desc += f"\n\n{t('rally_no_matches', lang)}"
    else:
        desc += t("rally_no_troop_note", lang)

    view = discord.ui.View()
    app_link = get_game_link(interaction.guild_id, default=DEFAULT_APP_LINK)
    view.add_item(discord.ui.Button(label=t("rally_open_app", lang), style=discord.ButtonStyle.link, url=app_link, emoji="📲"))

    header = t("rally_title", lang)
    ping_line = f"{t('rally_pinged', lang)}: {mentions}" if mentions else ""

    await interaction.response.send_message(
        content=f"# {header}\n{desc}\n{ping_line}".strip(),
        view=view,
        allowed_mentions=discord.AllowedMentions(users=True),
    )


class RallyCog(commands.Cog):
    """نداء الحشود الذكي وتسجيل نوع القوات."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="rally_log",
        description="👥 (إدارة) سجّل حضور حشد: الأعضاء المشاركين ونوعه (هجوم/دفاع) ونتيجته",
    )
    @app_commands.describe(
        rally_type="نوع الحشد",
        result="نتيجة الحشد",
        note="ملاحظة اختيارية (هدف الحشد مثلاً)",
    )
    @app_commands.choices(
        rally_type=[
            app_commands.Choice(name="⚔️ هجوم", value="attack"),
            app_commands.Choice(name="🛡️ دفاع", value="defense"),
        ],
        result=[
            app_commands.Choice(name="🏆 فوز", value="win"),
            app_commands.Choice(name="❌ خسارة", value="loss"),
            app_commands.Choice(name="🤝 تعادل", value="draw"),
        ],
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def rally_log(
        self,
        interaction: discord.Interaction,
        rally_type: app_commands.Choice[str],
        result: app_commands.Choice[str],
        note: Optional[str] = None,
    ):
        view = RallyLogView(rally_type.value, result.value, note, str(interaction.user))
        await interaction.response.send_message(
            "اختر الأعضاء المشاركين في الحشد من القائمة تحت، وبعدين دوس **تأكيد التسجيل**:",
            view=view,
            ephemeral=True,
        )

    @rally_log.error
    async def rally_log_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ الأمر ده مخصص للإدارة فقط (صلاحية Manage Server).", ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ حصل خطأ غير متوقع.", ephemeral=True)


class RallyLogView(discord.ui.View):
    """نافذة اختيار الأعضاء المشاركين في الحشد (حتى 25 عضو دفعة واحدة) وتأكيد التسجيل."""

    def __init__(self, rally_type: str, result: str, note: Optional[str], logged_by: str):
        super().__init__(timeout=180)
        self.rally_type = rally_type
        self.result = result
        self.note = note
        self.logged_by = logged_by
        self.selected_ids: list[int] = []

        self.user_select = discord.ui.UserSelect(
            placeholder="اختر الأعضاء المشاركين في الحشد...", min_values=1, max_values=25
        )
        self.user_select.callback = self.on_select
        self.add_item(self.user_select)

    async def on_select(self, interaction: discord.Interaction):
        self.selected_ids = [u.id for u in self.user_select.values]
        await interaction.response.send_message(
            f"✅ اخترت **{len(self.selected_ids)}** عضو. دوس زرار \"تأكيد التسجيل\" تحت عشان تحفظ.",
            ephemeral=True,
        )

    @discord.ui.button(label="✅ تأكيد التسجيل", style=discord.ButtonStyle.success, row=1)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_ids:
            await interaction.response.send_message("❌ لازم تختار عضو واحد على الأقل قبل التأكيد.", ephemeral=True)
            return

        data = load(RALLY_LOG_FILE)
        gid = str(interaction.guild_id)
        data.setdefault(gid, {"entries": []})
        entry = {
            "members": self.selected_ids,
            "rally_type": self.rally_type,
            "result": self.result,
            "note": self.note or "-",
            "logged_by": self.logged_by,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        data[gid]["entries"].append(entry)
        save(RALLY_LOG_FILE, data)

        mentions = "، ".join(f"<@{uid}>" for uid in self.selected_ids)
        embed = discord.Embed(title="✅ تم تسجيل حضور الحشد", color=discord.Color.green())
        embed.add_field(name="🧭 النوع", value=RALLY_TYPE_LABELS[self.rally_type], inline=True)
        embed.add_field(name="🏆 النتيجة", value=RALLY_RESULT_LABELS[self.result], inline=True)
        embed.add_field(name="👥 الأعضاء المشاركون", value=mentions, inline=False)
        if self.note and self.note != "-":
            embed.add_field(name="📝 ملاحظة", value=self.note, inline=False)
        embed.set_footer(text=f"سجّله: {self.logged_by}")

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=None, embed=embed, view=self)


async def setup(bot: commands.Bot):
    await bot.add_cog(RallyCog(bot))
    bot.tree.add_command(troop_group)
    bot.tree.add_command(rally_group)
