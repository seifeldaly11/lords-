"""
🎯 متجر الحسابات + نظام البلاغات والوسيط (Shop / Report / Middleman).

كل الأوامر هنا عامة (الكل في التشانيل يشوف الرد) وثنائية اللغة بالكامل حسب
اختيار العضو (/language me) أو لغة السيرفر (/language server).

- 🛍️ /shop      : عرض كل الحسابات المتاحة في المتجر.
- 🏷️ /sell      : إدراج حساب للبيع.
- 🔍 /view      : تفاصيل حساب معيّن برقم المعرف (ID).
- 🚨 /report    : بلاغ عن مشكلة شراء / حساب مخالف / تواصل مع الدعم.
- 🛡️ /middleman : طلب وسيط معتمد لتأمين عملية التبادل.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load, save, get_leadership_role_id
from utils.ui import styled_embed, GOLD, CRIMSON, ROYAL_BLUE
from utils.i18n import get_lang, t

log = logging.getLogger("lordsbot.shop")

SHOP_FILE = "shop_accounts"
REPORTS_FILE = "shop_reports"
MIDDLEMAN_FILE = "middleman_requests"
SHOP_CHANNEL_KEY = "shop_channel"
MIDDLEMAN_CHANNEL_KEY = "middleman_channel"

MAX_SHOP_ENTRIES = 10


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_id(entries: list[dict], prefix: str) -> str:
    return f"{prefix}{len(entries) + 1:04d}"


def _guild_entries(file_name: str, guild_id: int) -> tuple[dict, list[dict]]:
    data = load(file_name)
    gid = str(guild_id)
    data.setdefault(gid, [])
    return data, data[gid]


def _leadership_mention(guild: Optional[discord.Guild]) -> str:
    if guild is None:
        return ""
    role_id = get_leadership_role_id(guild.id)
    role = guild.get_role(role_id) if role_id else None
    return role.mention if role else ""


# ---------------------------------------------------------------------------
# 🛡️ زرار استلام الوسيط
# ---------------------------------------------------------------------------

class MiddlemanView(discord.ui.View):
    def __init__(self, lang: str, request_id: str):
        super().__init__(timeout=None)
        self.lang = lang
        self.request_id = request_id
        self.take.label = t("middleman_take_button", lang)

    @discord.ui.button(label="🛡️", style=discord.ButtonStyle.success)
    async def take(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        member = interaction.user
        role_id = get_leadership_role_id(interaction.guild_id) if interaction.guild_id else None
        is_leader = bool(role_id) and any(r.id == role_id for r in getattr(member, "roles", []))
        is_admin = getattr(getattr(member, "guild_permissions", None), "manage_guild", False)
        if not (is_leader or is_admin):
            await interaction.response.send_message(t("middleman_admin_only_take", lang), ephemeral=False)
            return

        data, entries = _guild_entries(MIDDLEMAN_FILE, interaction.guild_id)
        for entry in entries:
            if entry["id"] == self.request_id:
                entry["middleman_id"] = member.id
                entry["status"] = "taken"
        save(MIDDLEMAN_FILE, data)

        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except discord.HTTPException:
            pass
        await interaction.response.send_message(t("middleman_taken", lang, user=member.mention))


# ---------------------------------------------------------------------------
# الـ Cog
# ---------------------------------------------------------------------------

class ShopCog(commands.Cog):
    """🎯 متجر الحسابات ونظام البلاغات والوسيط."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------------- /shop
    @app_commands.command(name="shop", description="🛍️ Browse all accounts currently listed in the shop")
    async def shop(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        _, entries = _guild_entries(SHOP_FILE, interaction.guild_id)
        open_entries = [e for e in entries if e.get("status") == "open"]

        if not open_entries:
            await interaction.response.send_message(t("shop_empty", lang))
            return

        embed = styled_embed(title=t("shop_title", lang), color=GOLD, lang=lang)
        for entry in open_entries[-MAX_SHOP_ENTRIES:][::-1]:
            embed.add_field(
                name=f"🏷️ `{entry['id']}` • {entry['title']}",
                value=t(
                    "shop_entry_value", lang,
                    price=entry["price"],
                    seller=f"<@{entry['seller_id']}>",
                    id=entry["id"],
                ),
                inline=False,
            )
        embed.set_footer(text=t("shop_footer", lang, count=len(open_entries)))
        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------------- /sell
    @app_commands.command(name="sell", description="🏷️ List your account for sale in the shop")
    @app_commands.describe(
        title="Short account title / عنوان مختصر للحساب",
        price="Asking price / السعر المطلوب",
        details="Account details: level, heroes, power… / تفاصيل الحساب",
        contact="How buyers reach you / طريقة التواصل معك",
        image="Optional screenshot / صورة اختيارية",
    )
    async def sell(
        self,
        interaction: discord.Interaction,
        title: app_commands.Range[str, 3, 100],
        price: app_commands.Range[str, 1, 50],
        details: app_commands.Range[str, 3, 900],
        contact: Optional[app_commands.Range[str, 2, 100]] = None,
        image1: Optional[discord.Attachment] = None,
        image2: Optional[discord.Attachment] = None,
        image3: Optional[discord.Attachment] = None,
        image4: Optional[discord.Attachment] = None,
        image5: Optional[discord.Attachment] = None,
        more_images_urls: Optional[str] = None,
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)

        if image is not None and not (image.content_type or "").startswith("image/"):
            await interaction.response.send_message(t("sell_bad_image", lang), ephemeral=False)
            return

        data, entries = _guild_entries(SHOP_FILE, interaction.guild_id)
        entry = {
            "id": _next_id(entries, "A"),
            "seller_id": interaction.user.id,
            "seller_name": str(interaction.user),
            "title": title,
            "price": price,
            "details": details,
            "contact": contact,
            "image_url": image.url if image else None,
            "status": "open",
            "timestamp": _now_iso(),
        }
        entries.append(entry)
        save(SHOP_FILE, data)

        embed = self._listing_embed(entry, lang, title_key="sell_added_title")
        embed.description = t("sell_added_desc", lang, id=entry["id"])
        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------------- /view
    @app_commands.command(name="view", description="🔍 View full details of a listing by its ID")
    @app_commands.describe(listing_id="Listing ID from /shop / رقم معرف العرض")
    async def view(self, interaction: discord.Interaction, listing_id: str):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        _, entries = _guild_entries(SHOP_FILE, interaction.guild_id)
        wanted = listing_id.strip().upper()
        entry = next((e for e in entries if e["id"].upper() == wanted), None)

        if entry is None:
            await interaction.response.send_message(t("view_not_found", lang, id=listing_id))
            return

        embed = self._listing_embed(entry, lang, title_key="view_title")
        await interaction.response.send_message(embed=embed)

    @view.autocomplete("listing_id")
    async def view_autocomplete(self, interaction: discord.Interaction, current: str):
        _, entries = _guild_entries(SHOP_FILE, interaction.guild_id)
        current = (current or "").lower()
        return [
            app_commands.Choice(name=f"{e['id']} • {e['title'][:60]}", value=e["id"])
            for e in entries
            if e.get("status") == "open" and (current in e["id"].lower() or current in e["title"].lower())
        ][:25]

    def _listing_embed(self, entry: dict, lang: str, title_key: str) -> discord.Embed:
        embed = styled_embed(title=t(title_key, lang, id=entry["id"]), color=GOLD, lang=lang)
        embed.add_field(name=t("sell_field_title", lang), value=entry["title"], inline=False)
        embed.add_field(name=t("sell_field_price", lang), value=f"**{entry['price']}**")
        embed.add_field(
            name=t("view_field_status", lang),
            value=t("view_status_open", lang) if entry.get("status") == "open" else t("view_status_closed", lang),
        )
        embed.add_field(name=t("sell_field_seller", lang), value=f"<@{entry['seller_id']}>")
        embed.add_field(name=t("sell_field_details", lang), value=entry["details"][:1000], inline=False)
        if entry.get("contact"):
            embed.add_field(name=t("sell_field_contact", lang), value=entry["contact"], inline=False)
        if entry.get("image_url"):
            embed.set_image(url=entry["image_url"])
        embed.add_field(name="\u200b", value=t("sell_safety_note", lang), inline=False)
        return embed

    # -------------------------------------------------------------- /report
    @app_commands.command(name="report", description="🚨 Report a purchase issue, a bad account, or contact support")
    @app_commands.describe(
        details="What happened / اشرح المشكلة بالتفصيل",
        member="Member involved / العضو الطرف التاني",
        listing_id="Related listing ID / معرف العرض المرتبط",
    )
    @app_commands.choices(
        report_type=[
            app_commands.Choice(name="🛒 مشكلة شراء / Purchase issue", value="purchase"),
            app_commands.Choice(name="⚠️ حساب مخالف / Violating account", value="scam"),
            app_commands.Choice(name="🎧 دعم فني / Support", value="support"),
        ]
    )
    async def report(
        self,
        interaction: discord.Interaction,
        report_type: app_commands.Choice[str],
        details: app_commands.Range[str, 5, 900],
        member: Optional[discord.Member] = None,
        listing_id: Optional[str] = None,
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        data, entries = _guild_entries(REPORTS_FILE, interaction.guild_id)
        entry = {
            "id": _next_id(entries, "R"),
            "type": report_type.value,
            "details": details,
            "reporter_id": interaction.user.id,
            "target_id": member.id if member else None,
            "listing_id": listing_id,
            "status": "open",
            "timestamp": _now_iso(),
        }
        entries.append(entry)
        save(REPORTS_FILE, data)

        type_key = {
            "purchase": "report_type_purchase",
            "scam": "report_type_scam",
            "support": "report_type_support",
        }[report_type.value]

        embed = styled_embed(
            title=t("report_title", lang),
            description=t("report_thanks", lang, id=entry["id"]),
            color=CRIMSON,
            lang=lang,
        )
        embed.add_field(name=t("report_field_type", lang), value=t(type_key, lang), inline=False)
        embed.add_field(name=t("report_field_reporter", lang), value=interaction.user.mention)
        if member:
            embed.add_field(name=t("report_field_target", lang), value=member.mention)
        if listing_id:
            embed.add_field(name=t("report_field_listing", lang), value=f"`{listing_id}`")
        embed.add_field(name=t("report_field_details", lang), value=details[:1000], inline=False)

        mention = _leadership_mention(interaction.guild)
        await interaction.response.send_message(content=mention or None, embed=embed)

    # ----------------------------------------------------------- /middleman
    @app_commands.command(name="middleman", description="🛡️ Request a trusted middleman to secure a trade")
    @app_commands.describe(
        deal="Deal details / تفاصيل العملية",
        partner="The other party / الطرف التاني",
        listing_id="Related listing ID / معرف العرض",
    )
    async def middleman(
        self,
        interaction: discord.Interaction,
        deal: app_commands.Range[str, 5, 900],
        partner: Optional[discord.Member] = None,
        listing_id: Optional[str] = None,
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        data, entries = _guild_entries(MIDDLEMAN_FILE, interaction.guild_id)
        entry = {
            "id": _next_id(entries, "M"),
            "requester_id": interaction.user.id,
            "partner_id": partner.id if partner else None,
            "listing_id": listing_id,
            "deal": deal,
            "status": "open",
            "middleman_id": None,
            "timestamp": _now_iso(),
        }
        entries.append(entry)
        save(MIDDLEMAN_FILE, data)

        embed = styled_embed(
            title=t("middleman_title", lang),
            description=t("middleman_desc", lang, id=entry["id"]),
            color=ROYAL_BLUE,
            lang=lang,
        )
        embed.add_field(name=t("middleman_field_requester", lang), value=interaction.user.mention)
        if partner:
            embed.add_field(name=t("middleman_field_partner", lang), value=partner.mention)
        if listing_id:
            embed.add_field(name=t("report_field_listing", lang), value=f"`{listing_id}`")
        embed.add_field(name=t("middleman_field_deal", lang), value=deal[:1000], inline=False)

        mention = _leadership_mention(interaction.guild)
        await interaction.response.send_message(
            content=mention or None,
            embed=embed,
            view=MiddlemanView(lang, entry["id"]),
        )



    # -------------------------------------------------- Admin Channels Setup
    @app_commands.command(name="set_shop_channel", description="⚙️ [إدارة] تحديد روم متجر بيع وشراء الحسابات")
    @app_commands.describe(channel="الروم المخصص لإعلانات بيع الحسابات")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_shop_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = load(SHOP_CHANNEL_KEY)
        data[str(interaction.guild_id)] = channel.id
        save(SHOP_CHANNEL_KEY, data)
        await interaction.response.send_message(f"✅ تم تعيين {channel.mention} كروم رسمي لمتجر الحسابات.", ephemeral=False)

    @app_commands.command(name="set_middleman_channel", description="⚙️ [إدارة] تحديد روم طلبات الوساطة والتواصل")
    @app_commands.describe(channel="الروم المخصص لطلبات الوساطة بين البائع والمشتري")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_middleman_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = load(MIDDLEMAN_CHANNEL_KEY)
        data[str(interaction.guild_id)] = channel.id
        save(MIDDLEMAN_CHANNEL_KEY, data)
        await interaction.response.send_message(f"✅ تم تعيين {channel.mention} كروم رسمي لطلبات الوسيط.", ephemeral=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(ShopCog(bot))
