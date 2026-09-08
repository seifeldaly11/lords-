"""
/monster    — قائمة منسدلة بالوحوش المضافة (تبدأ فاضية، الإدارة تضيفها بـ /add_monster).
/add_monster — (إدارة) يضيف وحش جديد: اسمه، نوع الضرر المطلوب، الأبطال المقترحين،
                وملاحظة دفاع اختيارية، مع إمكانية إرفاق صورة أو صورتين للوحش/التشكيلة.
/dict       — قاموس مصطلحات اللعبة السريع (ثابت من data/dict.json).
/info       — قائمة منسدلة بشرح الأحداث. بتجمع بين شروحات جاهزة (data/info.json)
               وشروحات أضافتها الإدارة بـ /add_info (ممكن تتضمن صورة أو صورتين).
/add_info   — (إدارة) يضيف شرح جديد: عنوان + نص، مع إمكانية إرفاق صورة أو صورتين.

بيانات /monster و/info المضافة يدوياً بتتخزن في storage (custom_monsters / custom_info)
منفصلة تماماً عن البيانات الجاهزة في data/*.json، فمفيش خطر إنها تتمسح لو حدّثنا الكود.
"""
from typing import Optional

import re

import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang, t
from utils.storage import load, save, load_json_data

CUSTOM_MONSTERS_FILE = "custom_monsters"
CUSTOM_INFO_FILE = "custom_info"


# ---------------------------------------------------------------------------
# /monster (ديناميكي بالكامل - يبدأ فاضي)
# ---------------------------------------------------------------------------

