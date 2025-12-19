import discord
from discord.ext import commands
from discord import app_commands

COOLBOT_JSON_URL = "https://next.coolify.io/docs/coolbot.json"

class DocsDBSync(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="docs-db-sync", description="Syncs documentation database from remote URL")
    @app_commands.guild_only()
    async def docs_db_sync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            updated, status_info = await self.bot.db.sync_docs_from_url(COOLBOT_JSON_URL)  # type: ignore

            # Create embed with sync information
            embed = discord.Embed(
                color=discord.Color.green() if updated else discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            description_parts = []

            # Remote URL (1st)
            description_parts.append(f"**Remote URL:**\n```{status_info['url']}```")

            # Request Headers (2nd)
            header_status = "Used" if status_info['used_etag_header'] else "Not used"
            description_parts.append(f"**Request Headers:**\n```If-None-Match: {header_status}```")

            # Response Status (3rd)
            description_parts.append(f"**Response Status:**\n```HTTP {status_info['response_status']}```")

            # Current ETag (4th)
            if status_info["current_etag"]:
                description_parts.append(f"**Current ETag:**\n```{status_info['current_etag']}```")
            else:
                description_parts.append("**Current ETag:**\n```None (first sync)```")

            # Response ETag (5th)
            if status_info["response_etag"]:
                description_parts.append(f"**Response ETag:**\n```{status_info['response_etag']}```")

            # Sync Status (6th)
            if status_info["error"]:
                description_parts.append(f"**Sync Status:**\n```Error: {status_info['error']}```")
                embed.color = discord.Color.red()
            elif updated:
                description_parts.append(f"**Sync Status:**\n```Database updated with {status_info['docs_count']} documentation entries```")
            else:
                description_parts.append("**Sync Status:**\n```No updates needed (ETag match)```")

            embed.description = "\n\n".join(description_parts)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            embed = discord.Embed(
                title="Documentation Sync Failed",
                description=f"An error occurred during sync: {e}",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(DocsDBSync(bot))