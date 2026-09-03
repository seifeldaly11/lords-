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
HUNT_FILE = "hunt_log"
DEFAULT_DAILY_TARGET = 100

LINE_RE = re.compile(r"^(?P<name>.+?)[\s:،,\-–—]+(?P<count>\d+)\s*$")


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


async def extract_from_image(image_url: str, lang: str) -> list[tuple[str, int]]:
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
    raw = await ask_ai(prompt, image_url=image_url, lang=lang)
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
        description="🐾 سجّل صيد: يدوي لعضو، أو صورة جدول/تقرير صيد، أو قائمة مجمّعة (اسم + رقم بكل سطر)",
    )
    @app_commands.describe(
        member="سجّل الصيد لهذا العضو (وضع يدوي - لو مسيبتهوش هيتسجل لحسابك انت)",
        hunted="عدد الوحوش المصيدة (وضع يدوي - بيتضاف على رصيد اليوم)",
        image="صورة لجدول/تقرير صيد عشان تتحلل تلقائياً (محتاج COHERE_API_KEY)",
        bulk_list="قائمة مجمّعة: سطر لكل عضو بصيغة 'الاسم رقم' - هتستبدل رصيد اليوم بالرقم المكتوب",
    )
    async def hunt_log(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None,
        hunted: Optional[int] = None,
        image: Optional[discord.Attachment] = None,
        bulk_list: Optional[str] = None,
    ):
        modes_used = sum(x is not None for x in (hunted, image, bulk_list))
        if modes_used == 0:
            await interaction.response.send_message(
                "❌ لازم تستخدم طريقة واحدة على الأقل: `hunted` (يدوي)، أو `image` (صورة)، أو `bulk_list` (قائمة مجمّعة).",
                ephemeral=True,
            )
            return
        if modes_used > 1:
            await interaction.response.send_message(
                "❌ استخدم طريقة واحدة بس في المرة الواحدة (يدوي/صورة/قائمة) عشان منلخبطش الأرقام.",
                ephemeral=True,
            )
            return

        data = load(HUNT_FILE)
        bucket = get_bucket(data, interaction.guild_id)
        channel_id = bucket.get("channel_id")

        # -- الوضع اليدوي --------------------------------------------------
        if hunted is not None:
            if hunted <= 0:
                await interaction.response.send_message("❌ العدد لازم يكون أكبر من صفر.", ephemeral=True)
                return
            target_member = member or interaction.user
            total_today, daily_target = self._apply_manual(interaction.guild_id, target_member, hunted)
            remaining = max(0, daily_target - total_today)
            status = "✅ خلّص التارجت اليومي! 🎉" if total_today >= daily_target else f"باقيله **{remaining}** للتارجت."
            embed = discord.Embed(
                title="🐾 تم تسجيل الصيد",
                description=f"{target_member.mention} صاد **{hunted}** دلوقتي.\n📊 إجمالي اليوم: **{total_today}/{daily_target}**\n{status}",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed)
            await self._mirror_to_hunt_channel(interaction, channel_id, embed)
            return

        # -- وضع القائمة المجمّعة -------------------------------------------
        if bulk_list is not None:
            entries = parse_bulk_list(bulk_list)
            if not entries:
                await interaction.response.send_message(
                    "❌ مقدرتش أفهم أي سطر من القائمة. الصيغة المتوقعة: `الاسم رقم` في كل سطر (مثال: `Ahmed 250`).",
                    ephemeral=True,
                )
                return
            await interaction.response.defer(thinking=True)
            matched, unmatched, daily_target, _ = self._apply_bulk(interaction.guild, entries)
            embed = self._build_bulk_report_embed(matched, unmatched, daily_target)
            await interaction.followup.send(embed=embed)
            await self._mirror_to_hunt_channel(interaction, channel_id, embed)
            return

        # -- وضع الصورة ------------------------------------------------------
        if image is not None:
            if not (image.content_type or "").startswith("image/"):
                await interaction.response.send_message("❌ المرفق ده مش صورة.", ephemeral=True)
                return
            await interaction.response.defer(thinking=True)
            entries = await extract_from_image(image.url, lang="ar")
            if not entries:
                await interaction.followup.send(
                    "❌ مقدرتش أقرأ الجدول من الصورة (أو COHERE_API_KEY مش مضبوط). "
                    "جرّب صورة أوضح، أو استخدم `bulk_list`/`hunted` بدل كده.",
                )
                return
            matched, unmatched, daily_target, _ = self._apply_bulk(interaction.guild, entries)
            embed = self._build_bulk_report_embed(matched, unmatched, daily_target, from_image=True)
            await interaction.followup.send(embed=embed)
            await self._mirror_to_hunt_channel(interaction, channel_id, embed)
            return

    def _build_bulk_report_embed(
        self,
        matched: list[tuple[discord.Member, int]],
        unmatched: list[tuple[str, int]],
        daily_target: int,
        from_image: bool = False,
    ) -> discord.Embed:
        embed = discord.Embed(
            title="🐾 تقرير صيد" + (" (من صورة)" if from_image else " (قائمة مجمّعة)"),
            color=discord.Color.green() if matched else discord.Color.orange(),
        )
        if matched:
            lines = []
            for m, count in sorted(matched, key=lambda x: x[1], reverse=True)[:30]:
                emoji = "✅" if count >= daily_target else "🕗"
                lines.append(f"{emoji} **{m.display_name}** — {count}/{daily_target}")
            embed.add_field(name=f"📋 تم تسجيل {len(matched)} عضو", value="\n".join(lines), inline=False)
        if unmatched:
            lines = [f"❓ {name} ({count})" for name, count in unmatched[:15]]
            embed.add_field(
                name=f"⚠️ {len(unmatched)} اسم مش متعرف عليه",
                value="\n".join(lines) + "\n(اتأكد إن الاسم مطابق لليوزرنيم/اسم الشهرة في الديسكورد)",
                inline=False,
            )
        embed.set_footer(text=f"🎯 التارجت اليومي الحالي: {daily_target}")
        return embed

    # -- /hunt_channel (إدارة) -------------------------------------------

    @app_commands.command(
        name="hunt_channel",
        description="📍 (إدارة) حدد قناة إرسال تقارير وقوائم الصيد، وحدّث التارجت اليومي لو حبيت",
    )
    @app_commands.describe(
        channel="القناة اللي هتتوجّه لها تقارير وملخصات الصيد",
        daily_target="(اختياري) التارجت اليومي المطلوب من كل عضو",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def hunt_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        daily_target: Optional[int] = None,
    ):
        if daily_target is not None and daily_target <= 0:
            await interaction.response.send_message("❌ التارجت اليومي لازم يكون رقم أكبر من صفر.", ephemeral=True)
            return
        data = load(HUNT_FILE)
        bucket = get_bucket(data, interaction.guild_id)
        bucket["channel_id"] = channel.id
        if daily_target is not None:
            bucket["daily_target"] = daily_target
        save(HUNT_FILE, data)

        msg = f"✅ تم تحديد {channel.mention} كقناة تقارير وقوائم الصيد."
        if daily_target is not None:
            msg += f"\n🎯 التارجت اليومي اتضبط على **{daily_target}**."
        await interaction.response.send_message(msg, ephemeral=True)

    @hunt_channel.error
    async def hunt_channel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ الأمر ده مخصص للإدارة فقط (صلاحية Manage Server).", ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ حصل خطأ غير متوقع.", ephemeral=True)

    # -- /hunt_list -------------------------------------------------------

    @app_commands.command(name="hunt_list", description="📊 عرض شامل: كل عضو صاد كام وباقيله كام على التارجت اليومي")
    async def hunt_list(self, interaction: discord.Interaction):
        data = load(HUNT_FILE)
        bucket = data.get(str(interaction.guild_id), {})
        daily_target = bucket.get("daily_target", DEFAULT_DAILY_TARGET)
        members_data = bucket.get("members", {})
        today = today_str()

        if not members_data:
            await interaction.response.send_message(
                "مفيش بيانات صيد مسجلة لسه. استخدم `/hunt_log` عشان تبدأ التسجيل.", ephemeral=True
            )
            return

        done_lines, pending_lines = [], []
        for uid, record in members_data.items():
            hunted = record.get("hunted", 0) if record.get("date") == today else 0
            name = record.get("name", f"<@{uid}>")
            bar = progress_bar(hunted, daily_target, length=8)
            if hunted >= daily_target:
                done_lines.append((hunted, f"✅ **{name}** — {bar} ({hunted}/{daily_target})"))
            else:
                remaining = daily_target - hunted
                pending_lines.append((remaining, f"🕗 **{name}** — {bar} ({hunted}/{daily_target}, باقي {remaining})"))

        done_lines.sort(key=lambda x: x[0], reverse=True)
        pending_lines.sort(key=lambda x: x[0])  # الأقرب للتارجت الأول

        embed = discord.Embed(
            title="📊 القائمة الشاملة للصيد اليومي",
            color=GOLD,
            timestamp=datetime.now(timezone.utc),
        )
        if pending_lines:
            embed.add_field(
                name=f"🕗 لسه ماوصلوش ({len(pending_lines)})",
                value="\n".join(l for _, l in pending_lines[:20]) or "-",
                inline=False,
            )
        if done_lines:
            embed.add_field(
                name=f"✅ خلّصوا التارجت ({len(done_lines)})",
                value="\n".join(l for _, l in done_lines[:20]) or "-",
                inline=False,
            )
        embed.set_footer(text=f"🎯 التارجت اليومي: {daily_target} | إجمالي الأعضاء المتابَعين: {len(members_data)}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(HuntCog(bot))
