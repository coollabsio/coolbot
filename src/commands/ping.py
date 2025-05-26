import discord
from discord.ext import commands
from discord import app_commands

VERSION = "v3.0 Stable"

class PingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's status")
    async def ping(self, interaction: discord.Interaction):
        latency = self.bot.latency * 1000  # Convert to milliseconds
        embed = discord.Embed(
            title="I'm Alive!",
            description=f"**Response time:** {latency:.2f}ms"
        )
        embed.set_footer(text=f"Version {VERSION}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PingCog(bot))
