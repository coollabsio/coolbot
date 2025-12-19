import discord
from discord.ext import commands
from discord import app_commands, ui
import re

from config import AUTHORIZED_ROLE_ID


class AutoresponseView(ui.View):
    def __init__(self, autoresponses, current_page=0):
        super().__init__(timeout=300)
        self.autoresponses = autoresponses
        self.current_page = current_page
        self.max_pages = len(autoresponses)
        self.update_buttons()

    def update_buttons(self):
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.max_pages - 1

    def get_embed(self):
        ar = self.autoresponses[self.current_page]
        embed = discord.Embed(title="Available Autoresponses", color=discord.Color.blue())
        embed.set_footer(text=f"(Page {self.current_page+1}/{self.max_pages})")
        embed.add_field(name="ID", value=f"```py\n{ar['id']}\n```", inline=True)
        embed.add_field(name="Name", value=f"```py\n{ar['name']}\n```", inline=True)
        embed.add_field(name="Regex", value=f"```py\n{ar['regex']}\n```", inline=False)
        embed.add_field(name="Response", value=f"```ruby\n{ar['response_message']}\n```", inline=False)
        return embed

    @ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button):
        self.current_page -= 1
        self.update_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: ui.Button):
        self.current_page += 1
        self.update_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class AutoResponder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages
        if message.author == self.bot.user:
            return

        # Ignore messages from authorized users
        if any(role.id == AUTHORIZED_ROLE_ID for role in getattr(message.author, 'roles', [])):
            return

        # Check if message content matches any autoresponse regex
        autoresponses = await self.bot.db.get_autoresponses()
        for ar in autoresponses:
            try:
                if re.search(ar['regex'], message.content, re.IGNORECASE):
                    response = ar['response_message'].replace("${usermention}", message.author.mention)
                    await message.reply(response)
                    break  # Only respond to the first match
            except re.error:
                # Invalid regex, skip
                continue

        # Process commands
        await self.bot.process_commands(message)

    @app_commands.command(
        name="add-autoresponse",
        description="Add a new autoresponse message"
    )
    @app_commands.describe(
        name="Unique name for the autoresponse",
        regex="Regex pattern to match in messages",
        response="Response message to send (use ${usermention} to mention the user)"
    )
    async def add_autoresponse(
        self,
        interaction: discord.Interaction,
        name: str,
        regex: str,
        response: str
    ):
        # Check authorization
        if not any(role.id == AUTHORIZED_ROLE_ID for role in getattr(interaction.user, 'roles', [])):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True
            )
            return

        # Validate regex
        try:
            re.compile(regex)
        except re.error as e:
            await interaction.response.send_message(
                f"Invalid regex: {e}",
                ephemeral=True
            )
            return

        try:
            await self.bot.db.add_autoresponse(name, regex, response)
            await interaction.response.send_message(
                f"Autoresponse `{name}` added successfully.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to add autoresponse: {e}",
                ephemeral=True
            )

    @app_commands.command(
        name="view-autoresponses",
        description="View all autoresponse messages"
    )
    async def view_autoresponses(self, interaction: discord.Interaction):
        # Check authorization
        if not any(role.id == AUTHORIZED_ROLE_ID for role in getattr(interaction.user, 'roles', [])):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True
            )
            return

        autoresponses = await self.bot.db.get_autoresponses()
        if not autoresponses:
            await interaction.response.send_message(
                "No autoresponses configured.",
                ephemeral=True
            )
            return

        view = AutoresponseView(autoresponses)
        embed = view.get_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(
        name="delete-autoresponse",
        description="Delete an autoresponse message by name or ID"
    )
    @app_commands.describe(
        identifier="Name or ID of the autoresponse to delete"
    )
    async def delete_autoresponse(self, interaction: discord.Interaction, identifier: str):
        # Check authorization
        if not any(role.id == AUTHORIZED_ROLE_ID for role in getattr(interaction.user, 'roles', [])):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True
            )
            return

        try:
            await self.bot.db.delete_autoresponse(identifier)
            await interaction.response.send_message(
                f"Autoresponse `{identifier}` deleted successfully.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to delete autoresponse: {e}",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoResponder(bot))