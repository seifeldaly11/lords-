"""Interactive Components v2-style demo implemented with discord.py."""

import os

import discord
from discord.ext import commands


TEST_IMAGE_URL = os.getenv("TEST_IMAGE_URL", "").strip()


class TestComponentsView(discord.ui.View):
    """Interactive controls matching the JavaScript Components v2 example."""

    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(TestSelect())

    @discord.ui.button(
        label="السلام عليكم",
        custom_id="testt",
        style=discord.ButtonStyle.success
    )
    async def greeting(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "وعليكم السلام — Wa alaikum assalam"
        )

    @discord.ui.button(
        label="زر ثاني",
        custom_id="testtt",
        style=discord.ButtonStyle.primary
    )
    async def second_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "دوست على الزر الثاني — You pressed the second button"
        )


class TestSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            custom_id="menu2",
            placeholder="اضغط هنا • Choose an option",
            options=[
                discord.SelectOption(label="hi • أهلاً", value="test"),
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "test":
            await interaction.response.send_message("أنا هنا — I'm here")


def build_test_embed() -> discord.Embed:
    """Build the embed equivalent of the supplied ContainerBuilder layout.

    discord.py 2.4 does not expose Discord.js' raw ContainerBuilder API, so
    the same visual hierarchy is represented with an Embed and a View while
    keeping the bot compatible with the current dependency.
    """
    embed = discord.Embed(
        title="🧩 INFORMATION • معلومات",
        description=(
            "**English:** This text is inside a Text Display component.\n"
            "**العربية:** هذا النص داخل مكوّن عرض نصي.\n\n"
            "Use the menu and buttons below to test the interactive components.\n"
            "استخدم القائمة والأزرار بالأسفل لتجربة المكوّنات التفاعلية."
        ),
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="🔽 Select Menu • قائمة الاختيار",
        value="hi -> test\nاختر من القائمة لعرض الرد التفاعلي.",
        inline=False
    )
    embed.add_field(
        name="────────────",
        value="🟢 السلام عليكم  •  🔵 زر ثاني\nTwo bilingual buttons are ready below.",
        inline=False
    )
    if TEST_IMAGE_URL.startswith(("http://", "https://")):
        # Main image = Media Gallery equivalent; thumbnail = Section accessory.
        embed.set_image(url=TEST_IMAGE_URL)
        embed.set_thumbnail(url=TEST_IMAGE_URL)
    embed.set_footer(text="Components v2-style demo • تجربة ثنائية اللغة")
    return embed


class ComponentsCog(commands.Cog):
    """Interactive buttons and select menu from the supplied JavaScript sample."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_test_message(self, channel: discord.abc.Messageable):
        await channel.send(embed=build_test_embed(), view=TestComponentsView())


async def setup(bot: commands.Bot):
    await bot.add_cog(ComponentsCog(bot))
