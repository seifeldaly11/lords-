"""
منبه الدرع الذكي: /shield أو /voice_rescue (نفس الوظيفة بالظبط - اسم بديل).

- بتحدد مدة الدرع (دقائق/ساعات/أيام) وتنبيه تلقائي قبل الانتهاء بـ15 دقيقة (رسالة + DM).
- لو محدش رد (لا بزرار "✅ استلمت" ولا بأمر /shelter_done) لحد ما الدرع يخلص فعلياً:
  البوت يدخل الروم الصوتية اللي صاحب الدرع فيها (أو روم احتياطية لو محددة) ويشغّل نغمة
  إنذار مستمرة + Soundboard (لو متاح على السيرفر) + يعمل Mention متكرر في التشانيل،
  لحد ما يكتب /shelter_done أو يدوس زرار "✅ استلمت" فيفصل فوراً.
- في إمكانية تفعيل تكرار تلقائي للمنبه كل عدد ساعات محدد.

ملاحظة: النغمة بتتولّد برمجياً (Sine wave خام) من غير أي ملفات صوت خارجية ومن غير الحاجة
لتثبيت ffmpeg، فالاعتماد الوحيد الإضافي هو مكتبة PyNaCl (لازمة لأي اتصال صوتي في discord.py).
"""
import array
import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import get_game_link, get_leadership_role_id
from utils.ui import styled_embed, progress_bar, CRIMSON, GOLD, EMERALD
from utils.i18n import get_lang, t

log = logging.getLogger("lordsbot.shield")

UNIT_SECONDS = {"minutes": 60, "hours": 3600, "days": 86400}
# مفاتيح i18n لكل وحدة، بيستعيروا نفس مفاتيح fmt_unit_* المستخدمة في events_cog.py
UNIT_LABEL_KEYS = {"minutes": "fmt_unit_minute", "hours": "fmt_unit_hour", "days": "fmt_unit_day"}
PRE_ALERT_SECONDS = 15 * 60          # تنبيه قبل الانتهاء بـ15 دقيقة
ESCALATION_PING_EVERY = 25           # كل قد إيه (بالثواني) يعيد المنشن وقت التصعيد الصوتي
MAX_ESCALATION_SECONDS = 30 * 60     # أقصى وقت يفضل البوت واقف في الروم يرن من غير رد


def fmt_seconds(total_seconds: float, lang: str) -> str:
    """يحوّل عدد الثواني لصيغة أيام/ساعات/دقايق مقروءة حسب اللغة."""
    total_seconds = max(0, int(total_seconds))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} {t('fmt_unit_day', lang)}")
    if hours:
        parts.append(f"{hours} {t('fmt_unit_hour', lang)}")
    if minutes or not parts:
        parts.append(f"{minutes} {t('fmt_unit_minute', lang)}")
    return t("fmt_joiner", lang).join(parts)


# ---------------------------------------------------------------------------
# مصدر صوت "إنذار" بسيط بيتولّد برمجياً (نغمتين متبادلتين) - بدون ملفات/ffmpeg
# ---------------------------------------------------------------------------

class SirenAudioSource(discord.AudioSource):
    """نغمة إنذار مستمرة لحد ما حد يستدعي stop_ringing()."""

    SAMPLE_RATE = 48000
    FRAME_MS = 20
    SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_MS // 1000  # 960

    def __init__(self, low_freq: int = 600, high_freq: int = 950, switch_every: float = 0.4, volume: float = 0.4):
        self.low_freq = low_freq
        self.high_freq = high_freq
        self.switch_every = switch_every
        self.volume = max(0.0, min(1.0, volume))
        self._sample_index = 0
        self._elapsed = 0.0
        self._stopped = False

    def stop_ringing(self) -> None:
        self._stopped = True

    def read(self) -> bytes:
        if self._stopped:
            return b""
        n = self.SAMPLES_PER_FRAME
        cycle_pos = int(self._elapsed / self.switch_every) % 2
        freq = self.low_freq if cycle_pos == 0 else self.high_freq
        buf = array.array("h")
        for i in range(n):
            t_ = (self._sample_index + i) / self.SAMPLE_RATE
            value = int(self.volume * 32767 * math.sin(2 * math.pi * freq * t_))
            buf.append(value)  # قناة شمال
            buf.append(value)  # قناة يمين
        self._sample_index += n
        self._elapsed += self.FRAME_MS / 1000
        return buf.tobytes()

    def is_opus(self) -> bool:
        return False

    def cleanup(self) -> None:
        self._stopped = True


