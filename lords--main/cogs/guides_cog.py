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


# ---------------------------------------------------------------------------
# Monster Translations & Image Fallbacks
# ---------------------------------------------------------------------------

MONSTER_IMAGES = {
    "saberfang": "https://static.wikia.nocookie.net/lordsmobile/images/9/91/Saberfang.png",
    "frostwing": "https://static.wikia.nocookie.net/lordsmobile/images/d/da/Frostwing.png",
    "noceros": "https://static.wikia.nocookie.net/lordsmobile/images/c/c8/Noceros.png",
    "hell_drider": "https://static.wikia.nocookie.net/lordsmobile/images/f/fd/Hell_Drider.png",
    "gryphon": "https://static.wikia.nocookie.net/lordsmobile/images/2/2f/Gryphon.png",
    "blackwing": "https://static.wikia.nocookie.net/lordsmobile/images/c/ce/Blackwing.png",
    "mega_maggot": "https://static.wikia.nocookie.net/lordsmobile/images/5/55/Mega_Maggot.png",
    "bon_appeti": "https://static.wikia.nocookie.net/lordsmobile/images/b/bf/Bon_Appeti.png",
    "gargantua": "https://static.wikia.nocookie.net/lordsmobile/images/2/21/Gargantua.png",
    "grim_reaper": "https://static.wikia.nocookie.net/lordsmobile/images/7/74/Grim_Reaper.png",
    "hardrox": "https://static.wikia.nocookie.net/lordsmobile/images/d/d6/Hardrox.png",
    "hootclaw": "https://static.wikia.nocookie.net/lordsmobile/images/c/cb/Hootclaw.png",
    "jade_wyrm": "https://static.wikia.nocookie.net/lordsmobile/images/5/51/Jade_Wyrm.png",
    "mecha_trojan": "https://static.wikia.nocookie.net/lordsmobile/images/3/3a/Mecha_Trojan.png",
    "queen_bee": "https://static.wikia.nocookie.net/lordsmobile/images/f/f0/Queen_Bee.png",
    "snow_beast": "https://static.wikia.nocookie.net/lordsmobile/images/2/28/Snow_Beast.png",
    "terrorthorn": "https://static.wikia.nocookie.net/lordsmobile/images/6/6a/Terrorthorn.png",
    "tidal_titan": "https://static.wikia.nocookie.net/lordsmobile/images/c/c0/Tidal_Titan.png",
    "voodoo_shaman": "https://static.wikia.nocookie.net/lordsmobile/images/2/2e/Voodoo_Shaman.png",
    "cottontail": "https://static.wikia.nocookie.net/lordsmobile/images/0/07/Cottageroar.png",
    "cottageroar": "https://static.wikia.nocookie.net/lordsmobile/images/0/07/Cottageroar.png",
    "necrosis": "https://static.wikia.nocookie.net/lordsmobile/images/4/49/Undead_Ogre.png",
    "serpent_gladiator": "https://static.wikia.nocookie.net/lordsmobile/images/0/0b/Serpent_Vizier.png",
    "gorgon": "https://static.wikia.nocookie.net/lordsmobile/images/4/4e/Gorgon.png",
    "arctic_flipper": "https://static.wikia.nocookie.net/lordsmobile/images/c/c9/Arctic_Flipper.png",
    "cyclops": "https://static.wikia.nocookie.net/lordsmobile/images/2/23/Cyclops.png",
}

