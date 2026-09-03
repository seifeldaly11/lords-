"""
/wiki - دليل اللعبة الشامل.
قائمة منسدلة لاختيار الفئة (وحوش / عتاد / أبطال / مرافقين)، وكل فئة بتفتح
قائمة فرعية أو أزرار حسب نوع المحتوى.
"""
import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load_json_data

CATEGORY_LABELS = {
    "monsters": "🐾 الوحوش",
    "gear": "🛡️ المعدات والعتاد",
    "heroes": "🦸 الأبطال",
    "companions": "🐉 المرافقين",
}


# ---------------------------------------------------------------------------
# المستوى 1: اختيار الفئة الرئيسية
# ---------------------------------------------------------------------------

class WikiCategorySelect(discord.ui.Select):
    def __init__(self, cog: "WikiCog"):
        self.cog = cog
        options = [
            discord.SelectOption(label=label, value=key)
            for key, label in CATEGORY_LABELS.items()
        ]
        super().__init__(placeholder="اختر فئة الدليل...", options=options)

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        if key == "monsters":
            view = MonsterSubView(self.cog.monster_data)
            content = f"{CATEGORY_LABELS[key]} — اختر الوحش عشان تشوف نوع الضرر، الأبطال المناسبين، والعتاد المطلوب:"
        elif key == "gear":
            view = GearSubView(self.cog.gear_tiers)
            content = f"{CATEGORY_LABELS[key]} — اختر النوع عشان تشوف أفضل التشكيلات (F2P / P2P / هجين):"
        elif key == "heroes":
            view = FormationSubView(self.cog.formations)
            content = f"{CATEGORY_LABELS[key]} — اختر نوع التشكيلة (كولوسيوم / حرب / دفاع):"
        else:
            view = CompanionSubView(self.cog.companions)
            content = f"{CATEGORY_LABELS[key]} — اختر المرافق عشان تشوف مهاراته وبوفاته وطريقة تجميعه:"
        await interaction.response.edit_message(content=content, view=view)


class WikiRootView(discord.ui.View):
    def __init__(self, cog: "WikiCog"):
        super().__init__(timeout=90)
        self.add_item(WikiCategorySelect(cog))


# ---------------------------------------------------------------------------
# مستوى 2: الوحوش (نوع الضرر + الأبطال + العتاد المطلوب)
# ---------------------------------------------------------------------------

class MonsterSubSelect(discord.ui.Select):
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
            title=f"{info['emoji']} {self.values[0].replace('_', ' ').capitalize()}",
            color=discord.Color.dark_green(),
        )
        embed.add_field(name="⚡ نوع الضرر المطلوب", value=info["damage_type"], inline=False)
        if info.get("defense_note"):
            embed.add_field(name="🛡️ ملاحظة الدفاع", value=info["defense_note"], inline=False)
        embed.add_field(name="🦸 الأبطال المقترحون", value="\n".join(f"• {h}" for h in info["heroes"]), inline=False)
        embed.add_field(
            name="🎽 العتاد المطلوب",
            value="طقم الصائد (Hunter Set) لو متاح، وإلا العتاد المتاح اللي يرفع الهجوم المناسب لنوع ضرر الوحش.",
            inline=False,
        )
        embed.set_footer(text="استخدم /wiki تاني للرجوع للقائمة الرئيسية")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MonsterSubView(discord.ui.View):
    def __init__(self, monster_data: dict):
        super().__init__(timeout=90)
        self.add_item(MonsterSubSelect(monster_data))


# ---------------------------------------------------------------------------
# مستوى 2: المعدات والعتاد (F2P / P2P / هجين)
# ---------------------------------------------------------------------------

