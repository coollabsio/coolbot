import discord
from discord.ext import commands
from discord import app_commands
import logging

from config import (
    GENERAL_CHANNEL_ID,
    AUTHORIZED_ROLE_ID
)

logger = logging.getLogger(__name__)

class UserSelectView(discord.ui.View):
    """
    Prompt the executor to select a target user from the guild.
    """
    def __init__(self, executor: discord.Member, bot: commands.Bot, origin_channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.executor = executor
        self.bot = bot
        self.origin_channel = origin_channel

        options = [
            discord.SelectOption(label=member.display_name, value=str(member.id))
            for member in executor.guild.members
        ] or [
            discord.SelectOption(label="No users available", value="none", default=True)
        ]

        self.select = discord.ui.Select(
            placeholder="Select a user",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="user_select"
        )
        self.select.callback = self.on_user_select
        self.add_item(self.select)

    async def on_user_select(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected = self.select.values[0]
        if selected == "none":
            return await interaction.followup.send("No valid users available.", ephemeral=True)

        target = interaction.guild.get_member(int(selected))
        if not target:
            return await interaction.followup.send("Selected user not found.", ephemeral=True)

        # Create a private thread in the general channel
        general = self.bot.get_channel(GENERAL_CHANNEL_ID)
        if general is None:
            logger.error(f"General channel {GENERAL_CHANNEL_ID} not found.")
            return await interaction.followup.send("Could not find the general channel.", ephemeral=True)

        try:
            thread = await general.create_thread(
                name=f"Private: {self.executor.display_name} & {target.display_name}",
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440
            )
            await thread.add_user(self.executor)
            await thread.add_user(target)
        except Exception as e:
            logger.error(f"Failed to create private thread: {e}")
            return await interaction.followup.send("Failed to create private thread.", ephemeral=True)

        # Send link in the origin channel
        link = thread.jump_url
        await self.origin_channel.send(
            f"Hey {self.executor.mention} && {target.mention}, I’ve set up a private thread for your discussion. You can continue on: {link}"
        )

        # Notify inside the private thread
        embed = discord.Embed(
            description=(
                f"This is a private thread, only you ({target.mention}) and the **CoolLabs team members** can view it.\n\n"
                "Do not ping any other users here, as that will add them to the thread."
            ),
            color=discord.Color.yellow()
        )
        await thread.send(content=f"Hey {self.executor.mention} && {target.mention}!", embed=embed)

        try:
            await interaction.delete_original_response()
        except Exception:
            pass

        self.stop()

class PrivateThreadCog(commands.Cog):
    """
    Cog to handle creation of private threads.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create-private-thread", description="Create a private thread with a selected user")
    async def create_private_thread(self, interaction: discord.Interaction):
        # Permission check
        if AUTHORIZED_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )

        view = UserSelectView(interaction.user, self.bot, interaction.channel)
        embed = discord.Embed(
            title="Create Private Thread",
            description="Select a user to create a private thread with.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(PrivateThreadCog(bot))