MONSTER_AR_TO_EN = {
    "سابرفنغ": "Saberfang", "سابرفانج": "Saberfang", "ذو الناب": "Saberfang",
    "تنين الثلج": "Frostwing", "جناح الصقيع": "Frostwing", "فروستونج": "Frostwing", "فروست وينج": "Frostwing", "فروست وينغ": "Frostwing",
    "نوسيروس": "Noceros", "الكركدن": "Noceros",
    "عنكبوت الجحيم": "Hell Drider", "هيل درايدر": "Hell Drider",
    "غريفون": "Gryphon", "الجريفون": "Gryphon",
    "الجناح الاسود": "Blackwing", "الجناح الأسود": "Blackwing", "تنين الظلام": "Blackwing", "العنقاء": "Blackwing",
    "اليرقة العملاقة": "Mega Maggot", "الدودة العملاقة": "Mega Maggot", "الدوده العملاقة": "Mega Maggot", "ميجا ماجوت": "Mega Maggot",
    "بون أبتيت": "Bon Appeti", "بون ابتيت": "Bon Appeti", "بون أبيتيت": "Bon Appeti", "بون ابيتيت": "Bon Appeti",
    "غارغانتوا": "Gargantua", "غوريلا": "Gargantua", "الغوريلا": "Gargantua",
    "حاصد الارواح": "Grim Reaper", "حاصد الأرواح": "Grim Reaper",
    "صلخر": "Hardrox", "هاردوكس": "Hardrox", "هارد روكس": "Hardrox",
    "مخلب البومة": "Hootclaw", "مخلب البومه": "Hootclaw",
    "تنين اليشم": "Jade Wyrm", "جايد ويرم": "Jade Wyrm",
    "طروادة الالي": "Mecha Trojan", "طروادة الآلي": "Mecha Trojan", "حصان طروادة": "Mecha Trojan",
    "ملكة النحل": "Queen Bee", "ملكه النحل": "Queen Bee",
    "وحش الثلج": "Snow Beast", "سنو بيست": "Snow Beast", "سنود بيست": "Snow Beast",
    "شوك الرعب": "Terrorthorn", "شوكة الرعب": "Terrorthorn",
    "عملاق المد": "Tidal Titan",
    "شامان الفودو": "Voodoo Shaman", "الكاهن فودو": "Voodoo Shaman", "كاهن فودو": "Voodoo Shaman", "ساحرة الشر": "Voodoo Shaman", "ساحره الشر": "Voodoo Shaman",
    "ذيل القطن": "Cottontail",
    "الكوخ المتوحش": "Cottageroar",
    "نخر": "Necrosis", "نيكروسيس": "Necrosis",
    "المصارع الثعبان": "Serpent Gladiator", "الثعبان المقاتل": "Serpent Gladiator",
    "جورجون": "Gorgon", "الأفعى جورجون": "Gorgon", "الافعى جورجون": "Gorgon",
    "زعنفة القطب": "Arctic Flipper", "زعنفه القطب": "Arctic Flipper",
    "العملاق الاعور": "Cyclops", "العملاق الأعور": "Cyclops", "عملاق اعور": "Cyclops", "عملاق أعور": "Cyclops",
}

def _normalize_name(text: str) -> str:
    t_str = str(text or "").strip()
    t_str = re.sub(r'[\u064B-\u065F\u0670]', '', t_str)
    t_str = t_str.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    t_str = t_str.replace('ة', 'ه').replace('ى', 'ي')
    return ' '.join(t_str.split()).lower()

_NORM_AR_TO_EN = {_normalize_name(k): v for k, v in MONSTER_AR_TO_EN.items()}
_NORM_EN_TO_AR = {_normalize_name(v): k for k, v in MONSTER_AR_TO_EN.items()}

def _resolve_monster_en(name: str) -> str:
    norm = _normalize_name(name)
    if norm in _NORM_AR_TO_EN:
        return _NORM_AR_TO_EN[norm]
    # Check lowercase match
    for k, v in MONSTER_AR_TO_EN.items():
        if k in name or name in k:
            return v
    return name

def _resolve_monster_ar(name: str) -> str:
    norm = _normalize_name(name)
    if norm in _NORM_EN_TO_AR:
        return _NORM_EN_TO_AR[norm]
    for k, v in MONSTER_AR_TO_EN.items():
        if v.lower() == norm or v.lower() in norm:
            return k
    return name

def _is_expired_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return True
    if "cdn.discordapp.com" in url or "media.discordapp.net" in url:
        m = re.search(r'[?&]ex=([0-9a-fA-F]+)', url)
        if m:
            try:
                import time
                exp_ts = int(m.group(1), 16)
                if time.time() >= exp_ts - 60:
                    return True
            except Exception:
                pass
    return False

def _get_monster_image(name: str, key: str = "") -> str:
    clean_key = key.lower().replace("-", "_").strip()
    if clean_key in MONSTER_IMAGES:
        return MONSTER_IMAGES[clean_key]
    en_name = _resolve_monster_en(name).lower().replace(" ", "_")
    if en_name in MONSTER_IMAGES:
        return MONSTER_IMAGES[en_name]
    for m_key, url in MONSTER_IMAGES.items():
        if m_key in clean_key or m_key in en_name:
            return url
    return ""

