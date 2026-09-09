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
from utils.i18n import get_lang, t, RALLY_TYPE_LABELS_I18N, RALLY_RESULT_LABELS_I18N

TROOP_FILE = "member_troops"
RALLY_LOG_FILE = "rally_log"
DEFAULT_APP_LINK = os.getenv("GAME_APP_LINK", "https://www.lordsmobile.com/")

RALLY_TYPE_LABELS = RALLY_TYPE_LABELS_I18N
RALLY_RESULT_LABELS = RALLY_RESULT_LABELS_I18N


def rally_type_label(value: str, lang: str) -> str:
    return RALLY_TYPE_LABELS.get(value, {}).get(lang, value)


def rally_result_label(value: str, lang: str) -> str:
    return RALLY_RESULT_LABELS.get(value, {}).get(lang, value)

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
    troop=[app_commands.Choice(name=TROOP_LABELS[k]["en"], value=k) for k in TROOP_LABELS]
)
async def troop_set(interaction: discord.Interaction, troop: app_commands.Choice[str]):
    lang = get_lang(interaction.guild_id, interaction.user.id)
    data = load(TROOP_FILE)
    gid = str(interaction.guild_id)
    data.setdefault(gid, {})
    data[gid][str(interaction.user.id)] = {"troop": troop.value, "name": str(interaction.user)}
    save(TROOP_FILE, data)
    await interaction.response.send_message(
        t("troop_set_success", lang, troop=troop_label(troop.value, lang))
    )


# ---------------------------------------------------------------------------
# /rally set
# ---------------------------------------------------------------------------

@app_commands.command(
    name="rallyset",
    description="📯 افتح نداء حشد وينبّه كل أعضاء السيرفر (@everyone) | Open a rally call and ping everyone"
)
@app_commands.describe(
    troop="Troop type needed",
    target="Target alliance or player name",
    image="Optional rally screenshot",
    minutes="Minutes until rally closes (default: 5)",
    note="Optional note"
)
@app_commands.choices(
    troop=[app_commands.Choice(name=TROOP_LABELS[k]["ar"] + " / " + TROOP_LABELS[k]["en"], value=k) for k in TROOP_LABELS]
)
async def rally_set(
    interaction: discord.Interaction,
    troop: app_commands.Choice[str],
    target: str,
    image: discord.Attachment = None,
    minutes: int = 5,
    note: str = None
):
    lang = get_lang(interaction.guild_id, interaction.user.id)

    deadline = datetime.now(timezone.utc) + timedelta(minutes=max(1, minutes))
    countdown = discord.utils.format_dt(deadline, style="R")

    embed = discord.Embed(
        title=t("rally_title", lang),
        description=t(
            "rally_desc_v2",
            lang,
            leader=interaction.user.mention,
            troop=troop_label(troop.value, lang),
            countdown=countdown
        ),
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name=t("rally_target_field", lang), value=target, inline=True)
    if note:
        embed.add_field(name=t("rally_note_field", lang), value=note, inline=True)
    if image is not None and (image.content_type or "").lower().startswith("image/"):
        embed.set_image(url=image.url)
    embed.add_field(
        name=t("rally_joiners_field", lang),
        value=t("rally_no_joiners", lang),
        inline=False
    )
    embed.set_footer(text=t("rally_footer_v2", lang, leader=str(interaction.user)))

    view = RallyJoinView(embed, lang)
    app_link = get_game_link(interaction.guild_id, default=DEFAULT_APP_LINK)
    view.add_item(discord.ui.Button(label=t("rally_open_app", lang), style=discord.ButtonStyle.link, url=app_link, emoji="📲"))

    await interaction.response.send_message(
        content=f"@everyone {t('rally_everyone_ping', lang)}",
        embed=embed,
        view=view,
        allowed_mentions=discord.AllowedMentions(everyone=True)
    )


