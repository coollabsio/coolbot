import discord
from discord.ext import commands
from discord import app_commands, ui
import re
from datetime import datetime, timedelta

from config import AUTHORIZED_ROLE_ID, AUTOMOD_REPORT_CHANNEL_ID, REPORTS_PING_ROLE_ID


class AutomoderationView(ui.View):
    def __init__(self, automoderations, current_page=0):
        super().__init__(timeout=300)
        self.automoderations = automoderations
        self.current_page = current_page
        self.max_pages = len(automoderations)
        self.update_buttons()

    def update_buttons(self):
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.max_pages - 1

    def get_embed(self):
        am = self.automoderations[self.current_page]
        embed = discord.Embed(title="Available automoderation rules", color=discord.Color.green())
        embed.set_footer(text=f"(Page {self.current_page+1}/{self.max_pages})")
        embed.add_field(name="ID", value=f"```py\n{am['id']}\n```", inline=True)
        embed.add_field(name="Name", value=f"```py\n{am['name']}\n```", inline=True)
        embed.add_field(name="Regex", value=f"```py\n{am['regex']}\n```", inline=False)
        embed.add_field(name="Reason", value=f"```py\n{am['reason']}\n```", inline=False)
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


class Automoderation(commands.Cog):
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

        # Check if message content matches any automoderation regex
        automoderations = await self.bot.db.get_automoderation_rules()
        for am in automoderations:
            try:
                if re.search(am['regex'], message.content, re.IGNORECASE):
                    # Mute user for 12 hours
                    if isinstance(message.author, discord.Member):
                        await message.author.timeout(discord.utils.utcnow() + timedelta(hours=12))

                    # Send embed to trigger channel
                    embed_trigger = discord.Embed(
                        description=f"{message.author.mention} muted\n> Reason: {am['reason']}\n> Duration: 12 hours",
                        color=discord.Color.green()
                    )
                    await message.channel.send(embed=embed_trigger)

                    # Send full embed to report channel
                    report_channel = self.bot.get_channel(AUTOMOD_REPORT_CHANNEL_ID)
                    if report_channel:
                        ping = f"<@&{REPORTS_PING_ROLE_ID}>"
                        await report_channel.send(ping)
                        embed_report = discord.Embed(title="Automoderation Triggered", color=discord.Color.green())
                        embed_report.add_field(name="User", value=f" - {message.author.mention} (`{message.author.id}`)", inline=True)
                        embed_report.add_field(name="Channel", value=f" - {message.channel.mention}", inline=False)
                        embed_report.add_field(name="Rule", value=f"```\n{am['name']}\n```", inline=False)
                        embed_report.add_field(name="Reason", value=f"```\n{am['reason']}\n```", inline=False)
                        embed_report.add_field(name="Message", value=f"```\n{message.content[:1024]}\n```", inline=False)
                        await report_channel.send(embed=embed_report)

                    # Delete all messages from user in last 5 minutes
                    cutoff = discord.utils.utcnow() - timedelta(minutes=5)
                    async for msg in message.channel.history(after=cutoff, limit=100):
                        if msg.author == message.author:
                            await msg.delete()

                    break  # Only trigger on the first match
            except re.error:
                # Invalid regex, skip
                continue

        # Process commands
        await self.bot.process_commands(message)

    @app_commands.command(
        name="add-automoderation-rule",
        description="Add a new automoderation rule"
    )
    @app_commands.describe(
        name="Unique name for the automoderation rule",
        regex="Regex pattern to match in messages",
        reason="Reason for the automoderation rule"
    )
    async def add_automoderation(
        self,
        interaction: discord.Interaction,
        name: str,
        regex: str,
        reason: str
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
            await self.bot.db.add_automoderation_rule(name, regex, reason)
            await interaction.response.send_message(
                f"Automoderation rule `{name}` added successfully.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to add automoderation rule: {e}",
                ephemeral=True
            )

    @app_commands.command(
        name="view-automoderations",
        description="View all automoderation rules"
    )
    async def view_automoderations(self, interaction: discord.Interaction):
        # Check authorization
        if not any(role.id == AUTHORIZED_ROLE_ID for role in getattr(interaction.user, 'roles', [])):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True
            )
            return

        automoderations = await self.bot.db.get_automoderation_rules()
        if not automoderations:
            await interaction.response.send_message(
                "No automoderation rules configured.",
                ephemeral=True
            )
            return

        view = AutomoderationView(automoderations)
        embed = view.get_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(
        name="delete-automoderation-rule",
        description="Delete an automoderation rule by name or ID"
    )
    @app_commands.describe(
        identifier="Name or ID of the automoderation rule to delete"
    )
    async def delete_automoderation(self, interaction: discord.Interaction, identifier: str):
        # Check authorization
        if not any(role.id == AUTHORIZED_ROLE_ID for role in getattr(interaction.user, 'roles', [])):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True
            )
            return

        try:
            await self.bot.db.delete_automoderation_rule(identifier)
            await interaction.response.send_message(
                f"Automoderation rule `{identifier}` deleted successfully.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to delete automoderation rule: {e}",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Automoderation(bot))