import discord
from discord.ext import commands
from discord import app_commands

from config import AUTHORIZED_ROLE_ID

class Restart(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="restart", description="Restart the bot")
    @app_commands.checks.has_role(AUTHORIZED_ROLE_ID)
    async def restart(self, interaction: discord.Interaction):
        extensions = [ext for ext in self.bot.extensions]
        await interaction.response.send_message(f"Reloading {len(extensions)} extension(s)...", ephemeral=False)
        
        for ext in extensions:
            try:
                await self.bot.reload_extension(ext)
            except Exception as e:
                await interaction.followup.send(f"Failed to reload {ext}: {e}", ephemeral=False)
        
        await interaction.followup.send("Restart completed!", ephemeral=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(Restart(bot))
