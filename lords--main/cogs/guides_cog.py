import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang, t, TROOP_LABELS_I18N
from utils.storage import load_json_data, load, save
from utils.ui import styled_embed, GOLD

GEAR_PREF_FILE = "gear_prefs"  # آخر اختيار (نوع قوات + F2P/P2P) لكل يوزر، عشان زرار "نفس اختيارك الأخير"


def _get_gear_pref(user_id: int) -> dict | None:
    return load(GEAR_PREF_FILE).get(str(user_id))


def _set_gear_pref(user_id: int, troop: str, kind: str) -> None:
    data = load(GEAR_PREF_FILE)
    data[str(user_id)] = {"troop": troop, "kind": kind}
    save(GEAR_PREF_FILE, data)

TROOP_TYPES = ["infantry", "ranged", "cavalry", "siege", "hybrid"]
# نسخة عربي فقط لسه مستخدمة في أماكن تانية بالملف ده (monster/info/dict) لسه مترجمتش
TROOP_LABELS = {
    "infantry": "🛡️ مشاة",
    "ranged": "🏹 رماة",
    "cavalry": "🐎 فرسان",
    "siege": "🏰 حصار",
    "hybrid": "🔀 هجين",
}


# ---------------------------------------------------------------------------
# /gear (بيحترم /language بالكامل)
# ---------------------------------------------------------------------------

class GearTypeSelect(discord.ui.Select):
    def __init__(self, gear_data: dict, lang: str):
        self.gear_data = gear_data
        self.lang = lang
        options = [
            discord.SelectOption(label=TROOP_LABELS_I18N[tr][lang], value=tr) for tr in TROOP_TYPES
        ]
        super().__init__(placeholder=t("gear_troop_select_placeholder", lang), options=options)

    async def callback(self, interaction: discord.Interaction):
        troop_label = TROOP_LABELS_I18N[self.values[0]][self.lang]
        await interaction.response.send_message(
            t("gear_choose_player_type", self.lang, troop=troop_label),
            view=GearPlayerTypeView(self.gear_data, self.values[0], self.lang),
            ephemeral=True,
        )


class GearCompareAllButton(discord.ui.Button):
    """بطاقة مقارنة سريعة: كل أنواع القوات F2P مقابل P2P في Embed واحد منظم."""

    def __init__(self, gear_data: dict, lang: str):
        self.gear_data = gear_data
        self.lang = lang
        super().__init__(
            label="🆚 قارن كل الأنواع" if lang == "ar" else "🆚 Compare all types",
            style=discord.ButtonStyle.secondary,
        )

    async def callback(self, interaction: discord.Interaction):
        embed = styled_embed(
            title="🆚 مقارنة سريعة: أفضل عتاد لكل نوع قوات" if self.lang == "ar" else "🆚 Quick gear comparison by troop type",
            color=GOLD,
            lang=self.lang,
        )
        for troop in TROOP_TYPES:
            info = self.gear_data[troop]
            label = TROOP_LABELS_I18N[troop][self.lang]
            embed.add_field(name=f"{info['emoji']} {label} — F2P 🆓", value=info["f2p"][self.lang][:180], inline=True)
            embed.add_field(name=f"{info['emoji']} {label} — P2P 💎", value=info["p2p"][self.lang][:180], inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)  # فاصل عشان الصفوف تترتب 2x2
        await interaction.response.send_message(embed=embed, ephemeral=True)