class GearSubSelect(discord.ui.Select):
    def __init__(self, gear_tiers: dict):
        self.gear_tiers = gear_tiers
        labels = {"war": "⚔️ عتاد الحرب", "hunting": "🏹 عتاد الصيد", "economy": "🏗️ عتاد الاقتصاد"}
        options = [discord.SelectOption(label=labels[k], value=k, emoji=v.get("emoji")) for k, v in gear_tiers.items()]
        super().__init__(placeholder="اختر نوع العتاد...", options=options)

    async def callback(self, interaction: discord.Interaction):
        info = self.gear_tiers[self.values[0]]
        embed = discord.Embed(title=f"{info.get('emoji', '🛡️')} أفضل تشكيلات العتاد", color=discord.Color.gold())
        if info.get("p2p"):
            embed.add_field(name="💎 P2P", value=info["p2p"], inline=False)
        if info.get("f2p"):
            embed.add_field(name="🆓 F2P", value=info["f2p"], inline=False)
        if info.get("pieces"):
            embed.add_field(name="🔀 القطع (هجين)", value=info["pieces"], inline=False)
        if info.get("weak"):
            embed.add_field(name="⚠️ عتاد ضعيف", value=info["weak"], inline=False)
        if info.get("warning"):
            embed.add_field(name="⚠️ تحذير", value=info["warning"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class GearSubView(discord.ui.View):
    def __init__(self, gear_tiers: dict):
        super().__init__(timeout=90)
        self.add_item(GearSubSelect(gear_tiers))


# ---------------------------------------------------------------------------
# مستوى 2: الأبطال (تشكيلات كولوسيوم / حرب / دفاع)
# ---------------------------------------------------------------------------

class FormationSubSelect(discord.ui.Select):
    def __init__(self, formations: dict):
        self.formations = formations
        options = [
            discord.SelectOption(label=v["title"], value=k, emoji=v.get("emoji")) for k, v in formations.items()
        ]
        super().__init__(placeholder="اختر نوع التشكيلة...", options=options)

    async def callback(self, interaction: discord.Interaction):
        info = self.formations[self.values[0]]
        embed = discord.Embed(title=info["title"], description=info["desc"], color=discord.Color.purple())
        await interaction.response.send_message(embed=embed, ephemeral=True)


class FormationSubView(discord.ui.View):
    def __init__(self, formations: dict):
        super().__init__(timeout=90)
        self.add_item(FormationSubSelect(formations))


# ---------------------------------------------------------------------------
# مستوى 2: المرافقين (المهارات، البوفات، التجميع)
# ---------------------------------------------------------------------------

class CompanionSubSelect(discord.ui.Select):
    def __init__(self, companions: dict):
        self.companions = companions
        options = [
            discord.SelectOption(label=v["name"], value=k, emoji=v.get("emoji"))
            for k, v in companions.items() if not k.startswith("_")
        ]
        super().__init__(placeholder="اختر المرافق...", options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        info = self.companions[self.values[0]]
        embed = discord.Embed(title=f"{info['emoji']} {info['name']}", color=discord.Color.blue())
        embed.add_field(name="✨ المهارات", value=info["skills"], inline=False)
        embed.add_field(name="💪 البوفات", value=info["buffs"], inline=False)
        embed.add_field(name="📦 طريقة التجميع", value=info["gathering"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CompanionSubView(discord.ui.View):
    def __init__(self, companions: dict):
        super().__init__(timeout=90)
        self.add_item(CompanionSubSelect(companions))


# ---------------------------------------------------------------------------
# الـ Cog
# ---------------------------------------------------------------------------

class WikiCog(commands.Cog):
    """دليل اللعبة الشامل."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.monster_data = load_json_data("monsters.json")
        self.gear_tiers = load_json_data("gear_tiers.json")
        self.formations = load_json_data("formations.json")
        self.companions = load_json_data("companions.json")

    @app_commands.command(name="wiki", description="📚 دليل اللعبة الشامل: وحوش، عتاد، أبطال، ومرافقين")
    async def wiki(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "📚 **دليل لوردس موبايل الشامل**\nاختر الفئة اللي عايز تعرف عنها:",
            view=WikiRootView(self),
            ephemeral=True,
        )

    @app_commands.command(name="guide", description="📚 اختصار لـ /wiki - دليل اللعبة الشامل")
    async def guide(self, interaction: discord.Interaction):
        await self.wiki.callback(self, interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(WikiCog(bot))