class RallyJoinView(discord.ui.View):
    """زر تسجيل ذاتي في الحشد؛ كل عضو يقدر يسجل نفسه مرة واحدة."""

    def __init__(self, embed: discord.Embed, lang: str):
        super().__init__(timeout=None)
        self.embed = embed
        self.lang = lang
        self.participant_ids: list[int] = []
        self.join_button.label = t("rally_join_button", lang)

    @discord.ui.button(label="✅ سجّل في الحشد", style=discord.ButtonStyle.success)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participant_ids:
            await interaction.response.send_message(t("rally_already_joined", self.lang))
            return

        self.participant_ids.append(interaction.user.id)
        mentions = "، ".join(f"<@{uid}>" for uid in self.participant_ids)
        for index, field in enumerate(self.embed.fields):
            if field.name == t("rally_joiners_field", self.lang):
                self.embed.set_field_at(index, name=field.name, value=mentions[:1024], inline=False)
                break
        button.label = f"✅ {t('rally_join_button_short', self.lang)} ({len(self.participant_ids)})"
        await interaction.response.edit_message(embed=self.embed, view=self)
        await interaction.followup.send(t("rally_joined_success", self.lang))


class RallyCog(commands.Cog):
    """نداء الحشود الذكي وتسجيل نوع القوات."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="rally_log",
        description="👥 (إدارة) سجّل حضور حشد: الأعضاء المشاركين ونوعه (هجوم/دفاع) ونتيجته"
    )
    @app_commands.describe(
        rally_type="Rally type",
        result="Rally result",
        note="Optional note (e.g. rally target)"
    )
    @app_commands.choices(
        rally_type=[
            app_commands.Choice(name="⚔️ Attack", value="attack"),
            app_commands.Choice(name="🛡️ Defense", value="defense"),
        ],
        result=[
            app_commands.Choice(name="🏆 Win", value="win"),
            app_commands.Choice(name="❌ Loss", value="loss"),
            app_commands.Choice(name="🤝 Draw", value="draw"),
        ]
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def rally_log(
        self,
        interaction: discord.Interaction,
        rally_type: app_commands.Choice[str],
        result: app_commands.Choice[str],
        note: Optional[str] = None
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        view = RallyLogView(rally_type.value, result.value, note, str(interaction.user), lang)
        await interaction.response.send_message(
            t("rally_log_prompt", lang),
            view=view,
            ephemeral=True
        )

    @rally_log.error
    async def rally_log_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                t("rally_log_admin_only", lang), ephemeral=True
            )
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)


class RallyLogView(discord.ui.View):
    """نافذة اختيار الأعضاء المشاركين في الحشد (حتى 25 عضو دفعة واحدة) وتأكيد التسجيل."""

    def __init__(self, rally_type: str, result: str, note: Optional[str], logged_by: str, lang: str):
        super().__init__(timeout=180)
        self.rally_type = rally_type
        self.result = result
        self.note = note
        self.logged_by = logged_by
        self.lang = lang
        self.selected_ids: list[int] = []

        self.user_select = discord.ui.UserSelect(
            placeholder=t("rally_select_placeholder", lang), min_values=1, max_values=25
        )
        self.user_select.callback = self.on_select
        self.add_item(self.user_select)
        self.confirm.label = t("rally_confirm_button", lang)

    async def on_select(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        self.selected_ids = [u.id for u in self.user_select.values]
        await interaction.response.send_message(
            t("rally_select_confirm_hint", lang, count=len(self.selected_ids))
            
        )

    @discord.ui.button(label="✅ تأكيد التسجيل", style=discord.ButtonStyle.success, row=1)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if not self.selected_ids:
            await interaction.response.send_message(t("rally_log_need_member", lang))
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

        mentions = t("rally_log_mentions_joiner", lang).join(f"<@{uid}>" for uid in self.selected_ids)
        embed = discord.Embed(title=t("rally_log_success_title", lang), color=discord.Color.green())
        embed.add_field(name=t("rally_log_type_field", lang), value=rally_type_label(self.rally_type, lang), inline=True)
        embed.add_field(name=t("rally_log_result_field", lang), value=rally_result_label(self.result, lang), inline=True)
        embed.add_field(name=t("rally_log_members_field", lang), value=mentions, inline=False)
        if self.note and self.note != "-":
            embed.add_field(name=t("rally_note_field", lang), value=self.note, inline=False)
        embed.set_footer(text=t("rally_log_footer", lang, by=self.logged_by))

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=None, embed=embed, view=self)


async def setup(bot: commands.Bot):
    await bot.add_cog(RallyCog(bot))
    bot.tree.add_command(troop_group)
    bot.tree.add_command(rally_set)
