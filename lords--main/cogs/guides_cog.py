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
        embed.add_field(name=t("monster_damage_field", lang), value=info.get("damage_type", "-"), inline=False)
        if info.get("defense_note"):
            embed.add_field(name=t("monster_defense_field", lang), value=info["defense_note"], inline=False)
        if info.get("heroes"):
            embed.add_field(name=t("monster_heroes_field", lang), value=info["heroes"], inline=False)
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

INFO_DEFAULT_EMOJI = "👑"

def _info_emoji(value: dict) -> str:
    """يعطي الأيقونات القديمة ℹ️ مظهرًا ذهبيًا موحدًا."""
    emoji = value.get("emoji")
    return INFO_DEFAULT_EMOJI if not emoji or emoji in {"ℹ️", "ℹ"} else emoji


class InfoSelect(discord.ui.Select):
    def __init__(self, info_data: dict, lang: str):
        self.info_data = info_data
        options = [
            discord.SelectOption(label=val["title"], value=key, emoji=_info_emoji(val))
            for key, val in info_data.items()
        ]
        super().__init__(placeholder=t("info_select_placeholder", lang), options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        info = self.info_data[self.values[0]]
        embed = discord.Embed(
            title=f"{_info_emoji(info)} {info['title']}",
            description=info.get("desc", ""),
            color=discord.Color.gold(),
        )
        if info.get("image_url"):
            embed.set_image(url=info["image_url"])
        if info.get("image_url_2"):
            embed.add_field(name="\u200b", value=f"[🖼️]({info['image_url_2']})", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class InfoView(discord.ui.View):
    def __init__(self, info_data: dict, lang: str):
        super().__init__(timeout=60)
        self.add_item(InfoSelect(info_data, lang))


# ---------------------------------------------------------------------------
# الـ Cog
# ---------------------------------------------------------------------------

class InfoDeleteSelect(discord.ui.Select):
    def __init__(self, entries: dict, lang: str):
        self.lang = lang
        options = [
            discord.SelectOption(label=value.get("title", key)[:100], value=key, emoji=_info_emoji(value))
            for key, value in entries.items()
        ]
        super().__init__(placeholder=t("delete_info_select_placeholder", lang), options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_key = self.values[0]
        title = self.view.entries[self.view.selected_key].get("title", self.view.selected_key)
        await interaction.response.send_message(t("delete_info_selected", self.lang, title=title), ephemeral=True)


class InfoDeleteView(discord.ui.View):
    def __init__(self, entries: dict, lang: str):
        super().__init__(timeout=180)
        self.entries = entries
        self.lang = lang
        self.selected_key = None
        self.add_item(InfoDeleteSelect(entries, lang))
        self.confirm.label = t("delete_info_confirm", lang)

    @discord.ui.button(label="🗑️ حذف الشرح", style=discord.ButtonStyle.danger, row=1)
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
        await interaction.response.edit_message(
            content=t("delete_info_success", self.lang, title=removed.get("title", self.selected_key)),
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
            discord.SelectOption(label=value.get("title", key)[:100], value=key, emoji=_info_emoji(value))
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
        self.title_input = discord.ui.TextInput(
            label=t("edit_info_title_field", lang)[:45],
            default=entry.get("title", "")[:100],
            required=False,
            max_length=100,
        )
        self.desc_input = discord.ui.TextInput(
            label=t("edit_info_desc_field", lang)[:45],
            default=entry.get("desc", "")[:4000],
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=4000,
        )
        self.add_item(self.title_input)
        self.add_item(self.desc_input)

    async def on_submit(self, interaction: discord.Interaction):
        data = load(CUSTOM_INFO_FILE)
        gid = str(interaction.guild_id)
        bucket = data.get(gid, {})
        entry = bucket.get(self.key)
        if entry is None:
            await interaction.response.send_message(t("delete_info_not_found", self.lang, title=self.key), ephemeral=True)
            return
        if self.title_input.value.strip():
            entry["title"] = self.title_input.value.strip()
        if self.desc_input.value.strip():
            entry["desc"] = self.desc_input.value.strip()
        if self.image:
            entry["image_url"] = self.image.url
        if self.image2:
            entry["image_url_2"] = self.image2.url
        save(CUSTOM_INFO_FILE, data)
        await interaction.response.send_message(
            t("edit_info_success", self.lang, title=entry.get("title", self.key)),
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
        """يدمج شروحات info.json الجاهزة مع إضافات الإدارة الخاصة بالسيرفر ده."""
        combined = dict(self.static_info_data)
        data = load(CUSTOM_INFO_FILE)
        combined.update(data.get(str(guild_id), {}))
        return combined

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

    @app_commands.command(name="add_monster", description="🐾 [إدارة] أضف وحش جديد لقائمة /monster (مع إمكانية إرفاق صور)")
    @app_commands.describe(
        name="Monster name",
        damage_type="Required damage type (e.g. cavalry attack)",
        heroes="Suggested heroes (comma-separated)",
        defense_note="Optional defense note",
        image="Optional monster or formation image",
        image2="Optional second image",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_monster(
        self,
        interaction: discord.Interaction,
        name: str,
        damage_type: str,
        heroes: str,
        defense_note: Optional[str] = None,
        image: Optional[discord.Attachment] = None,
        image2: Optional[discord.Attachment] = None,
    ):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        for att in (image, image2):
            if att and not (att.content_type or "").startswith("image/"):
                await interaction.response.send_message(t("add_monster_bad_image", lang), ephemeral=True)
                return

        data = load(CUSTOM_MONSTERS_FILE)
        gid = str(interaction.guild_id)
        data.setdefault(gid, {})
        key = name.strip().lower().replace(" ", "_")
        entry = {
            "name": name.strip(),
            "damage_type": damage_type.strip(),
            "heroes": heroes.strip(),
            "emoji": "🐾",
        }
        if defense_note:
            entry["defense_note"] = defense_note.strip()
        if image:
            entry["image_url"] = image.url
        if image2:
            entry["image_url_2"] = image2.url
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

    @app_commands.command(name="info", description="ℹ️ شرح الأحداث (ساحة التنين، المنفرد، KvK، الجحيم...)")
    async def info(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        info_data = self._get_info(interaction.guild_id)
        if not info_data:
            await interaction.response.send_message(t("info_empty", lang), ephemeral=True)
            return
        await interaction.response.send_message(
            t("info_prompt", lang), view=InfoView(info_data, lang), ephemeral=True
        )

    @app_commands.command(name="add_info", description="ℹ️ [إدارة] أضف شرح جديد لأمر /info (مع إمكانية إرفاق صور)")
    @app_commands.describe(
        title="Info title (e.g. Dragon Arena)",
        desc="Info description",
        image="Optional reference image",
        image2="Optional second image",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_info(
        self,
        interaction: discord.Interaction,
        title: str,
        desc: str,
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
        entry = {"title": title.strip(), "desc": desc.strip(), "emoji": INFO_DEFAULT_EMOJI}
        if image:
            entry["image_url"] = image.url
        if image2:
            entry["image_url_2"] = image2.url
        data[gid][key] = entry
        save(CUSTOM_INFO_FILE, data)

        await interaction.response.send_message(t("add_info_success", lang, title=title.strip()), ephemeral=True)

    @add_info.error
    async def add_info_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = get_lang(interaction.guild_id, interaction.user.id)
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(t("add_info_admin_only", lang), ephemeral=True)
        else:
            await interaction.response.send_message(t("unexpected_error", lang), ephemeral=True)

    @app_commands.command(name="delete_info", description="🗑️ [إدارة] اختر شرحًا مضافًا واحذفه")
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

    @app_commands.command(name="edit_info", description="✏️ [إدارة] اختر شرحًا وعدّل نصه أو أضف صورة")
    @app_commands.describe(
        image="Optional new first image (replaces the current one)",
        image2="Optional new second image (replaces the current one)",
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
