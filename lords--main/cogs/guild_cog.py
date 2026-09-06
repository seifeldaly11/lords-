import asyncio
import random
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load, save, load_json_data
from utils.i18n import get_lang, t, ACTIVITY_TYPE_LABELS_I18N
from cogs.rally_cog import RALLY_LOG_FILE, RALLY_TYPE_LABELS, RALLY_RESULT_LABELS
from cogs.war_cog import REPORTS_FILE

ACTIVITY_FILE = "activity"
QUIZ_FILE = "quiz_scores"
GF_FILE = "guild_fest"

ACTIVITY_TYPE_KEYS = ["rally", "guild_fest", "dragon_arena", "kvk"]

RANKS = [
    (0, "rank_beginner"),
    (20, "rank_active_contributor"),
    (50, "rank_field_leader"),
    (100, "rank_lords_expert"),
]


def get_rank(points: int, lang: str = "ar") -> str:
    rank_key = RANKS[0][1]
    for threshold, key in RANKS:
        if points >= threshold:
            rank_key = key
    return t(rank_key, lang)


def compute_member_stats(gid: str, uid: int) -> dict:
    """يجمع كل سجلات المشاركة الخاصة بعضو معيّن من كل الأنظمة (نشاطات، حشود، معارك، مهرجان)."""
    rally_entries = [e for e in load(RALLY_LOG_FILE).get(gid, {}).get("entries", []) if uid in e.get("members", [])]
    activity_logs = load(ACTIVITY_FILE).get(gid, {}).get(str(uid), {"logs": []})["logs"]
    reports = [r for r in load(REPORTS_FILE).get(gid, []) if r.get("author_id") == uid]
    gf_completed = load(GF_FILE).get(gid, {}).get("completed", {}).get(str(uid), 0)
    return {
        "rally_entries": rally_entries,
        "activity_logs": activity_logs,
        "reports": reports,
        "gf_completed": gf_completed,
    }


def compute_all_members_scores(gid: str) -> dict:
    """يحسب نقاط نشاط إجمالية لكل عضو (أنشطة + حضور حشود) عشان لوحات التصدر.

    ملحوظة أمان: معارك /report متعمّد استبعادها من الحساب هنا لأنها الدخل الوحيد
    غير المتحقَّق منه (اليوزر بيسجّلها بنفسه من غير أي صلاحية Manage Server، على عكس
    /log_activity و/rally_log اللي مقفولين على الإدارة). لو اتحسبت، أي عضو كان يقدر
    يسبام /report add بنتيجة "فوز" وهمية بلا حدود ويصعد ترتيبه في /top5 صناعياً.
    /report list و/report user لسه شغالين عادي كسجل شخصي - بس مش بيأثروا على الترتيب.
    """
    scores: dict[str, dict] = {}

    for uid, info in load(ACTIVITY_FILE).get(gid, {}).items():
        bucket = scores.setdefault(uid, {"name": info.get("name", f"<@{uid}>"), "score": 0})
        bucket["score"] += len(info.get("logs", []))
        bucket["name"] = info.get("name", bucket["name"])

    for entry in load(RALLY_LOG_FILE).get(gid, {}).get("entries", []):
        for uid in entry.get("members", []):
            suid = str(uid)
            bucket = scores.setdefault(suid, {"name": f"<@{uid}>", "score": 0})
            bucket["score"] += 1

    return scores


# ---------------------------------------------------------------------------
# /log_activity
# ---------------------------------------------------------------------------