# ---------------------------------------------------------------------------
# حالة تايمر درع واحد
# ---------------------------------------------------------------------------

class ShieldTimer:
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        channel: discord.abc.Messageable,
        user: discord.abc.User,
        duration_seconds: float,
        lang: str,
        repeat_interval_seconds: Optional[float] = None,
        fallback_voice_channel: Optional[discord.VoiceChannel] = None,
        leadership_role: Optional[discord.Role] = None,
    ):
        self.guild_id = guild_id
        self.user_id = user_id
        self.channel = channel
        self.user = user
        self.duration_seconds = duration_seconds
        self.lang = lang  # لغة السيرفر وقت إنشاء المنبه - تُستخدم في كل الرسائل اللاحقة (Task في الخلفية)
        self.repeat_interval_seconds = repeat_interval_seconds
        self.fallback_voice_channel = fallback_voice_channel
        self.leadership_role = leadership_role  # رتبة R4/R5 تتمنشن لو محدش رد وقت التصعيد

        self.end_time: Optional[datetime] = None
        self.ack_event = asyncio.Event()
        self.cancelled = False
        self.task: Optional[asyncio.Task] = None
        self.audio_source: Optional[SirenAudioSource] = None


def timer_key(guild_id: int, user_id: int) -> str:
    return f"{guild_id}:{user_id}"


# ---------------------------------------------------------------------------
# زرار "✅ استلمت" على رسالة التنبيه (بديل لأمر /shelter_done)
# ---------------------------------------------------------------------------

