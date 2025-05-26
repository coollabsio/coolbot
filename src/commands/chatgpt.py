import urllib.parse
import discord
from discord.ext import commands
from discord import app_commands

class ChatGPTCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="chat-gpt", description="Let me ask ChatGPT for you")
    @app_commands.describe(query="What do you want answer for?")
    async def google(self, interaction: discord.Interaction, query: str):
        # Encode the query for a URL
        encoded_query = urllib.parse.quote_plus(query)
        url = f"http://chat.com/?q={encoded_query}"

        # Create the embed
        embed = discord.Embed(
            description=f"### [{query}]({url})"
        )
        embed.set_footer(text=f"Recommended by {interaction.user.display_name}")

        # Create a button linking to the URL
        view = discord.ui.View()
        button = discord.ui.Button(label="View in browser", style=discord.ButtonStyle.secondary, url=url)
        view.add_item(button)

        # Send the embed with the button
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(ChatGPTCog(bot))
