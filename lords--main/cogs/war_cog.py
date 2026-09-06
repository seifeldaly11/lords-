from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang, t
from utils.storage import load, save, load_json_data

REPORTS_FILE = "reports"


# ---------------------------------------------------------------------------
# /counter - التشكيلة المضادة
# ---------------------------------------------------------------------------

class CounterModal(discord.ui.Modal):
    def __init__(self, lang: str):
        super().__init__(title=t("counter_modal_title", lang))
        self.lang = lang
        self.infantry = discord.ui.TextInput(label=t("counter_field_infantry", lang)[:45], placeholder="40")
        self.ranged = discord.ui.TextInput(label=t("counter_field_ranged", lang)[:45], placeholder="30")
        self.cavalry = discord.ui.TextInput(label=t("counter_field_cavalry", lang)[:45], placeholder="20")
        self.siege = discord.ui.TextInput(label=t("counter_field_siege", lang)[:45], placeholder="10")
        for item in (self.infantry, self.ranged, self.cavalry, self.siege):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.lang
        infantry_label = "🛡️ " + ("Infantry" if lang == "en" else "مشاة")
        ranged_label = "🏹 " + ("Ranged" if lang == "en" else "رماة")
        cavalry_label = "🐎 " + ("Cavalry" if lang == "en" else "فرسان")
        siege_label = "🏰 " + ("Siege" if lang == "en" else "حصار")
        try:
            comp = {
                infantry_label: float(self.infantry.value or 0),
                ranged_label: float(self.ranged.value or 0),
                cavalry_label: float(self.cavalry.value or 0),
                siege_label: float(self.siege.value or 0),
            }
        except ValueError:
            await interaction.response.send_message(t("err_invalid_numbers", lang), ephemeral=True)
            return

        dominant = max(comp, key=comp.get)

        # قاعدة تفوّق تقريبية (Rock-Paper-Scissors) شائعة الاستخدام في اللعبة
        counter_map = {
            infantry_label: (cavalry_label, "Wedge (" + ("offensive" if lang == "en" else "هجومي") + ")"),
            ranged_label: (infantry_label, "Phalanx (" + ("advanced defense" if lang == "en" else "دفاعي متقدم") + ")"),
            cavalry_label: (ranged_label, "Wedge"),
            siege_label: (
                ("🏹 Ranged or fast Cavalry" if lang == "en" else "🏹 رماة أو فرسان سريعة"),
                "Wedge",
            ),
        }
        counter_troop, formation = counter_map.get(dominant, (t("counter_mixed", lang), "Phalanx"))

        embed = discord.Embed(
            title=t("counter_title", lang),
            color=discord.Color.red(),
            timestamp=datetime.utcnow(),
        )
        breakdown = "\n".join(f"{k}: **{v:g}**" for k, v in comp.items())
        embed.add_field(name=t("counter_input_field", lang), value=breakdown, inline=False)
        embed.add_field(name=t("counter_dominant_field", lang), value=dominant, inline=True)
        embed.add_field(name=t("counter_suggestion_field", lang), value=counter_troop, inline=True)
        embed.add_field(name=t("counter_formation_field", lang), value=formation, inline=False)
        embed.set_footer(text=t("counter_footer", lang))
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CounterView(discord.ui.View):
    def __init__(self, lang: str):
        super().__init__(timeout=60)
        self.lang = lang
        self.open_modal.label = t("counter_button", lang)

    @discord.ui.button(emoji="⚔️", style=discord.ButtonStyle.danger)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CounterModal(self.lang))


# ---------------------------------------------------------------------------
# /report - سجل المعارك
# ---------------------------------------------------------------------------

