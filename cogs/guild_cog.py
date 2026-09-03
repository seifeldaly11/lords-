import asyncio
import random
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load, save, load_json_data
from cogs.rally_cog import RALLY_LOG_FILE, RALLY_TYPE_LABELS, RALLY_RESULT_LABELS
from cogs.war_cog import REPORTS_FILE

ACTIVITY_FILE = "activity"
QUIZ_FILE = "quiz_scores"
GF_FILE = "guild_fest"

ACTIVITY_TYPES = [
    ("👥 حشود (Rally)", "rally"),
    ("🎉 مهرجان التحالف", "guild_fest"),
    ("🐉 ساحة التنين", "dragon_arena"),
    ("⚔️ KvK", "kvk"),
]

RANKS = [
    (0, "🥉 مبتدئ"),
    (20, "🥈 مساهم نشط"),
    (50, "🥇 قائد ميداني"),
    (100, "🧠 خبير لوردس"),
]


def get_rank(points: int) -> str:
    rank = RANKS[0][1]
    for threshold, label in RANKS:
        if points >= threshold:
            rank = label
    return rank


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

class LogActivityModal(discord.ui.Modal, title="📋 تسجيل مشاركة"):
    details = discord.ui.TextInput(label="📝 التفاصيل", style=discord.TextStyle.paragraph)
    reason = discord.ui.TextInput(label="❓ السبب/الملاحظة", required=False)

    def __init__(self, activity_key: str, activity_label: str, member: discord.Member):
        super().__init__()
        self.activity_key = activity_key
        self.activity_label = activity_label
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
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

        embed = discord.Embed(title="✅ تم تسجيل المشاركة", color=discord.Color.green())
        embed.add_field(name="👤 العضو", value=self.member.mention, inline=True)
        embed.add_field(name="🏷️ النشاط", value=self.activity_label, inline=True)
        embed.add_field(name="📝 التفاصيل", value=self.details.value, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ActivityTypeSelect(discord.ui.Select):
    def __init__(self, member: discord.Member):
        self.member = member
        options = [discord.SelectOption(label=label, value=key) for label, key in ACTIVITY_TYPES]
        super().__init__(placeholder="اختر نوع النشاط...", options=options)

    async def callback(self, interaction: discord.Interaction):
        label = next(lbl for lbl, key in ACTIVITY_TYPES if key == self.values[0])
        await interaction.response.send_modal(LogActivityModal(self.values[0], label, self.member))


class ActivityTypeView(discord.ui.View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=60)
        self.add_item(ActivityTypeSelect(member))


# ---------------------------------------------------------------------------
# /stats_event
# ---------------------------------------------------------------------------

class StatsEventView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=90)
        self.guild = guild

    def _get_bucket(self):
        data = load(ACTIVITY_FILE)
        return data.get(str(self.guild.id), {})

    @discord.ui.button(label="🏆 الأوائل", style=discord.ButtonStyle.success)
    async def top(self, interaction: discord.Interaction, button: discord.ui.Button):
        bucket = self._get_bucket()
        ranked = sorted(bucket.items(), key=lambda kv: len(kv[1]["logs"]), reverse=True)[:10]
        if not ranked:
            await interaction.response.send_message("لا توجد بيانات مسجلة بعد.", ephemeral=True)
            return
        desc = "\n".join(
            f"{i+1}. **{v['name']}** — {len(v['logs'])} مشاركة 🏅" for i, (uid, v) in enumerate(ranked)
        )
        embed = discord.Embed(title="🏆 الأوائل - تكريم أفضل المساهمين", description=desc, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="✅ المشاركون النشطون", style=discord.ButtonStyle.primary)
    async def active(self, interaction: discord.Interaction, button: discord.ui.Button):
        bucket = self._get_bucket()
        active_members = [v["name"] for v in bucket.values() if len(v["logs"]) >= 1]
        if not active_members:
            await interaction.response.send_message("لا يوجد أعضاء نشطون مسجلين بعد.", ephemeral=True)
            return
        desc = "\n".join(f"• {name}" for name in active_members[:40])
        embed = discord.Embed(title="✅ الأعضاء النشطون", description=desc, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="😴 غير المشاركين", style=discord.ButtonStyle.danger)
    async def inactive(self, interaction: discord.Interaction, button: discord.ui.Button):
        bucket = self._get_bucket()
        active_ids = set(bucket.keys())
        inactive_members = [
            m for m in self.guild.members if not m.bot and str(m.id) not in active_ids
        ]
        if not inactive_members:
            await interaction.response.send_message("🎉 كل الأعضاء شاركوا بحاجة على الأقل!", ephemeral=True)
            return
        desc = "\n".join(f"• {m.mention}" for m in inactive_members[:40])
        embed = discord.Embed(
            title="😴 غير المشاركين / المتقاعسون",
            description=desc,
            color=discord.Color.dark_grey(),
        )
        if len(inactive_members) > 40:
            embed.set_footer(text=f"+ {len(inactive_members) - 40} عضو إضافي غير معروض")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /gf (مهرجان التحالف)
