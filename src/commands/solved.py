import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import datetime

from config import (
            SOLVED_TAG_ID, 
            NOT_SOLVED_TAG_ID, 
            COOLIFY_CLOUD_TAG_ID, 
            SUPPORT_CHANNEL_ID, 
            AUTHORIZED_ROLE_ID,
)

async def process_solved_thread(thread: discord.Thread, bot: commands.Bot):
    """Common logic for marking a thread as solved"""
    await bot.post_closer.schedule_close(thread)
    now = datetime.datetime.now(datetime.timezone.utc)
    one_hour = now + datetime.timedelta(hours=1)
    return round(one_hour.timestamp())

async def is_user_authorized(thread: discord.Thread, user: discord.User) -> bool:
    """
    Determines whether the given user is authorized to modify the thread.
    Authorization is granted if the user is the post owner or has the authorized role.
    """
    # Fetch the starter message of the thread
    starter = await thread.fetch_message(thread.id)
    post_owner_id = None
    if not starter.author.bot:
        post_owner_id = starter.author.id
    else:
        if starter.mentions:
            post_owner_id = starter.mentions[0].id

    # Check if the user is the post owner
    if post_owner_id is not None and user.id == post_owner_id:
        return True

    # Check if the user has the authorized role
    if hasattr(user, 'roles'):
        if any(role.id == AUTHORIZED_ROLE_ID for role in user.roles):
            return True

    return False

class NotSolvedButton(ui.Button):
    def __init__(self, bot: commands.Bot, thread: discord.Thread):
        super().__init__(
            label="Mark as Not Solved",
            style=discord.ButtonStyle.grey,
            custom_id="not_solved_button"
        )
        self.bot = bot
        self.thread = thread
        self.message = None

    async def callback(self, interaction: discord.Interaction):
        try:
            # Permission check: only post owner or authorized users may use this button
            if not await is_user_authorized(self.thread, interaction.user):
                error_embed = discord.Embed(
                    title="Authorization Error",
                    description="You are not authorized to perform this action.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            # Cancel any scheduled closure
            await interaction.client.post_closer.cancel_close(self.thread.id)

            # Update tags
            allowed_tags = []
            coolify = self.thread.parent.get_tag(COOLIFY_CLOUD_TAG_ID)
            not_solved = self.thread.parent.get_tag(NOT_SOLVED_TAG_ID)
            if coolify and coolify in self.thread.applied_tags:
                allowed_tags.append(coolify)
            if not_solved:
                allowed_tags.append(not_solved)
            else:
                await interaction.response.send_message("Not Solved tag not found.", ephemeral=True)
                return

            await self.thread.edit(applied_tags=allowed_tags, reason="Marked as not solved")

            # Update the embed:
            original_embed = interaction.message.embeds[0]
            if original_embed.title == "Post Solved":
                original_embed.title = "Post Not Solved"
                original_embed.description = f"~~{original_embed.description}~~\n\n**Post marked as NOT solved by {interaction.user.mention}.**"
            else:
                original_embed.description += f"\n\n**Post marked as NOT solved by {interaction.user.mention}.**"
            original_embed.color = discord.Color.orange()

            view = ui.View(timeout=None)
            view.add_item(SolvedButton(self.bot, self.thread))
            
            await interaction.response.edit_message(embed=original_embed, view=view)
            
            # Update the existing view record in database instead of creating a new one
            try:
                # First try to remove any existing view for this message
                await self.bot.db.remove_view(interaction.message.id)
                
                # Then add the new view
                await self.bot.db.add_view(
                    message_id=interaction.message.id,
                    channel_id=interaction.channel_id,
                    thread_id=self.thread.id,
                    view_type="solved",
                    is_solved=False
                )
                
            except Exception as e:
                pass
                
        except Exception as e:
            await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)

