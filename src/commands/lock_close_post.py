import discord
from discord import app_commands
from discord.ext import commands

from config import AUTHORIZED_ROLE_ID, SOLVED_TAG_ID

class LockClosePost(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="lock-close", description="Locks and archives the current post.")
    async def lock_close(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)

            # Check if user has the required role
            if AUTHORIZED_ROLE_ID not in [role.id for role in interaction.user.roles]:
                embed = discord.Embed(
                    description=f"{interaction.user.mention}, you are not allowed to use this command.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Ensure command is used inside a thread
            if not isinstance(interaction.channel, discord.Thread):
                await interaction.followup.send("This command can only be used inside a thread.", ephemeral=True)
                return

            thread = interaction.channel
            parent_channel = thread.parent

            if isinstance(parent_channel, discord.ForumChannel):
                # Find the correct tag object
                solved_tag = next((tag for tag in parent_channel.available_tags if tag.id == SOLVED_TAG_ID), None)
                if solved_tag:
                    await thread.edit(locked=True, archived=True, applied_tags=[solved_tag])
                else:
                    await thread.edit(locked=True, archived=True)  # Archive without applying a tag if not found
            else:
                await thread.edit(locked=True, archived=True)  # If it's not a forum thread, just lock and archive it

            # Send confirmation message
            embed = discord.Embed(
                description=f"{interaction.user.mention} locked and closed this post.",
                color=discord.Color.red()
            )
            await thread.send(embed=embed)

            # Ensure interaction gets a response
            await interaction.followup.send("The post has been successfully locked and closed.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send("An error occurred while locking and closing the post.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(LockClosePost(bot))