class LogActivityModal(discord.ui.Modal):
    details = discord.ui.TextInput(label="📝 التفاصيل", style=discord.TextStyle.paragraph)
    reason = discord.ui.TextInput(label="❓ السبب/الملاحظة", required=False)

    def __init__(self, activity_key: str, activity_label: str, member: discord.Member, lang: str):
        super().__init__(title=t("log_activity_modal_title", lang))
        self.activity_key = activity_key
        self.activity_label = activity_label
        self.member = member
        self.lang = lang
        self.details.label = t("log_activity_details_label", lang)
        self.reason.label = t("log_activity_reason_label", lang)

    async def on_submit(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        data = load(ACTIVITY_FILE)
        gid = str(interaction.guild_id)
        data.setdefault(gid, {})
        uid = str(self.member.id)
        data[gid].setdefault(uid, {"name": str(self.member), "logs": []})
        data[gid][uid]["logs"].append(
            {
                "type": self.activity_key,
                "label": self.activity_label,
                "details": self.details.value,
                "reason": self.reason.value or "-",
                "by": str(interaction.user),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        save(ACTIVITY_FILE, data)

        embed = discord.Embed(title=t("log_activity_success_title", lang), color=discord.Color.green())
        embed.add_field(name=t("log_activity_member_field", lang), value=self.member.mention, inline=True)
        embed.add_field(name=t("log_activity_type_field", lang), value=self.activity_label, inline=True)
        embed.add_field(name=t("log_activity_details_field", lang), value=self.details.value, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ActivityTypeSelect(discord.ui.Select):
    def __init__(self, member: discord.Member, lang: str):
        self.member = member
        self.lang = lang
        options = [
            discord.SelectOption(label=ACTIVITY_TYPE_LABELS_I18N[key][lang], value=key)
            for key in ACTIVITY_TYPE_KEYS
        ]
        super().__init__(placeholder=t("activity_select_placeholder", lang), options=options)

    async def callback(self, interaction: discord.Interaction):
        label = ACTIVITY_TYPE_LABELS_I18N[self.values[0]][self.lang]
        await interaction.response.send_modal(
            LogActivityModal(self.values[0], label, self.member, self.lang)
        )


class ActivityTypeView(discord.ui.View):
    def __init__(self, member: discord.Member, lang: str):
        super().__init__(timeout=60)
        self.add_item(ActivityTypeSelect(member, lang))


# ---------------------------------------------------------------------------
# /stats_event
# ---------------------------------------------------------------------------

class StatsEventView(discord.ui.View):
    def __init__(self, guild: discord.Guild, lang: str):
        super().__init__(timeout=90)
        self.guild = guild
        self.lang = lang
        self.top.label = t("stats_top_button", lang)
        self.active.label = t("stats_active_button", lang)
        self.inactive.label = t("stats_inactive_button", lang)

    def _get_bucket(self):
        data = load(ACTIVITY_FILE)
        return data.get(str(self.guild.id), {})

    @discord.ui.button(label="🏆 الأوائل", style=discord.ButtonStyle.success)
    async def top(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = get_lang(interaction.guild_id)
        bucket = self._get_bucket()
        ranked = sorted(bucket.items(), key=lambda kv: len(kv[1]["logs"]), reverse=True)[:10]
        if not ranked:
            await interaction.response.send_message(t("stats_no_data", lang), ephemeral=True)
            return
        desc = "\n".join(
            t("stats_top_line", lang, rank=i + 1, name=v["name"], count=len(v["logs"]))
            for i, (uid, v) in enumerate(ranked)
        )
        embed = discord.Embed(title=t("stats_top_title", lang), description=desc, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="✅ المشاركون النشطون", style=discord.ButtonStyle.primary)
    async def active(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = get_lang(interaction.guild_id)
        bucket = self._get_bucket()
        active_members = [v["name"] for v in bucket.values() if len(v["logs"]) >= 1]
        if not active_members:
            await interaction.response.send_message(t("stats_no_active", lang), ephemeral=True)
            return
        desc = "\n".join(f"• {name}" for name in active_members[:40])
        embed = discord.Embed(title=t("stats_active_title", lang), description=desc, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="😴 غير المشاركين", style=discord.ButtonStyle.danger)
    async def inactive(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = get_lang(interaction.guild_id)
        bucket = self._get_bucket()
        active_ids = set(bucket.keys())
        inactive_members = [
            m for m in self.guild.members if not m.bot and str(m.id) not in active_ids
        ]
        if not inactive_members:
            await interaction.response.send_message(t("stats_all_participated", lang), ephemeral=True)
            return
        desc = "\n".join(f"• {m.mention}" for m in inactive_members[:40])
        embed = discord.Embed(
            title=t("stats_inactive_title", lang),
            description=desc,
            color=discord.Color.dark_grey(),
        )
        if len(inactive_members) > 40:
            embed.set_footer(text=t("stats_inactive_extra_footer", lang, count=len(inactive_members) - 40))
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /gf (مهرجان التحالف)
# ---------------------------------------------------------------------------

gf_group = app_commands.Group(name="gf", description="🎉 إدارة مهام مهرجان التحالف")


class GfTaskModal(discord.ui.Modal):
    task_name = discord.ui.TextInput(label="📌 اسم المهمة", placeholder="مثال: أنفق 500 جوهرة")
    minutes_until_due = discord.ui.TextInput(label="⏱️ المهمة هتنتهي خلال كام دقيقة؟", placeholder="مثال: 60")

    def __init__(self, member: discord.Member, cog: "GuildCog", lang: str):
        super().__init__(title=t("gf_task_modal_title", lang))
        self.member = member
        self.cog = cog
        self.lang = lang
        self.task_name.label = t("gf_task_name_label", lang)
        self.task_name.placeholder = t("gf_task_name_placeholder", lang)
        self.minutes_until_due.label = t("gf_minutes_label", lang)
        self.minutes_until_due.placeholder = t("gf_minutes_placeholder", lang)

    async def on_submit(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        try:
            minutes = float(self.minutes_until_due.value)
            if minutes <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(t("gf_invalid_minutes", lang), ephemeral=True)
            return

        data = load(GF_FILE)
        gid = str(interaction.guild_id)
        data.setdefault(gid, {"tasks": [], "completed": {}})
        task_id = f"{self.member.id}-{datetime.utcnow().timestamp()}"
        data[gid]["tasks"].append(
            {
                "id": task_id,
                "member_id": self.member.id,
                "member_name": str(self.member),
                "task": self.task_name.value,
                "due_in_minutes": minutes,
                "created": datetime.utcnow().isoformat(),
                "done": False,
            }
        )
        save(GF_FILE, data)

        await interaction.response.send_message(
            t("gf_task_added", lang, task=self.task_name.value, member=self.member.mention, minutes=minutes),
            ephemeral=True,
        )

        channel = interaction.channel
        remind_30 = max(0, minutes - 30) * 60
        remind_10 = max(0, minutes - 10) * 60
        if remind_30 > 0:
            asyncio.create_task(self.cog.gf_reminder(remind_30, channel, self.member, self.task_name.value, 30))
        if remind_10 > 0 and minutes > 10:
            asyncio.create_task(self.cog.gf_reminder(remind_10, channel, self.member, self.task_name.value, 10))


@gf_group.command(name="task", description="🎉 [إدارة] أضف مهمة مهرجان تحالف لعضو مع تذكير قبل الانتهاء")
@app_commands.checks.has_permissions(manage_guild=True)
async def gf_task(interaction: discord.Interaction, member: discord.Member):
    lang = get_lang(interaction.guild_id)
    cog = interaction.client.get_cog("GuildCog")
    await interaction.response.send_modal(GfTaskModal(member, cog, lang))


@gf_task.error
async def gf_task_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    lang = get_lang(interaction.guild_id)
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(t("gf_leadership_only", lang), ephemeral=True)
    else:
        await interaction.response.send_message(t("err_unexpected", lang), ephemeral=True)


@gf_group.command(name="done", description="✅ [إدارة] علّم مهمة مهرجان تحالف كمكتملة")
@app_commands.checks.has_permissions(manage_guild=True)
async def gf_done(interaction: discord.Interaction, member: discord.Member):
    lang = get_lang(interaction.guild_id)
    data = load(GF_FILE)
    gid = str(interaction.guild_id)
    tasks = data.get(gid, {}).get("tasks", [])
    pending = [task for task in tasks if task["member_id"] == member.id and not task["done"]]
    if not pending:
        await interaction.response.send_message(t("gf_no_pending_task", lang), ephemeral=True)
        return
    pending[-1]["done"] = True
    data.setdefault(gid, {}).setdefault("completed", {})
    uid = str(member.id)
    data[gid]["completed"][uid] = data[gid]["completed"].get(uid, 0) + 1
    save(GF_FILE, data)
    await interaction.response.send_message(t("gf_task_done", lang, member=member.mention), ephemeral=True)


@gf_done.error
async def gf_done_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    lang = get_lang(interaction.guild_id)
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(t("gf_leadership_only", lang), ephemeral=True)
    else:
        await interaction.response.send_message(t("err_unexpected", lang), ephemeral=True)


@gf_group.command(name="board", description="🏅 لوحة صدارة مهرجان التحالف")
async def gf_board(interaction: discord.Interaction):
    lang = get_lang(interaction.guild_id)
    data = load(GF_FILE)
    completed = data.get(str(interaction.guild_id), {}).get("completed", {})
    if not completed:
        await interaction.response.send_message(t("gf_no_completed_tasks", lang), ephemeral=True)
        return
    ranked = sorted(completed.items(), key=lambda kv: kv[1], reverse=True)[:10]
    desc = "\n".join(
        t("gf_board_line", lang, rank=i + 1, uid=uid, count=count) for i, (uid, count) in enumerate(ranked)
    )
    embed = discord.Embed(title=t("gf_board_title", lang), description=desc, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# /quiz
# ---------------------------------------------------------------------------

class QuizView(discord.ui.View):
    def __init__(self, question: dict, cog: "GuildCog", lang: str):
        super().__init__(timeout=30)
        self.question = question
        self.cog = cog
        self.lang = lang
        self.answered_users = set()
        for i, opt in enumerate(question["options"]):
            self.add_item(self.QuizButton(opt, i, question["answer"], self))

    class QuizButton(discord.ui.Button):
        def __init__(self, label, index, correct_index, parent_view):
            super().__init__(label=label, style=discord.ButtonStyle.secondary)
            self.index = index
            self.correct_index = correct_index
            self.parent_view = parent_view

        async def callback(self, interaction: discord.Interaction):
            lang = get_lang(interaction.guild_id)
            if interaction.user.id in self.parent_view.answered_users:
                await interaction.response.send_message(t("quiz_already_answered", lang), ephemeral=True)
                return
            self.parent_view.answered_users.add(interaction.user.id)

            correct = self.index == self.correct_index
            data = load(QUIZ_FILE)
            gid = str(interaction.guild_id)
            uid = str(interaction.user.id)
            data.setdefault(gid, {})
            data[gid].setdefault(uid, {"name": str(interaction.user), "points": 0})
            if correct:
                data[gid][uid]["points"] += 1
            save(QUIZ_FILE, data)

            points = data[gid][uid]["points"]
            rank = get_rank(points, lang)
            msg = t("quiz_correct", lang) if correct else t("quiz_wrong", lang)
            await interaction.response.send_message(
                t("quiz_result_footer", lang, msg=msg, points=points, rank=rank), ephemeral=True
            )


# ---------------------------------------------------------------------------
# /user_admin_check
# ---------------------------------------------------------------------------

def build_admin_dashboard_embed(member: discord.Member, stats: dict, lang: str) -> discord.Embed:
    activity_logs = stats["activity_logs"]
    rally_entries = stats["rally_entries"]
    reports = stats["reports"]
    gf_completed = stats["gf_completed"]

    counts = {"rally": 0, "guild_fest": 0, "dragon_arena": 0, "kvk": 0}
    for l in activity_logs:
        if l.get("type") in counts:
            counts[l["type"]] += 1

    embed = discord.Embed(
        title=t("admin_dashboard_title", lang, name=member.display_name),
        color=discord.Color.dark_teal(),
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(
        name=t("admin_dashboard_events_field", lang),
        value=t(
            "admin_dashboard_events_value",
            lang,
            rally=counts["rally"],
            guild_fest=counts["guild_fest"],
            gf_completed=gf_completed,
            dragon_arena=counts["dragon_arena"],
            kvk=counts["kvk"],
        ),
        inline=True,
    )
    embed.add_field(
        name=t("admin_dashboard_rally_field", lang),
        value=t(
            "admin_dashboard_rally_value",
            lang,
            total=len(rally_entries),
            wins=sum(1 for e in rally_entries if e.get("result") == "win"),
        ),
        inline=True,
    )
    embed.add_field(name=t("admin_dashboard_reports_field", lang), value=str(len(reports)), inline=True)

    if activity_logs:
        recent = sorted(activity_logs, key=lambda l: l.get("timestamp", ""), reverse=True)[:5]
        lines = [f"• {l.get('label', l.get('type'))} — {l.get('timestamp', '')[:10]}" for l in recent]
        embed.add_field(name=t("admin_dashboard_recent_activities_field", lang), value="\n".join(lines), inline=False)

    if rally_entries:
        recent_r = sorted(rally_entries, key=lambda e: e.get("timestamp", ""), reverse=True)[:5]
        lines = [
            f"• {RALLY_TYPE_LABELS.get(e.get('rally_type'), '?')} - "
            f"{RALLY_RESULT_LABELS.get(e.get('result'), '?')} — {e.get('timestamp', '')[:10]}"
            for e in recent_r
        ]
        embed.add_field(name=t("admin_dashboard_recent_rallies_field", lang), value="\n".join(lines), inline=False)

    if not activity_logs and not rally_entries and not reports:
        embed.description = t("admin_dashboard_no_data", lang)

    return embed


class AdminCheckView(discord.ui.View):
    def __init__(self, lang: str):
        super().__init__(timeout=120)
        self.lang = lang
        self.select = discord.ui.UserSelect(
            placeholder=t("admin_check_select_placeholder", lang), min_values=1, max_values=1
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        member = self.select.values[0]
        gid = str(interaction.guild_id)
        stats = compute_member_stats(gid, member.id)
        embed = build_admin_dashboard_embed(member, stats, lang)
        await interaction.response.edit_message(content=None, embed=embed, view=self)


# ---------------------------------------------------------------------------
# الـ Cog الرئيسي
# ---------------------------------------------------------------------------

class GuildCog(commands.Cog):
    """إدارة التحالف والتتبع والتفاعل."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.quiz_questions = load_json_data("quiz.json")

    @app_commands.command(name="log_activity", description="📋 [إدارة] سجّل مشاركة عضو في نشاط (حشود، مهرجان، ساحة تنين، KvK)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def log_activity(self, interaction: discord.Interaction, member: discord.Member):
        lang = get_lang(interaction.guild_id)
        await interaction.response.send_message(
            t("log_activity_prompt", lang, member=member.mention),
            view=ActivityTypeView(member, lang),
            ephemeral=True,
        )

    @log_activity.error
    async def log_activity_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                t("log_activity_admin_only", lang),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(t("err_unexpected", lang), ephemeral=True)

    @app_commands.command(name="stats_event", description="📊 عرض تفاعلي لإحصائيات مشاركة الأعضاء")
    async def stats_event(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        await interaction.response.send_message(
            t("stats_event_prompt", lang), view=StatsEventView(interaction.guild, lang), ephemeral=True
        )

    @app_commands.command(
        name="information",
        description="🪪 استعلام ملف عضو: إحصائيات شاملة (مشاركات الحشود، التزام الحروب، والفعاليات)",
    )
    @app_commands.describe(member="العضو المطلوب استعلام ملفه (افتراضياً نفسك)")
    async def information(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        lang = get_lang(interaction.guild_id)
        target = member or interaction.user
        gid = str(interaction.guild_id)
        uid = target.id
        stats = compute_member_stats(gid, uid)

        rally_entries = stats["rally_entries"]
        rally_total = len(rally_entries)
        rally_attack = sum(1 for e in rally_entries if e.get("rally_type") == "attack")
        rally_defense = sum(1 for e in rally_entries if e.get("rally_type") == "defense")
        rally_wins = sum(1 for e in rally_entries if e.get("result") == "win")

        activity_logs = stats["activity_logs"]
        kvk_count = sum(1 for l in activity_logs if l.get("type") == "kvk")
        reports_count = len(stats["reports"])
        fest_count = sum(1 for l in activity_logs if l.get("type") == "guild_fest")
        dragon_count = sum(1 for l in activity_logs if l.get("type") == "dragon_arena")
        gf_completed = stats["gf_completed"]

        total_points = len(activity_logs)
        rank = get_rank(total_points, lang)

        embed = discord.Embed(
            title=t("info_profile_title", lang, name=target.display_name),
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(
            name=t("info_rally_field", lang),
            value=t(
                "info_rally_value",
                lang,
                total=rally_total,
                attack_label=RALLY_TYPE_LABELS["attack"],
                attack=rally_attack,
                defense_label=RALLY_TYPE_LABELS["defense"],
                defense=rally_defense,
                win_label=RALLY_RESULT_LABELS["win"],
                wins=rally_wins,
            ),
            inline=True,
        )
        embed.add_field(
            name=t("info_war_field", lang),
            value=t("info_war_value", lang, kvk=kvk_count, reports=reports_count),
            inline=True,
        )
        embed.add_field(
            name=t("info_events_field", lang),
            value=t("info_events_value", lang, fest=fest_count, gf_completed=gf_completed, dragon=dragon_count),
            inline=True,
        )
        embed.add_field(
            name=t("info_rank_field", lang),
            value=t("info_rank_value", lang, rank=rank, points=total_points),
            inline=False,
        )
        embed.set_footer(text=t("info_footer", lang, user=interaction.user.display_name))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="user_admin_check",
        description="🛡️ (إدارة) لوحة متابعة شاملة: اختر عضو من قائمة واستعرض سجل مشاركته في كل الأحداث",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def user_admin_check(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        await interaction.response.send_message(
            t("admin_check_prompt", lang), view=AdminCheckView(lang), ephemeral=True
        )

    @user_admin_check.error
    async def user_admin_check_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                t("admin_check_permission_denied", lang), ephemeral=True
            )
        else:
            await interaction.response.send_message(t("err_unexpected", lang), ephemeral=True)

    @app_commands.command(name="top5", description="🏆 أنشط 5 أعضاء في كل الفعاليات والحشود مجتمعة")
    async def top5(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        gid = str(interaction.guild_id)
        scores = compute_all_members_scores(gid)
        if not scores:
            await interaction.response.send_message(t("top5_no_data", lang), ephemeral=True)
            return

        ranked = sorted(scores.items(), key=lambda kv: kv[1]["score"], reverse=True)[:5]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        lines = [
            t("top5_line", lang, medal=medals[i], name=info["name"], score=info["score"])
            for i, (uid, info) in enumerate(ranked)
        ]

        embed = discord.Embed(
            title=t("top5_title", lang),
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(text=t("top5_footer", lang))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="event_stats", description="📊 تقرير شامل عن نسبة مشاركة أعضاء التحالف في فعالية معينة")
    @app_commands.describe(event_type="الفعالية المطلوب عمل تقرير عنها")
    @app_commands.choices(
        event_type=[
            app_commands.Choice(name="👥 حشود (Rally)", value="rally"),
            app_commands.Choice(name="🎉 مهرجان التحالف", value="guild_fest"),
            app_commands.Choice(name="🐉 ساحة التنين", value="dragon_arena"),
            app_commands.Choice(name="⚔️ KvK", value="kvk"),
            app_commands.Choice(name="📊 الكل مجتمعين", value="all"),
        ]
    )
    async def event_stats(self, interaction: discord.Interaction, event_type: app_commands.Choice[str]):
        lang = get_lang(interaction.guild_id)
        gid = str(interaction.guild_id)
        activity_data = load(ACTIVITY_FILE).get(gid, {})
        total_members = [m for m in interaction.guild.members if not m.bot]
        total_count = len(total_members)

        if event_type.value == "rally":
            rally_entries = load(RALLY_LOG_FILE).get(gid, {}).get("entries", [])
            participant_ids = {uid for e in rally_entries for uid in e.get("members", [])}
        elif event_type.value == "all":
            participant_ids = {int(uid) for uid in activity_data.keys()}
            rally_entries = load(RALLY_LOG_FILE).get(gid, {}).get("entries", [])
            participant_ids |= {uid for e in rally_entries for uid in e.get("members", [])}
        else:
            participant_ids = {
                int(uid)
                for uid, info in activity_data.items()
                if any(l.get("type") == event_type.value for l in info.get("logs", []))
            }

        participants = [m for m in total_members if m.id in participant_ids]
        non_participants = [m for m in total_members if m.id not in participant_ids]
        percentage = (len(participants) / total_count * 100) if total_count else 0.0

        embed = discord.Embed(
            title=t("event_stats_title", lang, name=event_type.name),
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(
            name=t("event_stats_participated_field", lang),
            value=t("event_stats_participated_value", lang, count=len(participants), total=total_count),
            inline=True,
        )
        embed.add_field(
            name=t("event_stats_percentage_field", lang), value=f"{percentage:.1f}%", inline=True
        )
        if non_participants:
            preview = "، ".join(m.mention for m in non_participants[:15])
            if len(non_participants) > 15:
                preview += t("event_stats_extra_suffix", lang, count=len(non_participants) - 15)
            embed.add_field(
                name=t("event_stats_non_participants_field", lang, count=len(non_participants)),
                value=preview,
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    async def gf_reminder(self, delay, channel, member, task_name, minutes_left):
        await asyncio.sleep(delay)
        lang = get_lang(channel.guild.id) if channel and getattr(channel, "guild", None) else "ar"
        text = t("gf_reminder_text", lang, task=task_name, member=member.mention, minutes=minutes_left)
        try:
            if channel:
                await channel.send(text)
        except discord.HTTPException:
            pass
        try:
            await member.send(text)
        except discord.Forbidden:
            pass

    @app_commands.command(name="quiz", description="🧠 سؤال مسابقة سريع عن لوردس موبايل - اجمع نقاط وارفع رتبتك!")
    async def quiz(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        question = random.choice(self.quiz_questions)
        view = QuizView(question, self, lang)
        embed = discord.Embed(
            title=t("quiz_embed_title", lang),
            description=question["question"],
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=t("quiz_embed_footer", lang))
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="reset_stats", description="🔄 [إدارة فقط] تصفير سجلات النشاط والمسابقة لبدء أسبوع جديد")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_stats(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        await interaction.response.send_message(
            t("reset_confirm_prompt", lang),
            view=ResetConfirmView(lang),
            ephemeral=True,
        )

    @reset_stats.error
    async def reset_stats_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("reset_admin_only_full", lang), ephemeral=True)
        else:
            await interaction.response.send_message(t("err_unexpected", lang), ephemeral=True)


class ResetConfirmView(discord.ui.View):
    def __init__(self, lang: str):
        super().__init__(timeout=30)
        self.lang = lang
        self.confirm.label = t("reset_confirm_yes_button", lang)
        self.cancel.label = t("reset_confirm_cancel_button", lang)

    @discord.ui.button(label="نعم، صفّر كل شيء", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = get_lang(interaction.guild_id)
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(t("reset_confirm_admin_only", lang), ephemeral=True)
            return
        gid = str(interaction.guild_id)
        for fname in (ACTIVITY_FILE, QUIZ_FILE, GF_FILE):
            data = load(fname)
            if gid in data:
                del data[gid]
                save(fname, data)
        await interaction.response.edit_message(content=t("reset_confirm_success", lang), view=None)

    @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = get_lang(interaction.guild_id)
        await interaction.response.edit_message(content=t("reset_confirm_cancelled", lang), view=None)


async def setup(bot: commands.Bot):
    bot.tree.add_command(gf_group)
    await bot.add_cog(GuildCog(bot))