# ---------------------------------------------------------------------------

gf_group = app_commands.Group(name="gf", description="🎉 إدارة مهام مهرجان التحالف")


class GfTaskModal(discord.ui.Modal, title="🎉 مهمة مهرجان التحالف"):
    task_name = discord.ui.TextInput(label="📌 اسم المهمة", placeholder="مثال: أنفق 500 جوهرة")
    minutes_until_due = discord.ui.TextInput(label="⏱️ المهمة هتنتهي خلال كام دقيقة؟", placeholder="مثال: 60")

    def __init__(self, member: discord.Member, cog: "GuildCog"):
        super().__init__()
        self.member = member
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = float(self.minutes_until_due.value)
            if minutes <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ أدخل عدد دقائق صحيح وأكبر من صفر.", ephemeral=True)
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
            f"✅ تم تسجيل مهمة **{self.task_name.value}** للعضو {self.member.mention}، "
            f"هينتهي وقتها خلال {minutes:.0f} دقيقة. هيوصله تنبيه قبل 30 و10 دقايق ⏰",
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
    cog = interaction.client.get_cog("GuildCog")
    await interaction.response.send_modal(GfTaskModal(member, cog))


@gf_task.error
async def gf_task_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ الأمر ده مخصص لقيادة التحالف فقط.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ حصل خطأ غير متوقع.", ephemeral=True)


@gf_group.command(name="done", description="✅ [إدارة] علّم مهمة مهرجان تحالف كمكتملة")
@app_commands.checks.has_permissions(manage_guild=True)
async def gf_done(interaction: discord.Interaction, member: discord.Member):
    data = load(GF_FILE)
    gid = str(interaction.guild_id)
    tasks = data.get(gid, {}).get("tasks", [])
    pending = [t for t in tasks if t["member_id"] == member.id and not t["done"]]
    if not pending:
        await interaction.response.send_message("لا توجد مهام معلّقة لهذا العضو.", ephemeral=True)
        return
    pending[-1]["done"] = True
    data.setdefault(gid, {}).setdefault("completed", {})
    uid = str(member.id)
    data[gid]["completed"][uid] = data[gid]["completed"].get(uid, 0) + 1
    save(GF_FILE, data)
    await interaction.response.send_message(f"✅ تم تسجيل إكمال مهمة {member.mention}!", ephemeral=True)


@gf_done.error
async def gf_done_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ الأمر ده مخصص لقيادة التحالف فقط.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ حصل خطأ غير متوقع.", ephemeral=True)


