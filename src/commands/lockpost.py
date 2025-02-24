import discord
from discord import app_commands
from discord.ext import commands

from config import AUTHORIZED_ROLE_ID

class LockPost(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="lock-post", description="Locks the current post, preventing further replies.")
    async def lock_post(self, interaction: discord.Interaction):
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
            await thread.edit(locked=True)  # Lock the thread to prevent new messages

            # Send confirmation message
            embed = discord.Embed(
                description=f"{interaction.user.mention} locked this post.",
                color=discord.Color.green()
            )
            await thread.send(embed=embed)

            await interaction.followup.send("The post has been successfully locked.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send("An error occurred while locking the post.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(LockPost(bot))
