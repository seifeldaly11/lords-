"""واجهة اختبار تفاعلية من ملف Discord.js المرفق، بنسخة discord.py."""

import os

import discord
from discord import app_commands
from discord.ext import commands


TEST_IMAGE_URL = os.getenv("TEST_IMAGE_URL", "").strip()


class TestComponentsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(TestSelect())

    @discord.ui.button(
        label="السلام عليكم",
        custom_id="testt",
        style=discord.ButtonStyle.success,
    )
    async def greeting(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("وعليكم السلام", ephemeral=True)

    @discord.ui.button(
        label="زر ثاني",
        custom_id="testtt",
        style=discord.ButtonStyle.primary,
    )
    async def second_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("دوست على الزر الثاني", ephemeral=True)


class TestSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            custom_id="menu2",
            placeholder="اضغط هنا",
            options=[
                discord.SelectOption(label="hi", value="test"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "test":
            await interaction.response.send_message("انا هنا")


def build_test_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🧩 Interactive test",
        description="Example Text",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Section", value="Example Text", inline=False)
    if TEST_IMAGE_URL.startswith(("http://", "https://")):
        embed.set_image(url=TEST_IMAGE_URL)
        embed.set_thumbnail(url=TEST_IMAGE_URL)
    return embed


class ComponentsCog(commands.Cog):
    """أزرار وقائمة الاختيار الموجودة في العينة المرفقة."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_test_message(self, channel: discord.abc.Messageable):
        await channel.send(embed=build_test_embed(), view=TestComponentsView())

    @app_commands.command(
        name="test",
        description="🧩 جرّب الأزرار وقائمة الاختيار التفاعلية",
    )
    async def test(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=build_test_embed(),
            view=TestComponentsView(),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ComponentsCog(bot))