class MonsterSelect(discord.ui.Select):
    def __init__(self, monster_data: dict, lang: str):
        self.monster_data = monster_data
        self.lang = lang
        options = [
            discord.SelectOption(label=val.get("name", key), value=key, emoji=val.get("emoji") or "🐾")
            for key, val in monster_data.items()
        ]
        super().__init__(placeholder=t("monster_select_placeholder", lang), options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        lang = self.lang
        info = self.monster_data[self.values[0]]
        embed = discord.Embed(
            title=f"{info.get('emoji') or '🐾'} {info.get('name', self.values[0])}",
            color=discord.Color.dark_green(),
        )
        if info.get("image_url"):
            embed.set_image(url=info["image_url"])
        embed.set_footer(text=t("monster_footer", lang))
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MonsterView(discord.ui.View):
    def __init__(self, monster_data: dict, lang: str):
        super().__init__(timeout=60)
        self.add_item(MonsterSelect(monster_data, lang))


# ---------------------------------------------------------------------------
# /info (يجمع بين info.json الجاهز + الإضافات اليدوية اللي ممكن تتضمن صور)
# ---------------------------------------------------------------------------

INFO_CUSTOM_FALLBACK_EMOJI = "📝"


def _localized(value, lang: str) -> str:
    if isinstance(value, dict):
        return value.get(lang) or value.get("ar") or value.get("en") or ""
    return value or ""


LEGACY_INFO_TRANSLATIONS = (
    (("academy", "الأبحاث"), "Academy Research", "Start with research that improves construction, research speed, resource production, and troop development. Prioritize military research before major war activities, then complete the branches that unlock stronger formations and higher troop tiers. Plan your resources, tomes, and speed-ups before starting long research so your Academy keeps progressing without wasted time."),
    (("black nest", "dark nest", "العش الأسود", "عش اسود"), "What Is a Dark Nest?", "A Dark Nest is a rally target that requires scouting, the right formation, and coordinated timing. Check the nest level, enemy troop type, and recommended counter before sending a march. Choose the rally leader and participating heroes carefully, send the required army size, and share the report with the guild so future rallies can be adjusted. Rewards depend on the nest level and the rally result."),
    (("mix", "ميكس"), "Best Mix Hero Lineups", "A mix formation combines infantry, ranged, and cavalry so your defense can absorb different attack types. Use heroes that strengthen the troop type you have the most of, keep your frontline durable, and adjust the wedge or phalanx to the enemy composition. The best lineup depends on your gear, familiars, troop ratios, and whether you are defending or joining a rally."),
    (("archaic", "المجلدات العتيقة", "المجلدات"), "How to Get Archaic Tomes", "Collect Archaic Tomes from events, guild activities, reward chests, and other limited-time sources. Save them for research branches that unlock major account milestones instead of spending them on low-priority upgrades. Check event rewards and guild tasks regularly so you do not miss a limited source of tomes."),
    (("prison", "السجن"), "Prison, Altar & Battle Hall for T4", "Unlocking T4 troops requires the Prison, Altar, and Battle Hall to reach their required levels, along with the matching Academy research and castle progression. Upgrade these buildings in the correct order, prepare the required resources and materials, and keep enough speed-ups available for the final upgrades. Once the building and research requirements are complete, the T4 troop research can be started."),
    (("infantry", "مشاة"), "Best Infantry Hero Lineups", "Infantry lineups are built around a strong frontline that can hold against sustained damage. Choose infantry attack and defense heroes, add support heroes that improve survivability, and match the lineup to your gear and familiars. Use infantry formations when the enemy is weak to your frontline pressure, and change the formation after scouting the opponent."),
    (("ranged", "الرماة", "رماة"), "Best Ranged Hero Lineups", "Ranged lineups focus on dealing damage from the back while the frontline protects the march. Select ranged attack heroes, add defensive support where needed, and use a formation that keeps ranged troops safe from the enemy counter. Your final choice should follow your strongest gear, familiars, troop ratio, and rally role."),
    (("cavalry", "الفرسان", "فرسان"), "Best Cavalry Hero Lineups", "Cavalry lineups are designed for fast, high-impact attacks and cavalry rallies. Pick cavalry attack heroes with suitable support heroes, then choose the wedge or phalanx that matches the target. Check the enemy report before committing, because the best cavalry lineup changes with the target formation, gear quality, and troop balance."),
    (("familiar", "الوحوش", "المهارة"), "Best Familiars by Skills", "Choose familiars by the skill that supports your current goal: troop training, research, construction, gathering, monster hunting, or war. Prioritize skills that affect your daily bottleneck, level the familiars consistently, and avoid investing all resources into a familiar whose skill does not match your account plan."),
    (("pact 3", "لفيفة 3", "اللفيفة 3"), "Pact 3 Familiars Guide", "Pact 3 familiars can provide useful boosts for growth, training, gathering, and early war preparation. Compare each familiar by its active and passive skills, focus on the bonuses your account uses most, and spend merging and leveling materials gradually instead of spreading them across every option."),
    (("paragon", "قدوة الممالك", "حدث قدوة"), "Kingdom Paragon Event Guide", "Kingdom Paragon is a limited event where kingdoms compete through scheduled challenges and score opportunities. Check the event tasks before spending resources, coordinate with your guild, and save speed-ups, troops, or items for the stages that give the best return. Track the event timer and claim every available reward before it ends."),
)


def _clean_legacy_arabic(value) -> str:
    if not isinstance(value, str):
        return value or ""
    return re.sub(r"\\s*\\([^()]*[A-Za-z][^()]*\\)", "", value).strip()


def _extract_legacy_english(value) -> str:
    if not isinstance(value, str):
        return ""
    parts = re.findall(r"\\(([^)]*[A-Za-z][^)]*)\\)", value)
    return " ".join(part.strip() for part in parts if part.strip())


def _legacy_translation(entry_key: str, title: str, desc: str):
    haystack = f"{entry_key} {title} {desc}".casefold()
    for terms, title_en, desc_en in LEGACY_INFO_TRANSLATIONS:
        if any(term.casefold() in haystack for term in terms):
            return title_en, desc_en
    return "", ""


def _prepare_custom_info(entries: dict) -> dict:
    """يحوّل الشروحات القديمة ذات النص الواحد إلى صيغة ar/en وقت العرض."""
    prepared = {}
    for key, raw_entry in entries.items():
        entry = dict(raw_entry)
        raw_title = entry.get("title", key)
        raw_desc = entry.get("desc", "")
        if isinstance(raw_title, dict):
            title_ar = raw_title.get("ar") or raw_title.get("en") or key
            title_en = raw_title.get("en") or raw_title.get("ar") or key
        else:
            title_ar = _clean_legacy_arabic(raw_title)
            title_en = _extract_legacy_english(raw_title)
        if isinstance(raw_desc, dict):
            desc_ar = raw_desc.get("ar") or raw_desc.get("en") or ""
            desc_en = raw_desc.get("en") or raw_desc.get("ar") or ""
        else:
            desc_ar = _clean_legacy_arabic(raw_desc)
            desc_en = _extract_legacy_english(raw_desc)

        translated_title, translated_desc = _legacy_translation(key, title_ar, desc_ar)
        if translated_title:
            title_en = translated_title
        if translated_desc:
            desc_en = translated_desc
        if not title_en:
            title_en = f"Lords Guide: {str(key).replace('_', ' ').title()}"
        if not desc_en:
            desc_en = "English translation not added yet. Use /edit_info to add the English title and description."

        entry["title"] = {"ar": title_ar, "en": title_en}
        entry["desc"] = {"ar": desc_ar, "en": desc_en}
        prepared[key] = entry
    return prepared


def _info_emoji(value: dict, fallback: str = INFO_CUSTOM_FALLBACK_EMOJI) -> str:
    emoji = value.get("emoji")
    return fallback if not emoji or emoji in {"👑", "ℹ️", "ℹ"} else emoji


class InfoCategorySelect(discord.ui.Select):
    def __init__(self, categories: list[dict], custom_info: dict, lang: str):
        self.categories = {str(category["key"]): category for category in categories}
        self.custom_info = custom_info
        self.lang = lang
        options = [
            discord.SelectOption(
                label=_localized(category.get("title"), lang)[:100],
                value=key,
                emoji=_info_emoji(category, "📚"),
            )
            for key, category in self.categories.items()
        ]
        if custom_info:
            options.append(
                discord.SelectOption(
                    label=t("info_custom_category", lang),
                    value="__custom__",
                    emoji="📝",
                )
            )
        super().__init__(placeholder=t("info_select_placeholder", lang), options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        if selected == "__custom__":
            await interaction.response.edit_message(
                content=t("info_custom_prompt", self.lang),
                view=InfoItemView(self.custom_info, self.lang, self.categories.values(), self.custom_info),
            )
            return
        category = self.categories[selected]
        await interaction.response.edit_message(
            content=t(
                "info_category_prompt",
                self.lang,
                category=_localized(category.get("title"), self.lang),
            ),
            view=InfoItemView(category.get("items", []), self.lang, self.categories.values(), self.custom_info),
        )


class InfoItemSelect(discord.ui.Select):
    def __init__(self, items, lang: str):
        self.lang = lang
        if isinstance(items, dict):
            item_pairs = list(items.items())
            self.items = {key: value for key, value in item_pairs}
        else:
            self.items = {str(item.get("key", index)): item for index, item in enumerate(items)}
        options = [
            discord.SelectOption(
                label=_localized(value.get("title", key), lang)[:100],
                value=key,
                emoji=_info_emoji(value, "📝"),
            )
            for key, value in self.items.items()
        ]
        super().__init__(placeholder=t("info_item_select_placeholder", lang), options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        info = self.items[self.values[0]]
        title = _localized(info.get("title", self.values[0]), self.lang)
        description = _localized(info.get("desc", ""), self.lang)
        embed = discord.Embed(
            title=f"{_info_emoji(info, '📝')} {title}",
            description=description,
            color=discord.Color.gold(),
        )
        if info.get("image_url"):
            embed.set_image(url=info["image_url"])
        if info.get("image_url_2"):
            embed.add_field(name="\u200b", value=f"[🖼️]({info['image_url_2']})", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class InfoView(discord.ui.View):
    def __init__(self, categories: list[dict], custom_info: dict, lang: str):
        super().__init__(timeout=180)
        self.add_item(InfoCategorySelect(list(categories), custom_info, lang))


class InfoItemView(discord.ui.View):
    def __init__(self, items, lang: str, categories, custom_info: dict):
        super().__init__(timeout=180)
        self.lang = lang
        self.categories = list(categories)
        self.custom_info = custom_info
        self.add_item(InfoItemSelect(items, lang))

    @discord.ui.button(label="↩️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=t("info_prompt", self.lang),
            view=InfoView(self.categories, self.custom_info, self.lang),
        )


# ---------------------------------------------------------------------------
# الـ Cog
# ---------------------------------------------------------------------------

class InfoDeleteSelect(discord.ui.Select):
    def __init__(self, entries: dict, lang: str):
        self.lang = lang
        options = [
            discord.SelectOption(
                label=_localized(value.get("title", key), lang)[:100],
                value=key,
                emoji=_info_emoji(value),
            )
            for key, value in entries.items()
        ]
        super().__init__(placeholder=t("delete_info_select_placeholder", lang), options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_key = self.values[0]
        entry = self.view.entries[self.view.selected_key]
        title = _localized(entry.get("title", self.view.selected_key), self.lang)
        await interaction.response.send_message(t("delete_info_selected", self.lang, title=title), ephemeral=True)


class InfoDeleteView(discord.ui.View):
    def __init__(self, entries: dict, lang: str):
        super().__init__(timeout=180)
        self.entries = entries
        self.lang = lang
        self.selected_key = None
        self.add_item(InfoDeleteSelect(entries, lang))
        self.confirm.label = t("delete_info_confirm", lang)

    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger, row=1)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_key:
            await interaction.response.send_message(t("delete_info_selection_needed", self.lang), ephemeral=True)
            return
        data = load(CUSTOM_INFO_FILE)
        gid = str(interaction.guild_id)
        bucket = data.get(gid, {})
        removed = bucket.pop(self.selected_key, None)
        if removed is None:
            await interaction.response.send_message(t("delete_info_not_found", self.lang, title=self.selected_key), ephemeral=True)
            return
        if bucket:
            data[gid] = bucket
        else:
            data.pop(gid, None)
        save(CUSTOM_INFO_FILE, data)
        for child in self.children:
            child.disabled = True
        removed_title = _localized(removed.get("title", self.selected_key), self.lang)
        await interaction.response.edit_message(
            content=t("delete_info_success", self.lang, title=removed_title),
            embed=None,
            view=self,
        )


class InfoEditSelect(discord.ui.Select):
    def __init__(self, entries: dict, lang: str, image: Optional[discord.Attachment], image2: Optional[discord.Attachment]):
        self.entries = entries
        self.lang = lang
        self.image = image
        self.image2 = image2
        options = [
            discord.SelectOption(
                label=_localized(value.get("title", key), lang)[:100],
                value=key,
                emoji=_info_emoji(value),
            )
            for key, value in entries.items()
        ]
        super().__init__(placeholder=t("edit_info_select_placeholder", lang), options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        await interaction.response.send_modal(
            InfoEditModal(key, self.entries[key], self.lang, self.image, self.image2)
        )


class InfoEditView(discord.ui.View):
    def __init__(self, entries: dict, lang: str, image: Optional[discord.Attachment], image2: Optional[discord.Attachment]):
        super().__init__(timeout=180)
        self.add_item(InfoEditSelect(entries, lang, image, image2))


class InfoEditModal(discord.ui.Modal):
    def __init__(self, key: str, entry: dict, lang: str, image: Optional[discord.Attachment], image2: Optional[discord.Attachment]):
        super().__init__(title=t("edit_info_modal_title", lang))
        self.key = key
        self.entry = entry
        self.lang = lang
        self.image = image
        self.image2 = image2
        self.title_ar_input = discord.ui.TextInput(
            label=t("info_title_ar_field", lang)[:45],
            default=_localized(entry.get("title", ""), "ar")[:100],
            required=True,
            max_length=100,
        )
        self.title_en_input = discord.ui.TextInput(
            label=t("info_title_en_field", lang)[:45],
            default=_localized(entry.get("title", ""), "en")[:100],
            required=True,
            max_length=100,
        )
        self.desc_ar_input = discord.ui.TextInput(
            label=t("info_desc_ar_field", lang)[:45],
            default=_localized(entry.get("desc", ""), "ar")[:4000],
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000,
        )
        self.desc_en_input = discord.ui.TextInput(
            label=t("info_desc_en_field", lang)[:45],
            default=_localized(entry.get("desc", ""), "en")[:4000],
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000,
        )
        self.add_item(self.title_ar_input)
        self.add_item(self.title_en_input)
        self.add_item(self.desc_ar_input)
        self.add_item(self.desc_en_input)

    async def on_submit(self, interaction: discord.Interaction):
        data = load(CUSTOM_INFO_FILE)
        gid = str(interaction.guild_id)
        bucket = data.get(gid, {})
        entry = bucket.get(self.key)
        if entry is None:
            await interaction.response.send_message(t("delete_info_not_found", self.lang, title=self.key), ephemeral=True)
            return
        entry["title"] = {
            "ar": self.title_ar_input.value.strip(),
            "en": self.title_en_input.value.strip(),
        }
        entry["desc"] = {
            "ar": self.desc_ar_input.value.strip(),
            "en": self.desc_en_input.value.strip(),
        }
        if self.image:
            entry["image_url"] = self.image.url
        if self.image2:
            entry["image_url_2"] = self.image2.url
        save(CUSTOM_INFO_FILE, data)
        saved_title = _localized(entry["title"], self.lang)
        await interaction.response.send_message(
            t("edit_info_success", self.lang, title=saved_title),
            ephemeral=True,
        )

class GuidesCog(commands.Cog):
    """الأدلة والمصطلحات (وحوش وشروحات أحداث قابلة للإضافة من الإدارة)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dict_data = load_json_data("dict.json")
        self.static_info_data = load_json_data("info.json")

    def _get_monsters(self, guild_id: int) -> dict:
        data = load(CUSTOM_MONSTERS_FILE)
        return data.get(str(guild_id), {})

    def _get_info(self, guild_id: int) -> dict:
        """يرجع الأقسام الجاهزة وإضافات الإدارة بصيغة ثنائية اللغة."""
        data = load(CUSTOM_INFO_FILE)
        custom = _prepare_custom_info(data.get(str(guild_id), {}))
        return {
            "categories": self.static_info_data.get("categories", []),
            "custom": custom,
        }

    # -- /monster + /add_monster ----------------------------------------

    @app_commands.command(name="monster", description="🐾 أفضل أبطال الصيد حسب اسم الوحش")
    async def monster(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        monsters = self._get_monsters(interaction.guild_id)
        if not monsters:
            await interaction.response.send_message(t("monster_empty", lang), ephemeral=True)
            return
        await interaction.response.send_message(
            t("monster_prompt", lang), view=MonsterView(monsters, lang), ephemeral=True
        )

    @app_commands.command(
        name="add_monster",
        description="🐾 [إدارة/Admin] أضف وحشًا بالاسم والصورة | Add a monster with its name and image",
    )
    @app_commands.describe(
        name="اسم الوحش | Monster name",
        image="صورة الوحش | Monster image",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_monster(
        self,
        interaction: discord.Interaction,
        name: str,
        image: discord.Attachment,
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if not (image.content_type or "").startswith("image/"):
            await interaction.response.send_message(t("add_monster_bad_image", lang), ephemeral=True)
            return

        data = load(CUSTOM_MONSTERS_FILE)
        gid = str(interaction.guild_id)
        data.setdefault(gid, {})
        key = name.strip().lower().replace(" ", "_")
        entry = {
            "name": name.strip(),
            "emoji": "🐾",
            "image_url": image.url,
        }
        data[gid][key] = entry
        save(CUSTOM_MONSTERS_FILE, data)

        await interaction.response.send_message(t("add_monster_success", lang, name=name.strip()), ephemeral=True)

    @add_monster.error
    async def add_monster_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("add_monster_admin_only", lang), ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)

    @app_commands.command(name="delete_monster", description="🗑️ [إدارة] احذف وحشًا مضافًا من قائمة /monster")
    @app_commands.describe(name="Monster name or key to delete")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete_monster(self, interaction: discord.Interaction, name: str):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        data = load(CUSTOM_MONSTERS_FILE)
        gid = str(interaction.guild_id)
        bucket = data.get(gid, {})
        normalized = name.strip().lower().replace(" ", "_")
        key = next((k for k, value in bucket.items() if k == normalized or value.get("name", "").strip().lower() == name.strip().lower()), None)
        if key is None:
            await interaction.response.send_message(t("delete_monster_not_found", lang, name=name), ephemeral=True)
            return
        removed = bucket.pop(key)
        if bucket:
            data[gid] = bucket
        else:
            data.pop(gid, None)
        save(CUSTOM_MONSTERS_FILE, data)
        await interaction.response.send_message(t("delete_monster_success", lang, name=removed.get("name", name)), ephemeral=True)

    @delete_monster.error
    async def delete_monster_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("add_monster_admin_only", lang), ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)

    # -- /dict -------------------------------------------------------------

    @app_commands.command(name="dict", description="📖 قاموس مصطلحات اللعبة السريع")
    @app_commands.describe(term="Enter a term (T4, Rally, RSS...) and choose a suggestion")
    async def dict_cmd(self, interaction: discord.Interaction, term: str):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        match = next((v for k, v in self.dict_data.items() if k.lower() == term.lower()), None)
        if not match:
            close = [k for k in self.dict_data if term.lower() in k.lower()]
            if close:
                await interaction.response.send_message(
                    t("dict_not_found_suggest", lang, term=term, suggestions=", ".join(close[:5])),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(t("dict_not_found", lang, term=term), ephemeral=True)
            return
        embed = discord.Embed(title=f"📖 {term.upper()}", description=match, color=discord.Color.light_grey())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @dict_cmd.autocomplete("term")
    async def dict_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        matches = [k for k in self.dict_data.keys() if current in k.lower()]
        return [app_commands.Choice(name=k, value=k) for k in matches[:25]]

    # -- /info + /add_info --------------------------------------------------

    @app_commands.command(
        name="info",
        description="ℹ️ شرح الأدلة والفعاليات | Lords guides and events",
    )
    async def info(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        info_data = self._get_info(interaction.guild_id)
        if not info_data["categories"] and not info_data["custom"]:
            await interaction.response.send_message(t("info_empty", lang), ephemeral=True)
            return
        await interaction.response.send_message(
            t("info_prompt", lang),
            view=InfoView(info_data["categories"], info_data["custom"], lang),
            ephemeral=True,
        )

    @app_commands.command(
        name="add_info",
        description="ℹ️ [إدارة/Admin] أضف شرحًا ثنائي اللغة | Add a bilingual Lords guide",
    )
    @app_commands.describe(
        title="عنوان الشرح بالعربي | Arabic guide title",
        desc="نص الشرح بالعربي | Arabic guide text",
        title_en="عنوان الشرح بالإنجليزي | English guide title",
        desc_en="نص الشرح بالإنجليزي | English guide text",
        image="صورة اختيارية | Optional reference image",
        image2="صورة ثانية اختيارية | Optional second image",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_info(
        self,
        interaction: discord.Interaction,
        title: str,
        desc: str,
        title_en: str,
        desc_en: str,
        image: Optional[discord.Attachment] = None,
        image2: Optional[discord.Attachment] = None,
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        for att in (image, image2):
            if att and not (att.content_type or "").startswith("image/"):
                await interaction.response.send_message(t("add_info_bad_image", lang), ephemeral=True)
                return

        data = load(CUSTOM_INFO_FILE)
        gid = str(interaction.guild_id)
        data.setdefault(gid, {})
        key = title.strip().lower().replace(" ", "_")
        entry = {
            "title": {"ar": title.strip(), "en": title_en.strip()},
            "desc": {"ar": desc.strip(), "en": desc_en.strip()},
            "emoji": INFO_CUSTOM_FALLBACK_EMOJI,
        }
        if image:
            entry["image_url"] = image.url
        if image2:
            entry["image_url_2"] = image2.url
        data[gid][key] = entry
        save(CUSTOM_INFO_FILE, data)

        shown_title = title_en.strip() if lang == "en" else title.strip()
        await interaction.response.send_message(t("add_info_success", lang, title=shown_title), ephemeral=True)

    @add_info.error
    async def add_info_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("add_info_admin_only", lang), ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)

    @app_commands.command(name="delete_info", description="🗑️ [إدارة/Admin] احذف شرحًا | Delete a Lords guide")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete_info(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        custom = load(CUSTOM_INFO_FILE).get(str(interaction.guild_id), {})
        if not custom:
            await interaction.response.send_message(t("edit_info_empty", lang), ephemeral=True)
            return
        await interaction.response.send_message(
            t("delete_info_prompt", lang),
            view=InfoDeleteView(custom, lang),
            ephemeral=True,
        )

    @delete_info.error
    async def delete_info_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("add_info_admin_only", lang), ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)

    @app_commands.command(name="edit_info", description="✏️ [إدارة/Admin] عدّل شرحًا ثنائي اللغة | Edit a bilingual Lords guide")
    @app_commands.describe(
        image="صورة جديدة اختيارية | Optional replacement image",
        image2="صورة ثانية جديدة اختيارية | Optional second replacement image",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def edit_info(
        self,
        interaction: discord.Interaction,
        image: Optional[discord.Attachment] = None,
        image2: Optional[discord.Attachment] = None,
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        for att in (image, image2):
            if att and not (att.content_type or "").lower().startswith("image/"):
                await interaction.response.send_message(t("add_info_bad_image", lang), ephemeral=True)
                return

        custom = load(CUSTOM_INFO_FILE).get(str(interaction.guild_id), {})
        if not custom:
            await interaction.response.send_message(t("edit_info_empty", lang), ephemeral=True)
            return
        await interaction.response.send_message(
            t("edit_info_prompt", lang),
            view=InfoEditView(custom, lang, image, image2),
            ephemeral=True,
        )

    @edit_info.error
    async def edit_info_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("add_info_admin_only", lang), ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(GuidesCog(bot))
