"""
نظام متتبع الصيد اليومي (Hunt Tracker):

- /hunt_log      — تسجيل صيد بثلاث طرق: يدوي (عضو + رقم)، أو صورة لجدول/تقرير الصيد
                    (بيتحلل تلقائياً عن طريق نفس موديل الرؤية المستخدم في /ai)، أو قائمة
                    نصية مجمّعة (اسم + رقم في كل سطر) بتتفلتر وتتوزّع على الأعضاء تلقائياً.
- /hunt_channel  — (إدارة) تحديد قناة إرسال تقارير/قوائم الصيد + التارجت اليومي المطلوب.
- /hunt_list     — عرض شامل: كل عضو صيد كام وباقيله كام للوصول للتارجت اليومي.

ملاحظة: تحليل الصورة بيستخدم نفس بنية تحاليل /ai (Cohere Vision)، فلازم يكون
COHERE_API_KEY مضبوط في .env عشان وضع الصورة يشتغل - وضعي التسجيل اليدوي والقائمة
المجمّعة شغالين بدون أي مفتاح خارجي.
"""
import difflib
import json
import re
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load, save
from utils.ui import progress_bar, GOLD
from utils.i18n import get_lang, t

HUNT_FILE = "hunt_log"
DEFAULT_DAILY_TARGET = 100

LINE_RE = re.compile(r"^(?P<n>.+?)[\s:،,\-–—]+(?P<count>\d+)\s*$")


def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_bucket(data: dict, guild_id: int) -> dict:
    gid = str(guild_id)
    data.setdefault(gid, {"channel_id": None, "daily_target": DEFAULT_DAILY_TARGET, "members": {}})
    return data[gid]


def match_member(guild: discord.Guild, raw_name: str) -> Optional[discord.Member]:
    """يدوّر على أقرب عضو في السيرفر لاسم مكتوب (يدعم اسم الشهرة أو اليوزرنيم، حتى لو مش مطابق 100%)."""
    raw_name = raw_name.strip().lstrip("@").strip()
    if not raw_name:
        return None

    name_map: dict[str, discord.Member] = {}
    for m in guild.members:
        if m.bot:
            continue
        for candidate in (str(m), m.name, m.display_name):
            name_map[candidate.lower()] = m

    exact = name_map.get(raw_name.lower())
    if exact:
        return exact

    close = difflib.get_close_matches(raw_name.lower(), list(name_map.keys()), n=1, cutoff=0.72)
    if close:
        return name_map[close[0]]
    return None


def parse_bulk_list(text: str) -> list[tuple[str, int]]:
    """يحلل قائمة نصية مجمّعة (كل سطر: اسم + رقم) ويرجع قائمة (اسم، عدد)."""
    results = []
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("•-–—*").strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if m:
            try:
                results.append((m.group("name").strip(), int(m.group("count"))))
            except ValueError:
                continue
    return results


async def extract_from_image(image_url: str, lang: str, guild_id: int | None = None) -> list[tuple[str, int]]:
    """يستخدم موديل الرؤية (نفس بنية /ai) عشان يقرأ جدول/تقرير صيد من صورة ويرجعه كقائمة (اسم، عدد)."""
    # استيراد كسول يمنع تسجيل أمر /gf optimize مرتين أثناء تحميل الـ cogs:
    # hunt_cog يحتاج الدالة فقط وقت تنفيذ تحليل الصورة.
    from cogs.ai_cog import ask_ai

    prompt = (
        "دي صورة لجدول أو تقرير صيد وحوش داخل تحالف في لعبة Lords Mobile. "
        "استخرج منها قائمة بكل اسم لاعب وعدد الوحوش (أو النقاط) اللي صادها، حتى لو الأرقام مش واضحة تماماً حاول تقدّرها. "
        "رجّعلي **JSON فقط** بدون أي نص تاني ولا Markdown، بالشكل ده بالظبط: "
        '[{"name": "اسم اللاعب", "hunted": 123}, ...]'
    )
    raw = await ask_ai(prompt, image_url=image_url, lang=lang, guild_id=guild_id)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned
    try:
        parsed = json.loads(cleaned)
        return [(str(item["name"]), int(item["hunted"])) for item in parsed if "name" in item and "hunted" in item]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return []