def _monster_name(entry: dict, key: str, lang: str) -> str:
    names = entry.get("name")
    target_lang = "en" if lang == "en" else "ar"
    
    if isinstance(names, dict):
        val = names.get(target_lang)
        if val:
            return str(val)
        other = names.get("ar" if target_lang == "en" else "en")
        if other and isinstance(other, str):
            return _resolve_monster_en(other) if target_lang == "en" else _resolve_monster_ar(other)
    
    val = entry.get(f"name_{target_lang}") or names
    if isinstance(val, str) and val.strip():
        val = val.strip()
        return _resolve_monster_en(val) if target_lang == "en" else _resolve_monster_ar(val)
        
    cleaned_key = key.replace("_", " ").title()
    if target_lang == "en":
        return _resolve_monster_en(cleaned_key)
    return _resolve_monster_ar(cleaned_key)


def _monster_text(value, lang: str) -> str:
    """Return the requested language, including bilingual lists of heroes."""
    if isinstance(value, dict):
        value = value.get(lang) or value.get("ar") or value.get("en") or ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")


class MonsterSelect(discord.ui.Select):
    def __init__(self, monster_data: dict, lang: str):
        self.monster_data = monster_data
        self.lang = lang
        options = [
            discord.SelectOption(
                label=_monster_name(value, key, lang)[:100],
                value=key,
                emoji="🐲"
            )
            for key, value in monster_data.items()
        ]
        super().__init__(placeholder=t("monster_select_placeholder", lang), options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        lang = self.lang
        key = self.values[0]
        info = self.monster_data.get(key, {})
        title = _monster_name(info, key, lang)
        embed = discord.Embed(
            title=f"🐲 {title}",
            color=discord.Color.dark_green()
        )
        embed.set_footer(text=t("monster_footer", lang))

        # 1. Check if a permanent locally saved image exists on the host
        gid = str(interaction.guild_id or 0)
        local_dir = os.path.join("storage", "monster_images")
        clean_key = re.sub(r'[^a-zA-Z0-9_]', '', key.lower().replace(" ", "_"))
        local_candidates = [
            os.path.join(local_dir, f"{gid}_{clean_key}.png"),
            os.path.join(local_dir, f"{clean_key}.png"),
        ]
        local_path = next((p for p in local_candidates if os.path.exists(p)), None)

        if local_path:
            filename = f"monster_{clean_key}.png"
            file = discord.File(local_path, filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            await interaction.response.send_message(embed=embed, file=file)
            return

        # 2. Check info image_url without expired Discord CDN links
        raw_url = info.get("image_url")
        if raw_url and not _is_expired_url(raw_url):
            image_url = raw_url
        else:
            image_url = _get_monster_image(title, key)

        if image_url:
            embed.set_image(url=image_url)

        await interaction.response.send_message(embed=embed)

class MonsterView(discord.ui.View):
    def __init__(self, monster_data: dict, lang: str):
        super().__init__(timeout=60)
        self.add_item(MonsterSelect(monster_data, lang))


class MonsterDeleteSelect(discord.ui.Select):
    def __init__(self, entries: dict, lang: str):
        self.entries = entries
        self.lang = lang
        options = [
            discord.SelectOption(
                label=_monster_name(value, key, lang)[:100],
                value=key,
                emoji=value.get("emoji") or "🐲"
            )
            for key, value in entries.items()
        ]
        super().__init__(
            placeholder=t("delete_monster_select_placeholder", lang),
            options=options[:25]
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_key = self.values[0]
        selected = self.entries[self.view.selected_key]
        name = _monster_name(selected, self.view.selected_key, self.lang)
        await interaction.response.send_message(
            t("delete_monster_selected", self.lang, name=name)
            
        )


class MonsterDeleteView(discord.ui.View):
    def __init__(self, entries: dict, lang: str):
        super().__init__(timeout=180)
        self.entries = entries
        self.lang = lang
        self.selected_key = None
        self.add_item(MonsterDeleteSelect(entries, lang))
        self.confirm.label = t("delete_monster_confirm", lang)

    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger, row=1)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_key:
            await interaction.response.send_message(
                t("delete_monster_selection_needed", self.lang)
                
            )
            return

        data = load(CUSTOM_MONSTERS_FILE)
        gid = str(interaction.guild_id)
        bucket = data.get(gid, {})
        removed = bucket.pop(self.selected_key, None)
        if removed is None:
            await interaction.response.send_message(
                t("delete_monster_not_found", self.lang, name=self.selected_key)
                
            )
            return
        if bucket:
            data[gid] = bucket
        else:
            data.pop(gid, None)
        save(CUSTOM_MONSTERS_FILE, data)

        for child in self.children:
            child.disabled = True
        removed_name = _monster_name(removed, self.selected_key, self.lang)
        await interaction.response.edit_message(
            content=t("delete_monster_success", self.lang, name=removed_name),
            embed=None,
            view=self
        )


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
    (("paragon", "قدوة الممالك", "حدث قدوة"), "Kingdom Paragon Event Guide", "Kingdom Paragon is a limited event where kingdoms compete through scheduled challenges and score opportunities. Check the event tasks before spending resources, coordinate with your guild, and save speed-ups, troops, or items for the stages that give the best return. Track the event timer and claim every available reward before it ends.")
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
                emoji=_info_emoji(category, "📚")
            )
            for key, category in self.categories.items()
        ]
        if custom_info:
            options.append(
                discord.SelectOption(
                    label=t("info_custom_category", lang),
                    value="__custom__",
                    emoji="📝"
                )
            )
        super().__init__(placeholder=t("info_select_placeholder", lang), options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        if selected == "__custom__":
            await interaction.response.edit_message(
                content=t("info_custom_prompt", self.lang),
                view=InfoItemView(self.custom_info, self.lang, self.categories.values(), self.custom_info)
            )
            return
        category = self.categories[selected]
        await interaction.response.edit_message(
            content=t(
                "info_category_prompt",
                self.lang,
                category=_localized(category.get("title"), self.lang)
            ),
            view=InfoItemView(category.get("items", []), self.lang, self.categories.values(), self.custom_info)
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
                emoji=_info_emoji(value, "📝")
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
            color=discord.Color.gold()
        )
        if info.get("image_url"):
            embed.set_image(url=info["image_url"])
        if info.get("image_url_2"):
            embed.add_field(name="\u200b", value=f"[🖼️]({info['image_url_2']})", inline=False)
        await interaction.response.send_message(embed=embed)


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
            view=InfoView(self.categories, self.custom_info, self.lang)
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
                emoji=_info_emoji(value)
            )
            for key, value in entries.items()
        ]
        super().__init__(placeholder=t("delete_info_select_placeholder", lang), options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_key = self.values[0]
        entry = self.view.entries[self.view.selected_key]
        title = _localized(entry.get("title", self.view.selected_key), self.lang)
        await interaction.response.send_message(t("delete_info_selected", self.lang, title=title))


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
            await interaction.response.send_message(t("delete_info_selection_needed", self.lang))
            return
        data = load(CUSTOM_INFO_FILE)
        gid = str(interaction.guild_id)
        bucket = data.get(gid, {})
        removed = bucket.pop(self.selected_key, None)
        if removed is None:
            await interaction.response.send_message(t("delete_info_not_found", self.lang, title=self.selected_key))
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
            view=self
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
                emoji=_info_emoji(value)
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
            max_length=100
        )
        self.title_en_input = discord.ui.TextInput(
            label=t("info_title_en_field", lang)[:45],
            default=_localized(entry.get("title", ""), "en")[:100],
            required=True,
            max_length=100
        )
        self.desc_ar_input = discord.ui.TextInput(
            label=t("info_desc_ar_field", lang)[:45],
            default=_localized(entry.get("desc", ""), "ar")[:4000],
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000
        )
        self.desc_en_input = discord.ui.TextInput(
            label=t("info_desc_en_field", lang)[:45],
            default=_localized(entry.get("desc", ""), "en")[:4000],
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000
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
            await interaction.response.send_message(t("delete_info_not_found", self.lang, title=self.key))
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
            t("edit_info_success", self.lang, title=saved_title)
            
        )