class ReportModal(discord.ui.Modal):
    def __init__(self, lang: str):
        super().__init__(title=t("report_modal_title", lang))
        self.lang = lang
        self.opponent = discord.ui.TextInput(label=t("report_field_opponent", lang)[:45], placeholder="PlayerX")
        self.result = discord.ui.TextInput(label=t("report_field_result", lang)[:45], placeholder="Win")
        self.notes = discord.ui.TextInput(
            label=t("report_field_notes", lang)[:45], style=discord.TextStyle.paragraph, required=False
        )
        for item in (self.opponent, self.result, self.notes):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.lang
        data = load(REPORTS_FILE)
        gid = str(interaction.guild_id)
        data.setdefault(gid, [])
        entry = {
            "author_id": interaction.user.id,
            "author_name": str(interaction.user),
            "opponent": self.opponent.value,
            "result": self.result.value,
            "notes": self.notes.value or "-",
            "timestamp": datetime.utcnow().isoformat(),
        }
        data[gid].append(entry)
        save(REPORTS_FILE, data)

        embed = discord.Embed(title=t("report_saved_title", lang), color=discord.Color.green())
        embed.add_field(name=t("report_opponent_field", lang), value=entry["opponent"], inline=True)
        embed.add_field(name=t("report_result_field", lang), value=entry["result"], inline=True)
        embed.add_field(name=t("report_notes_field", lang), value=entry["notes"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


report_group = app_commands.Group(name="report", description="📝 تسجيل واستدعاء سجل المعارك")


@report_group.command(name="add", description="📝 سجّل معركة جديدة في السجل")
@app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
async def report_add(interaction: discord.Interaction):
    lang = get_lang(interaction.guild_id)
    await interaction.response.send_modal(ReportModal(lang))


@report_add.error
async def report_add_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    lang = get_lang(interaction.guild_id)
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = (
            f"⏳ استنى شوية قبل ما تسجّل تقرير تاني ({error.retry_after:.0f} ثانية)."
            if lang == "ar"
            else f"⏳ Please wait {error.retry_after:.0f}s before logging another report."
        )
        await interaction.response.send_message(msg, ephemeral=True)
    else:
        await interaction.response.send_message("❌ حصل خطأ غير متوقع.", ephemeral=True)


@report_group.command(name="list", description="📚 استدعاء آخر المعارك المسجلة في السيرفر")
@app_commands.describe(count="عدد المعارك المطلوب عرضها (افتراضي 10)")
async def report_list(interaction: discord.Interaction, count: app_commands.Range[int, 1, 25] = 10):
    lang = get_lang(interaction.guild_id)
    data = load(REPORTS_FILE)
    entries = data.get(str(interaction.guild_id), [])
    if not entries:
        await interaction.response.send_message(t("report_none_yet", lang), ephemeral=True)
        return

    embed = discord.Embed(title=t("report_list_title", lang), color=discord.Color.dark_gold())
    for e in entries[-count:][::-1]:
        embed.add_field(
            name=t("report_vs", lang, result=e["result"], opponent=e["opponent"]),
            value=t(
                "report_by_line",
                lang,
                author=e["author_name"],
                notes=e["notes"],
                time=e["timestamp"][:16].replace("T", " "),
            ),
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@report_group.command(name="user", description="🔍 استدعاء سجل معارك عضو معيّن")
async def report_user(interaction: discord.Interaction, member: discord.Member):
    lang = get_lang(interaction.guild_id)
    data = load(REPORTS_FILE)
    entries = [e for e in data.get(str(interaction.guild_id), []) if e["author_id"] == member.id]
    if not entries:
        await interaction.response.send_message(
            t("report_none_for_user", lang, member=member.mention), ephemeral=True
        )
        return

    embed = discord.Embed(title=t("report_user_title", lang, member=member.display_name), color=discord.Color.dark_gold())
    for e in entries[-15:][::-1]:
        embed.add_field(
            name=t("report_vs", lang, result=e["result"], opponent=e["opponent"]),
            value=t("report_notes_line", lang, notes=e["notes"], time=e["timestamp"][:16].replace("T", " ")),
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /darknest
# ---------------------------------------------------------------------------

class DarknestSelect(discord.ui.Select):
    def __init__(self, data: dict, lang: str):
        self.data = data
        self.lang = lang
        options = [
            discord.SelectOption(label=f"Dark Nest Lv {lvl}", value=lvl)
            for lvl in data.keys() if lvl != "_note"
        ]
        super().__init__(placeholder=t("darknest_select_placeholder", lang), options=options)

    async def callback(self, interaction: discord.Interaction):
        lang = self.lang
        info = self.data[self.values[0]]
        embed = discord.Embed(
            title=t("darknest_title", lang, lvl=self.values[0]),
            color=discord.Color.dark_red(),
        )
        embed.add_field(name=t("darknest_heroes_field", lang), value=info["heroes"][lang], inline=False)
        embed.add_field(name=t("darknest_formation_field", lang), value=info["formation"][lang], inline=True)
        embed.add_field(name=t("darknest_notes_field", lang), value=info["notes"][lang], inline=False)
        embed.set_footer(text=t("darknest_footer", lang))
        await interaction.response.send_message(embed=embed, ephemeral=True)


class DarknestView(discord.ui.View):
    def __init__(self, data: dict, lang: str):
        super().__init__(timeout=60)
        self.add_item(DarknestSelect(data, lang))


# ---------------------------------------------------------------------------
# /colo
# ---------------------------------------------------------------------------

class ColoModal(discord.ui.Modal):
    def __init__(self, lang: str):
        super().__init__(title=t("colo_modal_title", lang))
        self.lang = lang
        self.heroes = discord.ui.TextInput(
            label=t("colo_field_heroes", lang)[:45],
            placeholder="Talus, Natalya" if lang == "en" else "طالوس, ناتاليا",
        )
        self.add_item(self.heroes)

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.lang
        colo_data = load_json_data("colo_counters.json")
        heroes_db = colo_data.get("heroes", [])
        general_rule = colo_data.get("general_rule", {}).get(lang, "")

        entered = [h.strip() for h in self.heroes.value.split(",") if h.strip()]
        embed = discord.Embed(title=t("colo_result_title", lang), color=discord.Color.blurple())
        for hero in entered:
            match = next(
                (
                    h for h in heroes_db
                    if hero.lower() in (h["names"].get("ar", "").lower(), h["names"].get("en", "").lower())
                ),
                None,
            )
            display_name = hero
            if match:
                display_name = match["names"].get(lang, hero)
                embed.add_field(
                    name=t("colo_vs_field", lang, hero=display_name),
                    value=match["counter"][lang],
                    inline=False,
                )
            else:
                embed.add_field(
                    name=t("colo_vs_field", lang, hero=display_name),
                    value=t("colo_no_data", lang),
                    inline=False,
                )
        embed.add_field(name=t("colo_general_rule_field", lang), value=general_rule, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# الـ Cog
# ---------------------------------------------------------------------------

class WarCog(commands.Cog):
    """أدوات الحرب والتكتيك (War Room)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.darknest_data = load_json_data("darknest.json")

    @app_commands.command(name="counter", description="⚔️ احصل على التشكيلة المضادة المثالية لتشكيلة العدو")
    async def counter(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        await interaction.response.send_message(
            t("counter_prompt", lang), view=CounterView(lang), ephemeral=True
        )

    @app_commands.command(name="darknest", description="🏯 أفضل أبطال وتشكيلة لإسقاط الحصن المظلم")
    async def darknest(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        await interaction.response.send_message(
            t("darknest_prompt", lang), view=DarknestView(self.darknest_data, lang), ephemeral=True
        )

    @app_commands.command(name="colo", description="🏟️ محاكي الكولوسيوم - التشكيلة المضادة لأبطال الخصم")
    async def colo(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        await interaction.response.send_modal(ColoModal(lang))

    @app_commands.command(name="analyze", description="🖼️ محلل تقارير المعارك - ارفع صورة التقرير وأدخل الأرقام لتحليلها")
    @app_commands.describe(screenshot="صورة تقرير المعركة (اختياري - للتوثيق فقط)")
    async def analyze(self, interaction: discord.Interaction, screenshot: Optional[discord.Attachment] = None):
        lang = get_lang(interaction.guild_id)
        note = ""
        if screenshot:
            if not (screenshot.content_type or "").startswith("image/"):
                await interaction.response.send_message(t("analyze_bad_image", lang), ephemeral=True)
                return
            note = t("analyze_with_image_note", lang, filename=screenshot.filename)
        await interaction.response.send_message(
            note or t("analyze_no_image_note", lang),
            view=CounterView(lang),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    bot.tree.add_command(report_group)
    await bot.add_cog(WarCog(bot))
