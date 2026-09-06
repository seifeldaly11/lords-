from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load, save

MARKET_FILE = "market"

RESOURCE_CHOICES = [
    app_commands.Choice(name="🍖 طعام", value="food"),
    app_commands.Choice(name="🪵 خشب", value="wood"),
    app_commands.Choice(name="🪨 حجر", value="stone"),
    app_commands.Choice(name="⛏️ خام/فولاذ", value="ore"),
    app_commands.Choice(name="💰 ذهب", value="gold"),
]
RESOURCE_LABELS = {c.value: c.name for c in RESOURCE_CHOICES}

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
    if give_resource.value == want_resource.value:
        await interaction.response.send_message("❌ ماينفعش نفس نوع المورد في العرض والطلب.", ephemeral=True)
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

    embed = discord.Embed(title="💱 تم إضافة عرضك في البورصة", color=discord.Color.blue())
    embed.add_field(name="لديّ", value=f"{give_amount:,.0f} {RESOURCE_LABELS[give_resource.value]}")
    embed.add_field(name="أريد", value=f"{want_amount:,.0f} {RESOURCE_LABELS[want_resource.value]}")
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
        notify = (
            f"🔔 لقينا تطابق محتمل في بورصة الموارد!\n"
            f"👤 <@{interaction.user.id}> عنده {give_amount:,.0f} {RESOURCE_LABELS[give_resource.value]} "
            f"ويبي {want_amount:,.0f} {RESOURCE_LABELS[want_resource.value]}\n"
            f"👤 <@{m['user_id']}> عنده {m['give_amount']:,.0f} {RESOURCE_LABELS[m['give']]} "
            f"ويبي {m['want_amount']:,.0f} {RESOURCE_LABELS[m['want']]}\n"
            f"تواصلوا وأتموا التبادل داخل اللعبة يدوياً 🤝"
        )
        try:
            await interaction.channel.send(notify)
        except discord.HTTPException:
            pass


@market_group.command(name="list", description="📋 عرض كل عروض التبادل النشطة في السيرفر")
async def market_list(interaction: discord.Interaction):
    data = load(MARKET_FILE)
    offers = [o for o in data.get(str(interaction.guild_id), []) if o["active"]]
    if not offers:
        await interaction.response.send_message("لا توجد عروض تبادل نشطة حالياً.", ephemeral=True)
        return

    embed = discord.Embed(title="💱 عروض بورصة الموارد النشطة", color=discord.Color.blue())
    for o in offers[-20:]:
        embed.add_field(
            name=f"{o['user_name']}",
            value=(
                f"يعطي: {o['give_amount']:,.0f} {RESOURCE_LABELS[o['give']]} "
                f"◀ مقابل ▶ يريد: {o['want_amount']:,.0f} {RESOURCE_LABELS[o['want']]}"
            ),
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@market_group.command(name="cancel", description="🗑️ ألغِ آخر عرض تبادل قمت بإضافته")
async def market_cancel(interaction: discord.Interaction):
    data = load(MARKET_FILE)
    gid = str(interaction.guild_id)
    offers = data.get(gid, [])
    mine = [o for o in offers if o["user_id"] == interaction.user.id and o["active"]]
    if not mine:
        await interaction.response.send_message("مفيش عروض نشطة ليك عشان تلغيها.", ephemeral=True)
        return
    mine[-1]["active"] = False
    save(MARKET_FILE, data)
    await interaction.response.send_message("✅ تم إلغاء آخر عرض ليك.", ephemeral=True)


class MarketCog(commands.Cog):
    """بورصة الموارد الداخلية - توفيق تلقائي بين طلبات الأعضاء."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot):
    bot.tree.add_command(market_group)
    await bot.add_cog(MarketCog(bot))
