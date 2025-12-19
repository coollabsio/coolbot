import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import datetime

from config import (
    SUPPORT_CHANNEL_ID,
    SOLVED_TAG_ID,
    AUTHORIZED_ROLE_ID,
)
from commands.solved import SolvedButton

async def get_post_owner_id(thread: discord.Thread) -> int:
    """
    Determine the actual post owner by inspecting the thread's starter message.
    If the starter is by the bot and mentions a user, use that mention.
    Otherwise use the starter author or the thread owner.
    """
    try:
        starter = await thread.fetch_message(thread.id)
    except discord.NotFound:
        return thread.owner_id

    if not starter.author.bot:
        return starter.author.id
    if starter.mentions:
        return starter.mentions[0].id
    return thread.owner_id

class SuggestSolved(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="suggest-to-solve-the-post", 
        description="Suggest the post owner to mark the post as solved"
    )
    async def suggest_to_solve(self, interaction: discord.Interaction):
        channel = interaction.channel
        if not isinstance(channel, discord.Thread) or channel.parent.id != SUPPORT_CHANNEL_ID:
            await interaction.response.send_message(
                "This command can only be used in a support thread.",
                ephemeral=True
            )
            return

        # Only allow authorized roles to use this command
        if not any(role.id == AUTHORIZED_ROLE_ID for role in getattr(interaction.user, 'roles', [])):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        thread: discord.Thread = channel

        # Determine post owner
        owner_id = await get_post_owner_id(thread)

        # Find last message by the owner
        last_owner_msg = None
        async for msg in thread.history(limit=5, oldest_first=False):
            if msg.author.id == owner_id:
                last_owner_msg = msg
                break

        embed = discord.Embed(
            title="Mark as Solved?",
            description=(
                "It looks like your issue might be solved. "
                "If that's the case, please click the button below to mark this post as solved."
            ),
            color=discord.Color.green()
        )

        solved_button = SolvedButton(self.bot, thread)
        view = ui.View(timeout=None)
        view.add_item(solved_button)

        # Reply to owner's last message or send new message mentioning owner
        try:
            if last_owner_msg:
                await last_owner_msg.reply(
                    embed=embed,
                    view=view,
                    mention_author=True,
                    allowed_mentions=discord.AllowedMentions(users=True)
                )
            else:
                await thread.send(
                    f"Hey <@{owner_id}>!",
                    embed=embed,
                    view=view,
                    allowed_mentions=discord.AllowedMentions(users=True)
                )
            await interaction.followup.send(
                "Suggestion sent to the post owner.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to send messages in this thread.",
                ephemeral=True
            )
        except discord.HTTPException:
            await interaction.followup.send(
                "Failed to send the suggestion. Please try again later.",
                ephemeral=True
            )
            return

        # Skip if already solved
        solved_tag = thread.parent.get_tag(SOLVED_TAG_ID)
        if solved_tag in thread.applied_tags:
            await interaction.followup.send(
                "This thread is already marked as solved.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Mark as Solved?",
            description=(
                "It looks like your issue might be solved. "
                "If that's the case, please click the button below to mark this post as solved."
            ),
            color=discord.Color.green()
        )

        solved_button = SolvedButton(self.bot, thread)
        view = ui.View(timeout=None)
        view.add_item(solved_button)

        # Reply to owner's last message
        try:
            await last_owner_msg.reply(
                embed=embed,
                view=view,
                mention_author=True,
                allowed_mentions=discord.AllowedMentions(users=True)
            )
            await interaction.followup.send(
                "Suggestion sent to the post owner.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to send messages in this thread.",
                ephemeral=True
            )
        except discord.HTTPException:
            await interaction.followup.send(
                "Failed to send the suggestion. Please try again later.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(SuggestSolved(bot))
