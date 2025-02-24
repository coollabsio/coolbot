import discord
from discord import app_commands
from discord.ext import commands

from config import AUTHORIZED_ROLE_ID, SOLVED_TAG_ID  # Ensure SOLVED_TAG_ID is an int

class ClosePost(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="close-post", description="Archives the current post")
    async def close_post(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

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
                    await thread.edit(archived=True, applied_tags=[solved_tag])
                else:
                    await thread.edit(archived=True)  # Archive without applying a tag if not found
            else:
                await thread.edit(archived=True)  # If it's not a forum thread, just archive it

            # Send confirmation message
            embed = discord.Embed(
                description=f"{interaction.user.mention} closed this post.",
                color=discord.Color.green()
            )
            await thread.send(embed=embed)


            await interaction.followup.send("The post has been successfully closed.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send("An error occurred while closing the post.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ClosePost(bot))
