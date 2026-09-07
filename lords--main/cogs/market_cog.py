from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load, save
from utils.i18n import get_lang, t, RESOURCE_LABELS_I18N

MARKET_FILE = "market"

# ⚠️ أسماء الموارد هنا (Choice.name) هي Metadata بتتسجل مع ديسكورد وقت تشغيل
# البوت - زي أسماء ووصف الأوامر بالظبط - فمش بتتغيّر ديناميكياً مع /language.
# اللي بيتغيّر فعلاً هو اسم المورد جوه رد البوت نفسه (Embeds/الرسائل)، وده بيجيب
# ترجمته من RESOURCE_LABELS_I18N في utils/i18n.py.
RESOURCE_CHOICES = [
    app_commands.Choice(name="🍖 طعام", value="food"),
    app_commands.Choice(name="🪵 خشب", value="wood"),
    app_commands.Choice(name="🪨 حجر", value="stone"),
    app_commands.Choice(name="⛏️ خام/فولاذ", value="ore"),
    app_commands.Choice(name="💰 ذهب", value="gold"),
]

market_group = app_commands.Group(name="market", description="💱 بورصة تبادل الموارد بين أعضاء التحالف")


@market_group.command(name="offer", description="💱 أضف عرض تبادل موارد (عندي X مقابل Y)")
@app_commands.describe(
    give_resource="نوع المورد اللي هتديه",
    give_amount="الكمية اللي هتديها",
    want_resource="نوع المورد اللي عايزه",
    want_amount="الكمية اللي عايزها",
)
@app_commands.choices(give_resource=RESOURCE_CHOICES, want_resource=RESOURCE_CHOICES)
async def market_offer(
    interaction: discord.Interaction,
    give_resource: app_commands.Choice[str],
    give_amount: app_commands.Range[float, 1, None],
    want_resource: app_commands.Choice[str],
    want_amount: app_commands.Range[float, 1, None],
):
    lang = get_lang(interaction.guild_id, interaction.user.id)

    if give_resource.value == want_resource.value:
        await interaction.response.send_message(t("market_same_resource", lang), ephemeral=True)
        return

    data = load(MARKET_FILE)
    gid = str(interaction.guild_id)
    data.setdefault(gid, [])

    offer = {
        "id": f"{interaction.user.id}-{datetime.utcnow().timestamp()}",
        "user_id": interaction.user.id,
        "user_name": str(interaction.user),
        "give": give_resource.value,
        "give_amount": give_amount,
        "want": want_resource.value,
        "want_amount": want_amount,
        "timestamp": datetime.utcnow().isoformat(),
        "active": True,
    }
    data[gid].append(offer)
    save(MARKET_FILE, data)

    give_label = RESOURCE_LABELS_I18N[give_resource.value][lang]
    want_label = RESOURCE_LABELS_I18N[want_resource.value][lang]

    embed = discord.Embed(title=t("market_offer_added_title", lang), color=discord.Color.blue())
    embed.add_field(name=t("market_have_field", lang), value=f"{give_amount:,.0f} {give_label}")
    embed.add_field(name=t("market_want_field", lang), value=f"{want_amount:,.0f} {want_label}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

    # البحث عن تطابق تلقائي: حد تاني عرضه (يديه ما إنت عايزه) و(عايز اللي إنت عندك) بكميات كافية
    matches = [
        o
        for o in data[gid]
        if o["active"]
        and o["user_id"] != interaction.user.id
        and o["give"] == want_resource.value
        and o["want"] == give_resource.value
        and o["give_amount"] >= want_amount
        and o["want_amount"] <= give_amount
    ]
    if matches:
        m = matches[0]
        notify = t(
            "market_match_notify", lang,
            user1=interaction.user.id,
            amount1=f"{give_amount:,.0f}",
            res1=give_label,
            want1=f"{want_amount:,.0f}",
            res2=want_label,
            user2=m["user_id"],
            amount2=f"{m['give_amount']:,.0f}",
            res3=RESOURCE_LABELS_I18N[m["give"]][lang],
            want2=f"{m['want_amount']:,.0f}",
            res4=RESOURCE_LABELS_I18N[m["want"]][lang],
        )
        try:
            await interaction.channel.send(notify)
        except discord.HTTPException:
            pass


@market_group.command(name="list", description="📋 عرض كل عروض التبادل النشطة في السيرفر")
async def market_list(interaction: discord.Interaction):
    lang = get_lang(interaction.guild_id, interaction.user.id)
    data = load(MARKET_FILE)
    offers = [o for o in data.get(str(interaction.guild_id), []) if o["active"]]
    if not offers:
        await interaction.response.send_message(t("market_list_empty", lang), ephemeral=True)
        return

    embed = discord.Embed(title=t("market_list_title", lang), color=discord.Color.blue())
    for o in offers[-20:]:
        embed.add_field(
            name=f"{o['user_name']}",
            value=t(
                "market_list_field_value", lang,
                give_amount=f"{o['give_amount']:,.0f}",
                give_res=RESOURCE_LABELS_I18N[o["give"]][lang],
                want_amount=f"{o['want_amount']:,.0f}",
                want_res=RESOURCE_LABELS_I18N[o["want"]][lang],
            ),
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@market_group.command(name="cancel", description="🗑️ ألغِ آخر عرض تبادل قمت بإضافته")
async def market_cancel(interaction: discord.Interaction):
    lang = get_lang(interaction.guild_id, interaction.user.id)
    data = load(MARKET_FILE)
    gid = str(interaction.guild_id)
    offers = data.get(gid, [])
    mine = [o for o in offers if o["user_id"] == interaction.user.id and o["active"]]
    if not mine:
        await interaction.response.send_message(t("market_cancel_none", lang), ephemeral=True)
        return
    mine[-1]["active"] = False
    save(MARKET_FILE, data)
    await interaction.response.send_message(t("market_cancel_success", lang), ephemeral=True)


class MarketCog(commands.Cog):
    """بورصة الموارد الداخلية - توفيق تلقائي بين طلبات الأعضاء."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot):
    bot.tree.add_command(market_group)
    await bot.add_cog(MarketCog(bot))