@gf_group.command(name="board", description="🏅 لوحة صدارة مهرجان التحالف")
async def gf_board(interaction: discord.Interaction):
    data = load(GF_FILE)
    completed = data.get(str(interaction.guild_id), {}).get("completed", {})
    if not completed:
        await interaction.response.send_message("لا توجد مهام مكتملة مسجلة بعد.", ephemeral=True)
        return
    ranked = sorted(completed.items(), key=lambda kv: kv[1], reverse=True)[:10]
    desc = "\n".join(f"{i+1}. <@{uid}> — {count} مهمة مكتملة ✅" for i, (uid, count) in enumerate(ranked))
    embed = discord.Embed(title="🏅 لوحة صدارة مهرجان التحالف", description=desc, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# /quiz
# ---------------------------------------------------------------------------

class QuizView(discord.ui.View):
    def __init__(self, question: dict, cog: "GuildCog"):
        super().__init__(timeout=30)
        self.question = question
        self.cog = cog
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
            if interaction.user.id in self.parent_view.answered_users:
                await interaction.response.send_message("إنت جاوبت على السؤال ده بالفعل!", ephemeral=True)
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
            rank = get_rank(points)
            msg = "✅ إجابة صحيحة!" if correct else "❌ إجابة غلط."
            await interaction.response.send_message(
                f"{msg} رصيدك دلوقتي: **{points}** نقطة | رتبتك: {rank}", ephemeral=True
            )


# ---------------------------------------------------------------------------
# /user_admin_check
# ---------------------------------------------------------------------------

def build_admin_dashboard_embed(member: discord.Member, stats: dict) -> discord.Embed:
    activity_logs = stats["activity_logs"]
    rally_entries = stats["rally_entries"]
    reports = stats["reports"]
    gf_completed = stats["gf_completed"]

    counts = {"rally": 0, "guild_fest": 0, "dragon_arena": 0, "kvk": 0}
    for l in activity_logs:
        if l.get("type") in counts:
            counts[l["type"]] += 1

    embed = discord.Embed(
        title=f"🛡️ لوحة المتابعة الإدارية: {member.display_name}",
        color=discord.Color.dark_teal(),
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(
        name="📋 سجل الأحداث (/log_activity)",
        value=(
            f"👥 حشود: {counts['rally']}\n"
            f"🎉 مهرجان التحالف: {counts['guild_fest']} ({gf_completed} مهمة مكتملة)\n"
            f"🐉 ساحة التنين: {counts['dragon_arena']}\n"
            f"⚔️ KvK: {counts['kvk']}"
        ),
        inline=True,
    )
    embed.add_field(
        name="📯 حضور الحشود (/rally_log)",
        value=(
            f"الإجمالي: {len(rally_entries)}\n"
            f"🏆 فوز: {sum(1 for e in rally_entries if e.get('result') == 'win')}"
        ),
        inline=True,
    )
    embed.add_field(name="⚔️ معارك مسجّلة (/report)", value=str(len(reports)), inline=True)

    if activity_logs:
        recent = sorted(activity_logs, key=lambda l: l.get("timestamp", ""), reverse=True)[:5]
        lines = [f"• {l.get('label', l.get('type'))} — {l.get('timestamp', '')[:10]}" for l in recent]
        embed.add_field(name="🕒 آخر 5 أنشطة", value="\n".join(lines), inline=False)

    if rally_entries:
        recent_r = sorted(rally_entries, key=lambda e: e.get("timestamp", ""), reverse=True)[:5]
        lines = [
            f"• {RALLY_TYPE_LABELS.get(e.get('rally_type'), '?')} - "
            f"{RALLY_RESULT_LABELS.get(e.get('result'), '?')} — {e.get('timestamp', '')[:10]}"
            for e in recent_r
        ]
        embed.add_field(name="🕒 آخر 5 حشود", value="\n".join(lines), inline=False)

    if not activity_logs and not rally_entries and not reports:
        embed.description = "⚠️ مفيش أي سجل مشاركة لهذا العضو لسه."

    return embed


class AdminCheckView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.select = discord.ui.UserSelect(
            placeholder="اختر العضو اللي عايز تراجع سجله...", min_values=1, max_values=1
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        member = self.select.values[0]
        gid = str(interaction.guild_id)
        stats = compute_member_stats(gid, member.id)
        embed = build_admin_dashboard_embed(member, stats)
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
        await interaction.response.send_message(
            f"سجّل نشاط للعضو {member.mention} - اختر النوع:", view=ActivityTypeView(member), ephemeral=True
        )

    @log_activity.error
    async def log_activity_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ الأمر ده مخصص لقيادة التحالف فقط (يحتاج صلاحية Manage Server) عشان محدش يسجّل بيانات غلط على غيره.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message("❌ حصل خطأ غير متوقع.", ephemeral=True)

    @app_commands.command(name="stats_event", description="📊 عرض تفاعلي لإحصائيات مشاركة الأعضاء")
    async def stats_event(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "اختر التقرير اللي عايز تشوفه:", view=StatsEventView(interaction.guild), ephemeral=True
        )

    @app_commands.command(
        name="information",
        description="🪪 استعلام ملف عضو: إحصائيات شاملة (مشاركات الحشود، التزام الحروب، والفعاليات)",
    )
    @app_commands.describe(member="العضو المطلوب استعلام ملفه (افتراضياً نفسك)")
    async def information(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
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
        rank = get_rank(total_points)

        embed = discord.Embed(
            title=f"🪪 ملف العضو: {target.display_name}",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(
            name="👥 مشاركات الحشود",
            value=(
                f"الإجمالي: **{rally_total}**\n"
                f"{RALLY_TYPE_LABELS['attack']}: {rally_attack} | {RALLY_TYPE_LABELS['defense']}: {rally_defense}\n"
                f"{RALLY_RESULT_LABELS['win']}: {rally_wins}"
            ),
            inline=True,
        )
        embed.add_field(
            name="⚔️ التزام الحروب",
            value=f"مشاركات KvK: **{kvk_count}**\nمعارك مسجّلة: **{reports_count}**",
            inline=True,
        )
        embed.add_field(
            name="🎉 الفعاليات",
            value=f"مهرجان التحالف: {fest_count} نشاط ({gf_completed} مهمة مكتملة)\nساحة التنين: {dragon_count}",
            inline=True,
        )
        embed.add_field(name="🏅 الرتبة العامة", value=f"{rank} — {total_points} نقطة مشاركة إجمالية", inline=False)
        embed.set_footer(text=f"طلب بواسطة {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="user_admin_check",
        description="🛡️ (إدارة) لوحة متابعة شاملة: اختر عضو من قائمة واستعرض سجل مشاركته في كل الأحداث",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def user_admin_check(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "اختر العضو اللي عايز تراجع سجله من القائمة تحت:", view=AdminCheckView(), ephemeral=True
        )

    @user_admin_check.error
    async def user_admin_check_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ الأمر ده مخصص للإدارة فقط (صلاحية Manage Server).", ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ حصل خطأ غير متوقع.", ephemeral=True)

    @app_commands.command(name="top5", description="🏆 أنشط 5 أعضاء في كل الفعاليات والحشود مجتمعة")
    async def top5(self, interaction: discord.Interaction):
        gid = str(interaction.guild_id)
        scores = compute_all_members_scores(gid)
        if not scores:
            await interaction.response.send_message("لا توجد بيانات مشاركة مسجلة بعد.", ephemeral=True)
            return

        ranked = sorted(scores.items(), key=lambda kv: kv[1]["score"], reverse=True)[:5]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        lines = [f"{medals[i]} **{info['name']}** — {info['score']} مشاركة إجمالية" for i, (uid, info) in enumerate(ranked)]

        embed = discord.Embed(
            title="🏆 أنشط 5 أعضاء - كل الفعاليات والحشود",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="الاحتساب: أنشطة /log_activity + حضور /rally_log + معارك /report")
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
            title=f"📊 إحصائية مشاركة التحالف: {event_type.name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="✅ شاركوا", value=f"{len(participants)}/{total_count} عضو", inline=True)
        embed.add_field(name="📈 نسبة المشاركة", value=f"{percentage:.1f}%", inline=True)
        if non_participants:
            preview = "، ".join(m.mention for m in non_participants[:15])
            if len(non_participants) > 15:
                preview += f" (+{len(non_participants) - 15} إضافي)"
            embed.add_field(name=f"😴 لم يشاركوا ({len(non_participants)})", value=preview, inline=False)
        await interaction.response.send_message(embed=embed)

    async def gf_reminder(self, delay, channel, member, task_name, minutes_left):
        await asyncio.sleep(delay)
        text = f"⏰ تنبيه: مهمة **{task_name}** الخاصة بـ {member.mention} هتنتهي خلال {minutes_left} دقيقة! 🎉"
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
        question = random.choice(self.quiz_questions)
        view = QuizView(question, self)
        embed = discord.Embed(title="🧠 سؤال مسابقة لوردس موبايل", description=question["question"], color=discord.Color.blurple())
        embed.set_footer(text="عندك 30 ثانية للإجابة!")
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="reset_stats", description="🔄 [إدارة فقط] تصفير سجلات النشاط والمسابقة لبدء أسبوع جديد")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_stats(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "⚠️ متأكد إنك عايز تصفّر كل سجلات النشاط والمسابقة لهذا السيرفر؟ الإجراء ده لا يمكن التراجع عنه.",
            view=ResetConfirmView(),
            ephemeral=True,
        )

    @reset_stats.error
    async def reset_stats_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ الأمر ده للإدارة فقط (Administrator).", ephemeral=True)
        else:
            await interaction.response.send_message("❌ حصل خطأ غير متوقع.", ephemeral=True)


class ResetConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="نعم، صفّر كل شيء", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ الأمر ده للإدارة فقط.", ephemeral=True)
            return
        gid = str(interaction.guild_id)
        for fname in (ACTIVITY_FILE, QUIZ_FILE, GF_FILE):
            data = load(fname)
            if gid in data:
                del data[gid]
                save(fname, data)
        await interaction.response.edit_message(content="✅ تم تصفير كل السجلات لهذا السيرفر.", view=None)

    @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="تم الإلغاء.", view=None)


async def setup(bot: commands.Bot):
    bot.tree.add_command(gf_group)
    await bot.add_cog(GuildCog(bot))