class GearLastChoiceButton(discord.ui.Button):
    """زرار لمسة واحدة يرجّع آخر نتيجة (نوع قوات + F2P/P2P) طلبها اليوزر من غير ما يعيد الاختيار."""

    def __init__(self, gear_data: dict, lang: str, pref: dict):
        self.gear_data = gear_data
        self.lang = lang
        self.pref = pref
        troop_label = TROOP_LABELS_I18N[pref["troop"]][lang]
        kind_label = pref["kind"].upper()
        super().__init__(
            label=f"⚡ {troop_label} {kind_label}" if lang == "ar" else f"⚡ Same as last time ({troop_label} {kind_label})",
            style=discord.ButtonStyle.success,
        )

    async def callback(self, interaction: discord.Interaction):
        info = self.gear_data[self.pref["troop"]]
        kind = self.pref["kind"]
        troop_label = TROOP_LABELS_I18N[self.pref["troop"]][self.lang]
        embed = styled_embed(
            title=t("gear_result_title", self.lang, emoji=info["emoji"], troop=troop_label, kind=kind.upper()),
            description=info[kind][self.lang],
            color=GOLD,
            lang=self.lang,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class GearTypeView(discord.ui.View):
    def __init__(self, gear_data: dict, lang: str, user_id: int | None = None):
        super().__init__(timeout=60)
        self.add_item(GearTypeSelect(gear_data, lang))
        self.add_item(GearCompareAllButton(gear_data, lang))
        pref = _get_gear_pref(user_id) if user_id else None
        if pref:
            self.add_item(GearLastChoiceButton(gear_data, lang, pref))


class GearPlayerTypeView(discord.ui.View):
    def __init__(self, gear_data: dict, troop: str, lang: str):
        super().__init__(timeout=60)
        self.gear_data = gear_data
        self.troop = troop
        self.lang = lang

    @discord.ui.button(label="F2P 🆓", style=discord.ButtonStyle.green)
    async def f2p(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send(interaction, "f2p")

    @discord.ui.button(label="P2P 💎", style=discord.ButtonStyle.blurple)
    async def p2p(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send(interaction, "p2p")

    async def _send(self, interaction: discord.Interaction, kind: str):
        _set_gear_pref(interaction.user.id, self.troop, kind)
        info = self.gear_data[self.troop]
        troop_label = TROOP_LABELS_I18N[self.troop][self.lang]
        embed = styled_embed(
            title=t(
                "gear_result_title", self.lang,
                emoji=info["emoji"], troop=troop_label, kind=kind.upper(),
            ),
            description=info[kind][self.lang],
            color=GOLD,
            lang=self.lang,
        )
        other_kind = "p2p" if kind == "f2p" else "f2p"
        embed.add_field(
            name=f"⚖️ {'مقارنة سريعة' if self.lang == 'ar' else 'Quick comparison'} — {other_kind.upper()}",
            value=info[other_kind][self.lang][:250],
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /monster
# ---------------------------------------------------------------------------

class MonsterSelect(discord.ui.Select):
    def __init__(self, monster_data: dict):
        self.monster_data = monster_data
        options = [
            discord.SelectOption(label=key.replace("_", " ").capitalize(), value=key, emoji=val.get("emoji"))
            for key, val in monster_data.items() if not key.startswith("_")
        ]
        super().__init__(placeholder="اختر اسم الوحش...", options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        info = self.monster_data[self.values[0]]
        embed = discord.Embed(
            title=f"{info['emoji']} أفضل أبطال لصيد: {self.values[0].replace('_', ' ').capitalize()}",
            color=discord.Color.dark_green(),
        )
        embed.add_field(name="⚡ نوع الضرر المطلوب", value=info["damage_type"], inline=False)
        if info.get("defense_note"):
            embed.add_field(name="🛡️ ملاحظة الدفاع", value=info["defense_note"], inline=False)
        embed.add_field(name="🦸 الأبطال المقترحون", value="\n".join(f"• {h}" for h in info["heroes"]), inline=False)
        embed.set_footer(text="بيانات إرشادية عامة - قد تختلف حسب مستوى الوحش")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MonsterView(discord.ui.View):
    def __init__(self, monster_data: dict):
        super().__init__(timeout=60)
        self.add_item(MonsterSelect(monster_data))



# ---------------------------------------------------------------------------
# /info
# ---------------------------------------------------------------------------

class InfoSelect(discord.ui.Select):
    def __init__(self, info_data: dict):
        self.info_data = info_data
        options = [
            discord.SelectOption(label=val["title"], value=key, emoji=val.get("emoji"))
            for key, val in info_data.items()
        ]
        super().__init__(placeholder="اختر الحدث اللي عايز تعرف عنه...", options=options)

    async def callback(self, interaction: discord.Interaction):
        info = self.info_data[self.values[0]]
        embed = discord.Embed(
            title=f"{info['emoji']} {info['title']}",
            description=info["desc"],
            color=discord.Color.magenta(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class InfoView(discord.ui.View):
    def __init__(self, info_data: dict):
        super().__init__(timeout=60)
        self.add_item(InfoSelect(info_data))


# ---------------------------------------------------------------------------
# الـ Cog
# ---------------------------------------------------------------------------

class GuidesCog(commands.Cog):
    """الأدلة والأبطال والمصطلحات."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gear_data = load_json_data("gear.json")
        self.monster_data = load_json_data("monsters.json")
        self.dict_data = load_json_data("dict.json")
        self.info_data = load_json_data("info.json")

    @app_commands.command(name="gear", description="🛡️ أفضل عتاد لكل نوع قوات (F2P/P2P)")
    async def gear(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        await interaction.response.send_message(
            t("gear_choose_troop", lang),
            view=GearTypeView(self.gear_data, lang, interaction.user.id),
            ephemeral=True,
        )

    @app_commands.command(name="monster", description="🐾 أفضل أبطال الصيد حسب اسم الوحش")
    async def monster(self, interaction: discord.Interaction):
        await interaction.response.send_message("اختر الوحش:", view=MonsterView(self.monster_data), ephemeral=True)

    @app_commands.command(name="dict", description="📖 قاموس مصطلحات اللعبة السريع")
    @app_commands.describe(term="اكتب المصطلح (T4, Rally, RSS...) واختر من الاقتراحات")
    async def dict_cmd(self, interaction: discord.Interaction, term: str):
        match = next((v for k, v in self.dict_data.items() if k.lower() == term.lower()), None)
        if not match:
            close = [k for k in self.dict_data if term.lower() in k.lower()]
            if close:
                await interaction.response.send_message(
                    f"❓ ما لقيتش '{term}' بالظبط. قصدك: {', '.join(close[:5])}؟", ephemeral=True
                )
            else:
                await interaction.response.send_message(f"❌ المصطلح '{term}' مش موجود في القاموس.", ephemeral=True)
            return
        embed = discord.Embed(title=f"📖 {term.upper()}", description=match, color=discord.Color.light_grey())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @dict_cmd.autocomplete("term")
    async def dict_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        matches = [k for k in self.dict_data.keys() if current in k.lower()]
        return [app_commands.Choice(name=k, value=k) for k in matches[:25]]

    @app_commands.command(name="info", description="ℹ️ شرح الأحداث (ساحة التنين، المنفرد، KvK، الجحيم...)")
    async def info(self, interaction: discord.Interaction):
        await interaction.response.send_message("اختر الحدث:", view=InfoView(self.info_data), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GuidesCog(bot))