class GuidesCog(commands.Cog):
    """الأدلة والمصطلحات (وحوش وشروحات أحداث قابلة للإضافة من الإدارة)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dict_data = load_json_data("dict.json")
        self.static_info_data = load_json_data("info.json")
        self.static_monsters = load_json_data("monsters.json")

    def _get_monsters(self, guild_id: int) -> dict:
        """Show the bilingual standard list, plus monsters added by this server's admins."""
        custom_data = load(CUSTOM_MONSTERS_FILE)
        monsters = {
            key: value for key, value in self.static_monsters.items()
            if not key.startswith("_") and isinstance(value, dict)
        }
        monsters.update(custom_data.get(str(guild_id), {}))
        return monsters

    def _get_info(self, guild_id: int) -> dict:
        """يرجع الأقسام الجاهزة وإضافات الإدارة بصيغة ثنائية اللغة."""
        data = load(CUSTOM_INFO_FILE)
        custom = _prepare_custom_info(data.get(str(guild_id), {}))
        return {
            "categories": self.static_info_data.get("categories", []),
            "custom": custom,
        }

    # -- /monster + /add_monster ----------------------------------------

    @app_commands.command(name="monster", description="🐲 اختر اللغة واعرف أفضل أبطال الصيد | Choose language and find the best hunt heroes")
    @app_commands.describe(language="اختر لغة الرد | Choose response language")
    @app_commands.choices(language=[
        app_commands.Choice(name="العربية", value="ar"),
        app_commands.Choice(name="English", value="en"),
    ])
    async def monster(self, interaction: discord.Interaction, language: app_commands.Choice[str]):
        # Language is deliberately selected per request, not inherited from server settings.
        lang = language.value
        monsters = self._get_monsters(interaction.guild_id)
        if not monsters:
            await interaction.response.send_message(t("monster_empty", lang))
            return
        await interaction.response.send_message(
            t("monster_prompt", lang), view=MonsterView(monsters, lang)
        )

    @app_commands.command(
        name="add_monster",
        description="🐲 [إدارة/Admin] أضف وحشًا ببيانات عربية وإنجليزية | Add a bilingual monster"
    )
    @app_commands.describe(
        name_ar="اسم الوحش بالعربي | Arabic monster name",
        name_en="اسم الوحش بالإنجليزي | English monster name",
        image="صورة الوحش | Monster image",
        damage_ar="نوع الضرر بالعربي (اختياري) | Damage type in Arabic (optional)",
        damage_en="نوع الضرر بالإنجليزي (اختياري) | Damage type in English (optional)",
        heroes_ar="الأبطال المقترحون بالعربي، افصل بينهم بفاصلة | Suggested heroes in Arabic, comma-separated",
        heroes_en="الأبطال المقترحون بالإنجليزي، افصل بينهم بفاصلة | Suggested heroes in English, comma-separated",
        note_ar="ملاحظة الدفاع بالعربي (اختياري) | Arabic defense note (optional)",
        note_en="ملاحظة الدفاع بالإنجليزي (اختياري) | English defense note (optional)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_monster(
        self,
        interaction: discord.Interaction,
        name_ar: str,
        name_en: str,
        image: discord.Attachment,
        damage_ar: Optional[str] = None,
        damage_en: Optional[str] = None,
        heroes_ar: Optional[str] = None,
        heroes_en: Optional[str] = None,
        note_ar: Optional[str] = None,
        note_en: Optional[str] = None
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if not (image.content_type or "").startswith("image/"):
            await interaction.response.send_message(t("add_monster_bad_image", lang))
            return

        name_ar = name_ar.strip()
        name_en = name_en.strip()
        if not name_ar or not name_en:
            await interaction.response.send_message(t("add_monster_names_required", lang))
            return

        data = load(CUSTOM_MONSTERS_FILE)
        gid = str(interaction.guild_id)
        data.setdefault(gid, {})
        key = name_en.lower().replace(" ", "_")
        # Save image locally so it NEVER expires after 24h
        local_dir = os.path.join("storage", "monster_images")
        os.makedirs(local_dir, exist_ok=True)
        clean_key = re.sub(r'[^a-zA-Z0-9_]', '', key)
        local_filename = f"{gid}_{clean_key}.png"
        local_path = os.path.join(local_dir, local_filename)
        saved_local = False
        try:
            await image.save(local_path)
            saved_local = True
        except Exception:
            pass

        entry = {
            "name": {"ar": name_ar, "en": name_en},
            "emoji": "🐲",
            "image_url": image.url,
            "local_image": local_filename if saved_local else None,
        }
        if damage_ar or damage_en:
            entry["damage_type"] = {"ar": (damage_ar or damage_en or "").strip(), "en": (damage_en or damage_ar or "").strip()}
        if heroes_ar or heroes_en:
            entry["heroes"] = {
                "ar": [item.strip() for item in (heroes_ar or heroes_en or "").split(",") if item.strip()],
                "en": [item.strip() for item in (heroes_en or heroes_ar or "").split(",") if item.strip()],
            }
        if note_ar or note_en:
            entry["defense_note"] = {"ar": (note_ar or note_en or "").strip(), "en": (note_en or note_ar or "").strip()}
        data[gid][key] = entry
        save(CUSTOM_MONSTERS_FILE, data)

        shown_name = name_en if lang == "en" else name_ar
        await interaction.response.send_message(t("add_monster_success", lang, name=shown_name), ephemeral=True)

    @add_monster.error
    async def add_monster_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("add_monster_admin_only", lang), ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)

    @app_commands.command(name="delete_monster", description="🗑️ [إدارة/Admin] اختر وحشًا لحذفه من قائمة /monster")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete_monster(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        custom = self._get_monsters(interaction.guild_id)
        if not custom:
            await interaction.response.send_message(t("delete_monster_empty", lang))
            return
        await interaction.response.send_message(
            t("delete_monster_prompt", lang),
            view=MonsterDeleteView(custom, lang),
            ephemeral=True
        )

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
                    t("dict_not_found_suggest", lang, term=term, suggestions=", ".join(close[:5]))
                    
                )
            else:
                await interaction.response.send_message(t("dict_not_found", lang, term=term))
            return
        embed = discord.Embed(title=f"📖 {term.upper()}", description=match, color=discord.Color.light_grey())
        await interaction.response.send_message(embed=embed)

    @dict_cmd.autocomplete("term")
    async def dict_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        matches = [k for k in self.dict_data.keys() if current in k.lower()]
        return [app_commands.Choice(name=k, value=k) for k in matches[:25]]

    # -- /info + /add_info --------------------------------------------------

    @app_commands.command(
        name="info",
        description="ℹ️ شرح الأدلة والفعاليات | Lords guides and events"
    )
    async def info(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        info_data = self._get_info(interaction.guild_id)
        if not info_data["categories"] and not info_data["custom"]:
            await interaction.response.send_message(t("info_empty", lang))
            return
        await interaction.response.send_message(
            t("info_prompt", lang),
            view=InfoView(info_data["categories"], info_data["custom"], lang)
        )

    @app_commands.command(
        name="add_info",
        description="ℹ️ [إدارة/Admin] أضف شرحًا ثنائي اللغة | Add a bilingual Lords guide"
    )
    @app_commands.describe(
        title="عنوان الشرح بالعربي | Arabic guide title",
        desc="نص الشرح بالعربي | Arabic guide text",
        title_en="عنوان الشرح بالإنجليزي | English guide title",
        desc_en="نص الشرح بالإنجليزي | English guide text",
        image="صورة اختيارية | Optional reference image",
        image2="صورة ثانية اختيارية | Optional second image"
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
        image2: Optional[discord.Attachment] = None
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        for att in (image, image2):
            if att and not (att.content_type or "").startswith("image/"):
                await interaction.response.send_message(t("add_info_bad_image", lang))
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
            await interaction.response.send_message(t("edit_info_empty", lang))
            return
        await interaction.response.send_message(
            t("delete_info_prompt", lang),
            view=InfoDeleteView(custom, lang),
            ephemeral=True
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
        image2="صورة ثانية جديدة اختيارية | Optional second replacement image"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def edit_info(
        self,
        interaction: discord.Interaction,
        image: Optional[discord.Attachment] = None,
        image2: Optional[discord.Attachment] = None
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        for att in (image, image2):
            if att and not (att.content_type or "").lower().startswith("image/"):
                await interaction.response.send_message(t("add_info_bad_image", lang))
                return

        custom = load(CUSTOM_INFO_FILE).get(str(interaction.guild_id), {})
        if not custom:
            await interaction.response.send_message(t("edit_info_empty", lang))
            return
        await interaction.response.send_message(
            t("edit_info_prompt", lang),
            view=InfoEditView(custom, lang, image, image2),
            ephemeral=True
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