class HuntCog(commands.Cog):
    """نظام متتبع الصيد اليومي للتحالف."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -- تطبيق نتائج (يدوي = إضافة، قائمة/صورة = استبدال بالرقم الإجمالي المرسل) -----

    def _apply_manual(self, guild_id: int, member: discord.Member, amount: int) -> tuple[int, int]:
        data = load(HUNT_FILE)
        bucket = get_bucket(data, guild_id)
        uid = str(member.id)
        record = bucket["members"].setdefault(uid, {"name": str(member), "date": "", "hunted": 0})
        today = today_str()
        if record.get("date") != today:
            record["date"] = today
            record["hunted"] = 0
        record["hunted"] += amount
        record["name"] = str(member)
        save(HUNT_FILE, data)
        return record["hunted"], bucket["daily_target"]

    def _apply_bulk(self, guild: discord.Guild, entries: list[tuple[str, int]]):
        data = load(HUNT_FILE)
        bucket = get_bucket(data, guild.id)
        today = today_str()
        matched, unmatched = [], []
        for raw_name, count in entries:
            member = match_member(guild, raw_name)
            if not member:
                unmatched.append((raw_name, count))
                continue
            uid = str(member.id)
            record = bucket["members"].setdefault(uid, {"name": str(member), "date": "", "hunted": 0})
            record["date"] = today
            record["hunted"] = count  # قائمة مجمّعة = رقم إجمالي (مش إضافة) لأنها تمثل تقرير كامل
            record["name"] = str(member)
            matched.append((member, count))
        save(HUNT_FILE, data)
        return matched, unmatched, bucket["daily_target"], bucket.get("channel_id")

    async def _mirror_to_hunt_channel(self, interaction: discord.Interaction, channel_id: Optional[int], embed: discord.Embed):
        if not channel_id or channel_id == interaction.channel_id:
            return
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    # -- /hunt_log ------------------------------------------------------

    @app_commands.command(
        name="hunt_log",
        description="🐾 سجّل صيد: يدوي لعضو، أو صورة جدول/تقرير صيد، أو قائمة مجمّعة (اسم + رقم بكل سطر)"
    )
    @app_commands.describe(
        member="Member to log for (defaults to yourself)",
        hunted="Number of monsters hunted",
        image="Hunt table or report image for automatic analysis",
        bulk_list="Bulk list: one member and count per line"
    )
    async def hunt_log(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None,
        hunted: Optional[int] = None,
        image: Optional[discord.Attachment] = None,
        bulk_list: Optional[str] = None
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        modes_used = sum(x is not None for x in (hunted, image, bulk_list))
        if modes_used == 0:
            await interaction.response.send_message(t("hunt_need_one_mode", lang))
            return
        if modes_used > 1:
            await interaction.response.send_message(t("hunt_only_one_mode", lang))
            return

        data = load(HUNT_FILE)
        bucket = get_bucket(data, interaction.guild_id)
        channel_id = bucket.get("channel_id")

        # -- الوضع اليدوي --------------------------------------------------
        if hunted is not None:
            if hunted <= 0:
                await interaction.response.send_message(t("hunt_manual_invalid_amount", lang), ephemeral=False)
                return
            target_member = member or interaction.user
            total_today, daily_target = self._apply_manual(interaction.guild_id, target_member, hunted)
            remaining = max(0, daily_target - total_today)
            status = (
                t("hunt_manual_status_done", lang)
                if total_today >= daily_target
                else t("hunt_manual_status_remaining", lang, remaining=remaining)
            )
            embed = discord.Embed(
                title=t("hunt_manual_log_title", lang),
                description=t(
                    "hunt_manual_log_desc", lang,
                    member=target_member.mention, hunted=hunted, total=total_today,
                    target=daily_target, status=status
                ),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
            await self._mirror_to_hunt_channel(interaction, channel_id, embed)
            return

        # -- وضع القائمة المجمّعة -------------------------------------------
        if bulk_list is not None:
            entries = parse_bulk_list(bulk_list)
            if not entries:
                await interaction.response.send_message(t("hunt_bulk_parse_failed", lang))
                return
            await interaction.response.defer(thinking=True)
            matched, unmatched, daily_target, _ = self._apply_bulk(interaction.guild, entries)
            embed = self._build_bulk_report_embed(matched, unmatched, daily_target, lang)
            await interaction.followup.send(embed=embed)
            await self._mirror_to_hunt_channel(interaction, channel_id, embed)
            return

        # -- وضع الصورة ------------------------------------------------------
        if image is not None:
            if not (image.content_type or "").startswith("image/"):
                await interaction.response.send_message(t("hunt_image_not_image", lang))
                return
            await interaction.response.defer(thinking=True)
            entries = await extract_from_image(image.url, lang=lang, guild_id=interaction.guild_id)
            if not entries:
                await interaction.followup.send(t("hunt_image_extract_failed", lang))
                return
            matched, unmatched, daily_target, _ = self._apply_bulk(interaction.guild, entries)
            embed = self._build_bulk_report_embed(matched, unmatched, daily_target, lang, from_image=True)
            await interaction.followup.send(embed=embed)
            await self._mirror_to_hunt_channel(interaction, channel_id, embed)
            return

    def _build_bulk_report_embed(
        self,
        matched: list[tuple[discord.Member, int]],
        unmatched: list[tuple[str, int]],
        daily_target: int,
        lang: str,
        from_image: bool = False
    ) -> discord.Embed:
        suffix = t("hunt_report_title_image_suffix", lang) if from_image else t("hunt_report_title_bulk_suffix", lang)
        embed = discord.Embed(
            title=t("hunt_report_title", lang) + suffix,
            color=discord.Color.green() if matched else discord.Color.orange()
        )
        if matched:
            lines = []
            for m, count in sorted(matched, key=lambda x: x[1], reverse=True)[:30]:
                emoji = "✅" if count >= daily_target else "🕗"
                lines.append(f"{emoji} **{m.display_name}** — {count}/{daily_target}")
            embed.add_field(
                name=t("hunt_report_matched_field", lang, count=len(matched)), value="\n".join(lines), inline=False
            )
        if unmatched:
            lines = [f"❓ {name} ({count})" for name, count in unmatched[:15]]
            embed.add_field(
                name=t("hunt_report_unmatched_field", lang, count=len(unmatched)),
                value="\n".join(lines) + "\n" + t("hunt_report_unmatched_hint", lang),
                inline=False
            )
        embed.set_footer(text=t("hunt_report_footer", lang, target=daily_target))
        return embed

    # -- /hunt_channel (إدارة) -------------------------------------------

    @app_commands.command(
        name="hunt_channel",
        description="📍 (إدارة) حدد قناة إرسال تقارير وقوائم الصيد، وحدّث التارجت اليومي لو حبيت"
    )
    @app_commands.describe(
        channel="Channel for hunt reports and summaries",
        daily_target="Optional daily target per member"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def hunt_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        daily_target: Optional[int] = None
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if daily_target is not None and daily_target <= 0:
            await interaction.response.send_message(t("hunt_channel_invalid_target", lang), ephemeral=False)
            return
        data = load(HUNT_FILE)
        bucket = get_bucket(data, interaction.guild_id)
        bucket["channel_id"] = channel.id
        if daily_target is not None:
            bucket["daily_target"] = daily_target
        save(HUNT_FILE, data)

        msg = t("hunt_channel_success", lang, channel=channel.mention)
        if daily_target is not None:
            msg += t("hunt_channel_target_set", lang, target=daily_target)
        await interaction.response.send_message(msg, ephemeral=False)

    @hunt_channel.error
    async def hunt_channel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("hunt_channel_admin_only", lang), ephemeral=False)
        else:
            await interaction.response.send_message(t("hunt_channel_error", lang), ephemeral=False)

    # -- /hunt_list -------------------------------------------------------

    @app_commands.command(name="hunt_list", description="📊 عرض شامل: كل عضو صاد كام وباقيله كام على التارجت اليومي")
    async def hunt_list(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        data = load(HUNT_FILE)
        bucket = data.get(str(interaction.guild_id), {})
        daily_target = bucket.get("daily_target", DEFAULT_DAILY_TARGET)
        members_data = bucket.get("members", {})
        today = today_str()

        if not members_data:
            await interaction.response.send_message(t("hunt_list_empty", lang))
            return

        done_lines, pending_lines = [], []
        for uid, record in members_data.items():
            hunted = record.get("hunted", 0) if record.get("date") == today else 0
            name = record.get("name", f"<@{uid}>")
            bar = progress_bar(hunted, daily_target, length=8)
            if hunted >= daily_target:
                done_lines.append((hunted, t("hunt_done_line", lang, name=name, bar=bar, hunted=hunted, target=daily_target)))
            else:
                remaining = daily_target - hunted
                pending_lines.append((
                    remaining,
                    t("hunt_pending_line", lang, name=name, bar=bar, hunted=hunted, target=daily_target, remaining=remaining)
                ))

        done_lines.sort(key=lambda x: x[0], reverse=True)
        pending_lines.sort(key=lambda x: x[0])  # الأقرب للتارجت الأول

        embed = discord.Embed(
            title=t("hunt_list_title", lang),
            color=GOLD,
            timestamp=datetime.now(timezone.utc)
        )
        if pending_lines:
            embed.add_field(
                name=t("hunt_list_pending_field", lang, count=len(pending_lines)),
                value="\n".join(l for _, l in pending_lines[:20]) or "-",
                inline=False
            )
        if done_lines:
            embed.add_field(
                name=t("hunt_list_done_field", lang, count=len(done_lines)),
                value="\n".join(l for _, l in done_lines[:20]) or "-",
                inline=False
            )
        embed.set_footer(text=t("hunt_list_footer", lang, target=daily_target, count=len(members_data)))
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(HuntCog(bot))