class ShieldAckView(discord.ui.View):
    def __init__(self, cog: "ShieldCog", key: str, owner_id: int, lang: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.key = key
        self.owner_id = owner_id
        self.lang = lang
        self.ack.label = t("shield_ack_button", lang)
        self.renew.label = t("shield_renew_button", lang)

    @discord.ui.button(label="✅ استلمت / Done", style=discord.ButtonStyle.success)
    async def ack(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self.lang
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(t("shield_ack_owner_only", lang), ephemeral=True)
            return
        timer = self.cog.active.get(self.key)
        if not timer:
            await interaction.response.send_message(t("shield_no_active_alarm", lang), ephemeral=True)
            return
        timer.ack_event.set()
        await interaction.response.send_message(t("shield_ack_stopped", lang), ephemeral=True)
        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="🛡️ تجديد الدرع", style=discord.ButtonStyle.primary)
    async def renew(self, interaction: discord.Interaction, button: discord.ui.Button):
        """زر لمسة واحدة يعيد تشغيل منبه بنفس مدة الدرع الأصلية من غير ما تكتب /shield تاني."""
        lang = self.lang
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(t("shield_ack_owner_only", lang), ephemeral=True)
            return
        timer = self.cog.active.get(self.key)
        if not timer:
            await interaction.response.send_message(t("shield_no_active_to_renew", lang), ephemeral=True)
            return
        timer.ack_event.set()
        await self.cog.renew_timer(interaction, timer)


# ---------------------------------------------------------------------------
# الـ Cog الرئيسي
# ---------------------------------------------------------------------------

class ShieldCog(commands.Cog):
    """منبه الدرع الذكي مع تصعيد صوتي (Voice Rescue)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active: dict[str, ShieldTimer] = {}

    # -- الأمر الأساسي و/voice_rescue بنفس المنطق تماماً ------------------

    async def _handle_start(
        self,
        interaction: discord.Interaction,
        amount: int,
        unit: app_commands.Choice[str],
        repeat_every_hours: Optional[int],
        voice_channel: Optional[discord.VoiceChannel],
        leadership_role: Optional[discord.Role] = None,
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)

        if amount <= 0:
            await interaction.response.send_message(t("shield_duration_invalid", lang), ephemeral=True)
            return
        if repeat_every_hours is not None and repeat_every_hours <= 0:
            await interaction.response.send_message(t("shield_repeat_invalid", lang), ephemeral=True)
            return

        key = timer_key(interaction.guild_id, interaction.user.id)
        if key in self.active:
            await interaction.response.send_message(t("shield_already_active", lang), ephemeral=True)
            return

        # لو محدش حدد رتبة قيادة يدوياً، استخدم الرتبة الافتراضية اللي اتضبطت بـ /setup (لو موجودة)
        if leadership_role is None:
            default_role_id = get_leadership_role_id(interaction.guild_id)
            if default_role_id and interaction.guild:
                leadership_role = interaction.guild.get_role(default_role_id)

        duration_seconds = amount * UNIT_SECONDS[unit.value]
        repeat_seconds = repeat_every_hours * 3600 if repeat_every_hours else None

        timer = ShieldTimer(
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
            channel=interaction.channel,
            user=interaction.user,
            duration_seconds=duration_seconds,
            lang=lang,
            repeat_interval_seconds=repeat_seconds,
            fallback_voice_channel=voice_channel,
            leadership_role=leadership_role,
        )
        self.active[key] = timer
        timer.task = asyncio.create_task(self._run_cycle(timer))

        await interaction.response.send_message(
            embed=self._build_start_embed(amount, unit, duration_seconds, repeat_every_hours, leadership_role, lang),
            view=self._build_link_view(interaction.guild_id, lang),
            ephemeral=True,
        )

    def _build_link_view(self, guild_id: int, lang: str) -> discord.ui.View:
        link = get_game_link(guild_id)
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=t("shield_open_game_button", lang), url=link, style=discord.ButtonStyle.link))
        return view

    def _build_start_embed(
        self,
        amount: int,
        unit: app_commands.Choice[str],
        duration_seconds: float,
        repeat_every_hours: Optional[int],
        leadership_role: Optional[discord.Role],
        lang: str,
    ) -> discord.Embed:
        end_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        unit_label = t(UNIT_LABEL_KEYS[unit.value], lang)
        embed = styled_embed(
            title=t("shield_started_title", lang),
            description=t("shield_duration_desc", lang, amount=amount, unit=unit_label),
            color=GOLD,
        )
        embed.add_field(name=t("shield_end_time_field", lang), value=f"`{end_time.strftime('%H:%M UTC')}`", inline=True)
        embed.add_field(name=t("shield_first_alert_field", lang), value=t("shield_first_alert_value", lang), inline=True)
        escalation_note = t("shield_escalation_value", lang)
        if leadership_role:
            escalation_note += t("shield_escalation_role_note", lang, role=leadership_role.mention)
        embed.add_field(name=t("shield_escalation_field", lang), value=escalation_note, inline=False)
        if repeat_every_hours:
            embed.add_field(
                name=t("shield_repeat_field", lang),
                value=t("shield_repeat_value", lang, hours=repeat_every_hours),
                inline=False,
            )
        return embed

    async def renew_timer(self, interaction: discord.Interaction, old_timer: "ShieldTimer") -> None:
        """يعيد إنشاء منبه جديد بنفس مدة/إعدادات القديم (زرار 🛡️ تجديد الدرع)."""
        lang = old_timer.lang
        key = timer_key(old_timer.guild_id, old_timer.user_id)
        self.active.pop(key, None)

        new_timer = ShieldTimer(
            guild_id=old_timer.guild_id,
            user_id=old_timer.user_id,
            channel=old_timer.channel,
            user=old_timer.user,
            duration_seconds=old_timer.duration_seconds,
            lang=lang,
            repeat_interval_seconds=old_timer.repeat_interval_seconds,
            fallback_voice_channel=old_timer.fallback_voice_channel,
            leadership_role=old_timer.leadership_role,
        )
        self.active[key] = new_timer
        new_timer.task = asyncio.create_task(self._run_cycle(new_timer))

        embed = styled_embed(
            title=t("shield_renewed_title", lang),
            description=t("shield_renewed_desc", lang, duration=fmt_seconds(old_timer.duration_seconds, lang)),
            color=EMERALD,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="shield",
        description="🛡️ منبه الدرع الذكي: تنبيه قبل 15 دقيقة، ولو محدش رد يدخل الروم الصوتية وينبّه بصوت إنذار",
    )
    @app_commands.describe(
        amount="Duration amount",
        unit="Duration unit",
        repeat_every_hours="Optional repeat interval in hours",
        voice_channel="Optional fallback voice channel",
        leadership_role="Optional leadership role to ping if unanswered",
    )
    @app_commands.choices(
        unit=[
            app_commands.Choice(name="⏱️ Minutes", value="minutes"),
            app_commands.Choice(name="🕐 Hours", value="hours"),
            app_commands.Choice(name="📅 Days", value="days"),
        ]
    )
    async def shield(
        self,
        interaction: discord.Interaction,
        amount: int,
        unit: app_commands.Choice[str],
        repeat_every_hours: Optional[int] = None,
        voice_channel: Optional[discord.VoiceChannel] = None,
        leadership_role: Optional[discord.Role] = None,
    ):
        await self._handle_start(interaction, amount, unit, repeat_every_hours, voice_channel, leadership_role)

    @app_commands.command(
        name="voice_rescue",
        description="🔊 نفس أمر /shield بالظبط - منبه درع مع تصعيد صوتي لو محدش رد",
    )
    @app_commands.describe(
        amount="Duration amount",
        unit="Duration unit",
        repeat_every_hours="Optional repeat interval in hours",
        voice_channel="Optional fallback voice channel",
        leadership_role="Optional leadership role to ping if unanswered",
    )
    @app_commands.choices(
        unit=[
            app_commands.Choice(name="⏱️ دقائق", value="minutes"),
            app_commands.Choice(name="🕐 ساعات", value="hours"),
            app_commands.Choice(name="📅 أيام", value="days"),
        ]
    )
    async def voice_rescue(
        self,
        interaction: discord.Interaction,
        amount: int,
        unit: app_commands.Choice[str],
        repeat_every_hours: Optional[int] = None,
        voice_channel: Optional[discord.VoiceChannel] = None,
        leadership_role: Optional[discord.Role] = None,
    ):
        await self._handle_start(interaction, amount, unit, repeat_every_hours, voice_channel, leadership_role)

    # -- إيقاف المنبه --------------------------------------------------

    @app_commands.command(
        name="shelter_done",
        description="✅ أوقف منبه الدرع الحالي (وأخرج البوت من الروم الصوتية لو داخل يرن)",
    )
    @app_commands.describe(stop_repeat="Also cancel any scheduled repeat? (default: No)")
    async def shelter_done(self, interaction: discord.Interaction, stop_repeat: bool = False):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        key = timer_key(interaction.guild_id, interaction.user.id)
        timer = self.active.get(key)
        if not timer:
            await interaction.response.send_message(t("shield_done_no_active", lang), ephemeral=True)
            return
        timer.ack_event.set()
        if stop_repeat:
            timer.cancelled = True
        await interaction.response.send_message(
            t("shield_done_stopped_and_repeat", lang) if stop_repeat else t("shield_done_stopped_plain", lang),
            ephemeral=True,
        )

    # -- دورة التشغيل (بتتكرر لو فيه repeat_interval_seconds) -----------

    async def _run_cycle(self, timer: ShieldTimer):
        key = timer_key(timer.guild_id, timer.user_id)
        lang = timer.lang
        try:
            while True:
                timer.ack_event.clear()
                timer.end_time = datetime.now(timezone.utc) + timedelta(seconds=timer.duration_seconds)
                await self._run_single(timer)

                if timer.cancelled or not timer.repeat_interval_seconds:
                    break

                try:
                    await timer.channel.send(
                        t(
                            "shield_repeat_auto_notice", lang,
                            user=timer.user.mention,
                            time=fmt_seconds(timer.repeat_interval_seconds, lang),
                        )
                    )
                except discord.HTTPException:
                    pass

                try:
                    await asyncio.wait_for(timer.ack_event.wait(), timeout=timer.repeat_interval_seconds)
                except asyncio.TimeoutError:
                    pass
                if timer.cancelled:
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("خطأ غير متوقع في دورة منبه الدرع")
        finally:
            self.active.pop(key, None)

    async def _run_single(self, timer: ShieldTimer):
        now = datetime.now(timezone.utc)
        pre_alert_wait = max(0.0, (timer.end_time - now).total_seconds() - PRE_ALERT_SECONDS)
        try:
            await asyncio.wait_for(timer.ack_event.wait(), timeout=pre_alert_wait)
            return  # اتلغى/اتأكد قبل حتى ما نوصل لمرحلة التنبيه
        except asyncio.TimeoutError:
            pass
        if timer.cancelled:
            return

        await self._send_pre_alert(timer)

        remaining = max(0.0, (timer.end_time - datetime.now(timezone.utc)).total_seconds())
        try:
            await asyncio.wait_for(timer.ack_event.wait(), timeout=remaining)
            return  # اتأكد قبل ما الدرع يخلص فعلياً
        except asyncio.TimeoutError:
            pass
        if timer.cancelled:
            return

        # محدش رد لحد ما الدرع خلص فعلياً -> تصعيد صوتي
        await self._escalate(timer)

    async def _send_pre_alert(self, timer: ShieldTimer):
        lang = timer.lang
        elapsed = max(0.0, timer.duration_seconds - PRE_ALERT_SECONDS)
        embed = styled_embed(
            title=t("shield_pre_alert_title", lang),
            description=t("shield_pre_alert_desc", lang),
            color=CRIMSON,
        )
        embed.add_field(
            name=t("shield_progress_field", lang),
            value=progress_bar(elapsed, timer.duration_seconds),
            inline=False,
        )
        view = ShieldAckView(self, timer_key(timer.guild_id, timer.user_id), timer.user_id, lang)
        try:
            if timer.channel:
                await timer.channel.send(content=timer.user.mention, embed=embed, view=view)
        except discord.HTTPException:
            pass
        try:
            await timer.user.send(embed=embed)
        except discord.Forbidden:
            pass  # المستخدم مقفل الـ DMs

    async def _try_soundboard(self, voice_channel: discord.VoiceChannel):
        """محاولة تشغيل صوت Soundboard على السيرفر (لو متاح) - أفضل جهد فقط، ومفيش مشكلة لو فشلت."""
        try:
            guild = voice_channel.guild
            fetch = getattr(guild, "fetch_soundboard_sounds", None)
            sounds = await fetch() if fetch else list(getattr(guild, "soundboard_sounds", []))
            if sounds:
                send = getattr(voice_channel, "send_soundboard_sound", None)
                if send:
                    await send(sounds[0])
        except Exception:
            pass  # الميزة دي مش متاحة في كل نسخ discord.py أو مفيش أصوات مضبوطة أصلاً

    async def _escalate(self, timer: ShieldTimer):
        lang = timer.lang
        guild = self.bot.get_guild(timer.guild_id)
        if guild is None:
            return

        target_channel: Optional[discord.VoiceChannel] = None
        member = guild.get_member(timer.user_id)
        if member and member.voice and member.voice.channel:
            target_channel = member.voice.channel
        elif timer.fallback_voice_channel:
            target_channel = timer.fallback_voice_channel

        vc: Optional[discord.VoiceClient] = None
        if target_channel:
            existing = guild.voice_client
            try:
                if existing and existing.is_connected():
                    if existing.channel.id != target_channel.id:
                        await existing.move_to(target_channel)
                    vc = existing
                else:
                    vc = await target_channel.connect()
                timer.audio_source = SirenAudioSource()
                if not vc.is_playing():
                    vc.play(timer.audio_source)
                asyncio.create_task(self._try_soundboard(target_channel))
            except Exception:
                log.exception("مقدرتش أدخل الروم الصوتية للتصعيد")
                vc = None

        try:
            desc = (
                t("shield_escalated_room_line", lang, channel=target_channel.name) if target_channel else ""
            ) + t("shield_escalated_instructions", lang)
            embed = styled_embed(
                title=t("shield_escalated_title", lang),
                description=desc,
                color=CRIMSON,
            )
            mentions = timer.user.mention
            if timer.leadership_role:
                mentions += f" {timer.leadership_role.mention}"
            await timer.channel.send(content=mentions, embed=embed)
        except discord.HTTPException:
            pass

        elapsed = 0.0
        acknowledged = False
        while elapsed < MAX_ESCALATION_SECONDS:
            try:
                await asyncio.wait_for(timer.ack_event.wait(), timeout=ESCALATION_PING_EVERY)
                acknowledged = True
                break
            except asyncio.TimeoutError:
                elapsed += ESCALATION_PING_EVERY
                if timer.cancelled:
                    break
                try:
                    await timer.channel.send(t("shield_escalation_ping", lang, user=timer.user.mention))
                except discord.HTTPException:
                    pass

        if timer.audio_source:
            timer.audio_source.stop_ringing()
        if vc and vc.is_connected():
            try:
                vc.stop()
                await vc.disconnect(force=True)
            except Exception:
                pass

        try:
            if acknowledged:
                embed = styled_embed(
                    title=t("shield_ack_done_title", lang),
                    description=t("shield_ack_done_desc", lang, user=timer.user.mention),
                    color=EMERALD,
                )
                renew_view = discord.ui.View(timeout=300)
                renew_button = discord.ui.Button(
                    label=t("shield_renew_same_duration_button", lang), style=discord.ButtonStyle.primary
                )

                async def _renew_callback(interaction: discord.Interaction, _timer=timer):
                    if interaction.user.id != _timer.user_id:
                        await interaction.response.send_message(
                            t("shield_ack_owner_only", _timer.lang), ephemeral=True
                        )
                        return
                    await self.renew_timer(interaction, _timer)

                renew_button.callback = _renew_callback
                renew_view.add_item(renew_button)
                await timer.channel.send(embed=embed, view=renew_view)
            else:
                embed = styled_embed(
                    title=t("shield_gave_up_title", lang),
                    description=t("shield_gave_up_desc", lang, user=timer.user.mention),
                    color=CRIMSON,
                )
                await timer.channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ShieldCog(bot))