class SolvedButton(ui.Button):
    def __init__(self, bot: commands.Bot, thread: discord.Thread):
        super().__init__(
            label="Mark as Solved",
            style=discord.ButtonStyle.green,
            custom_id="solved_button"
        )
        self.bot = bot
        self.thread = thread

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            # Permission check
            if not await is_user_authorized(self.thread, interaction.user):
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="No Permission",
                        description="You are not authorized to perform this action.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            # Update tags
            allowed_tags = []
            coolify = self.thread.parent.get_tag(COOLIFY_CLOUD_TAG_ID)
            solved = self.thread.parent.get_tag(SOLVED_TAG_ID)
            if coolify and coolify in self.thread.applied_tags:
                allowed_tags.append(coolify)
            if solved:
                allowed_tags.append(solved)
            else:
                await interaction.followup.send("Solved tag not found.", ephemeral=True)
                return

            await self.thread.edit(applied_tags=allowed_tags, reason="Marked as solved")

            # Schedule thread closure
            close_time = await process_solved_thread(self.thread, interaction.client)

            original_embed = interaction.message.embeds[0]
            original_embed.title = f"~~{original_embed.title}~~"
            
            if original_embed.description:
                parts = original_embed.description.split('\n\n')  # Split on double newlines to preserve formatting
                struck_parts = []
                for part in parts:
                    # If this part contains "NOT solved", strike through the whole thing
                    if "NOT solved" in part or not any("~~" in line for line in part.split('\n')):
                        struck_parts.append(f"~~{part}~~")
                    else:
                        # Keep already struck-through parts as they are
                        struck_parts.append(part)
                original_embed.description = '\n\n'.join(struck_parts)

            await interaction.message.edit(embed=original_embed, view=None)

            # Send new message with NotSolved button
            new_embed = discord.Embed(
                title="Post Solved",
                description=f"{interaction.user.mention} marked this post as solved.\nIt will be automatically closed and locked <t:{close_time}:R>.",
                color=discord.Color.green()
            )
            
            view = ui.View(timeout=None)
            not_solved_button = NotSolvedButton(self.bot, self.thread)
            view.add_item(not_solved_button)

            new_message = await interaction.followup.send(embed=new_embed, view=view)
            
            # Update database records
            try:
                await self.bot.db.remove_view(interaction.message.id)
                await self.bot.db.add_view(
                    message_id=new_message.id,
                    channel_id=interaction.channel_id,
                    thread_id=self.thread.id,
                    view_type="not_solved",
                    is_solved=True
                )
            except Exception:
                pass

        except Exception:
            try:
                await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)
            except:
                pass

class SolvePost(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="solved", description="Mark the current post as solved")
    async def solved(self, interaction: discord.Interaction):
        # Validate the channel
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("This command can only be used in a thread.", ephemeral=True)
            return
        thread: discord.Thread = interaction.channel

        if thread.parent.id != SUPPORT_CHANNEL_ID:
            await interaction.response.send_message("This command is only for the support channel.", ephemeral=True)
            return

        # Check permissions by determining the post owner.
        starter = await thread.fetch_message(thread.id)
        is_owner = False
        if not starter.author.bot:
            is_owner = (starter.author.id == interaction.user.id)
        else:
            if starter.mentions:
                is_owner = (starter.mentions[0].id == interaction.user.id)

        has_auth = any(role.id == AUTHORIZED_ROLE_ID for role in interaction.user.roles) if hasattr(interaction.user, 'roles') else False

        if not (is_owner or has_auth):
            error_embed = discord.Embed(
                title="No Permission",
                description="You are not authorized to perform this action.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        # Check if already solved BEFORE deferring the response
        solved_tag = thread.parent.get_tag(SOLVED_TAG_ID)
        coolify = thread.parent.get_tag(COOLIFY_CLOUD_TAG_ID)
        if not solved_tag:
            await interaction.response.send_message("Solved tag not found.", ephemeral=True)
            return

        if solved_tag in thread.applied_tags:
            embed = discord.Embed(
                title="Post Already Solved",
                description="This post is already marked as solved.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        allowed_tags = [solved_tag]
        if coolify and coolify in thread.applied_tags:
            allowed_tags.append(coolify)
        await thread.edit(applied_tags=allowed_tags, reason="Marking post as solved")

        # Schedule thread closure
        close_time = await process_solved_thread(thread, interaction.client)

        now = datetime.datetime.now(datetime.timezone.utc)
        one_hour = now + datetime.timedelta(hours=1)
        embed = discord.Embed(
            title="Post Solved",
            description=f"{interaction.user.mention} marked this post as solved.\nIt will be automatically closed and locked <t:{round(one_hour.timestamp())}:R>.",
            color=discord.Color.green()
        )
        view = ui.View()
        not_solved_button = NotSolvedButton(self.bot, thread)
        view.add_item(not_solved_button)
        
        message = await interaction.followup.send(embed=embed, view=view, ephemeral=False)
        not_solved_button.message = message
        
async def setup(bot: commands.Bot):
    await bot.add_cog(SolvePost(bot))
