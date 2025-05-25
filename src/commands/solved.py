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
    COMMUNITY_SUPPORT_CHANNEL_ID,
    COMMUNITY_SOLVED_TAG_ID,
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
    starter = await thread.fetch_message(thread.id)
    post_owner_id = None
    if not starter.author.bot:
        post_owner_id = starter.author.id
    else:
        if starter.mentions:
            post_owner_id = starter.mentions[0].id

    if post_owner_id is not None and user.id == post_owner_id:
        return True

    if hasattr(user, 'roles'):
        if any(role.id == AUTHORIZED_ROLE_ID for role in getattr(user, 'roles', [])):
            return True

    return False

class CommunitySolvedButton(ui.Button):
    def __init__(self, bot: commands.Bot, thread: discord.Thread):
        super().__init__(
            label="Mark as Solved",
            style=discord.ButtonStyle.green,
            custom_id="community_solved_button"
        )
        self.bot = bot
        self.thread = thread

    async def callback(self, interaction: discord.Interaction):
        if not await is_user_authorized(self.thread, interaction.user):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="No Permission",
                    description="You are not authorized to perform this action.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        community_tag = self.thread.parent.get_tag(COMMUNITY_SOLVED_TAG_ID)
        if not community_tag:
            await interaction.response.send_message("Community Solved tag not found.", ephemeral=True)
            return

        # Preserve other tags, only add community solved
        new_tags = [t for t in self.thread.applied_tags if t.id != COMMUNITY_SOLVED_TAG_ID]
        new_tags.append(community_tag)
        await self.thread.edit(applied_tags=new_tags, reason="Marked community post as solved")

        # Update message embed
        embed = discord.Embed(
            title="Post Solved",
            description=f"{interaction.user.mention} marked this community post as solved.",
            color=discord.Color.green()
        )
        view = ui.View(timeout=None)
        view.add_item(CommunityNotSolvedButton(self.bot, self.thread))
        await interaction.response.edit_message(embed=embed, view=view)

class CommunityNotSolvedButton(ui.Button):
    def __init__(self, bot: commands.Bot, thread: discord.Thread):
        super().__init__(
            label="Mark as Not Solved",
            style=discord.ButtonStyle.grey,
            custom_id="community_not_solved_button"
        )
        self.bot = bot
        self.thread = thread

    async def callback(self, interaction: discord.Interaction):
        if not await is_user_authorized(self.thread, interaction.user):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="No Permission",
                    description="You are not authorized to perform this action.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Remove only the community solved tag
        new_tags = [t for t in self.thread.applied_tags if t.id != COMMUNITY_SOLVED_TAG_ID]
        await self.thread.edit(applied_tags=new_tags, reason="Marked community post as not solved")

        # Update message embed
        embed = discord.Embed(
            title="Post Not Solved",
            description=f"**Post marked as NOT solved by {interaction.user.mention}.**",
            color=discord.Color.orange()
        )
        view = ui.View(timeout=None)
        view.add_item(CommunitySolvedButton(self.bot, self.thread))
        await interaction.response.edit_message(embed=embed, view=view)

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
            if not await is_user_authorized(self.thread, interaction.user):
                error_embed = discord.Embed(
                    title="Authorization Error",
                    description="You are not authorized to perform this action.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            await interaction.client.post_closer.cancel_close(self.thread.id)

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
                await self.bot.db.remove_view(interaction.message.id)
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
            close_time = await process_solved_thread(self.thread, interaction.client)

            original_embed = interaction.message.embeds[0]
            original_embed.title = f"~~{original_embed.title}~~"
            if original_embed.description:
                parts = original_embed.description.split('\n\n')  # Split on double newlines to preserve formatting
                struck_parts = []
                for part in parts:
                    if "NOT solved" in part or not any("~~" in line for line in part.split('\n')):
                        struck_parts.append(f"~~{part}~~")
                    else:
                        struck_parts.append(part)
                original_embed.description = '\n\n'.join(struck_parts)

            await interaction.message.edit(embed=original_embed, view=None)

            new_embed = discord.Embed(
                title="Post Solved",
                description=f"{interaction.user.mention} marked this post as solved.\nIt will be automatically closed and locked <t:{close_time}:R>.",
                color=discord.Color.green()
            )
            view = ui.View(timeout=None)
            view.add_item(NotSolvedButton(self.bot, self.thread))

            new_message = await interaction.followup.send(embed=new_embed, view=view)
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
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("This command can only be used in a thread.", ephemeral=True)
            return
        thread: discord.Thread = interaction.channel

        # Determine channel type and tag
        is_support = thread.parent.id == SUPPORT_CHANNEL_ID
        is_community = thread.parent.id == COMMUNITY_SUPPORT_CHANNEL_ID
        if not is_support and not is_community:
            await interaction.response.send_message(
                "This command is only for the support channels.", ephemeral=True
            )
            return

        # Check permissions by determining the post owner.
        starter = await thread.fetch_message(thread.id)
        is_owner = False
        if not starter.author.bot:
            is_owner = (starter.author.id == interaction.user.id)
        else:
            if starter.mentions:
                is_owner = (starter.mentions[0].id == interaction.user.id)
        has_auth = any(role.id == AUTHORIZED_ROLE_ID for role in getattr(interaction.user, 'roles', []))
        if not (is_owner or has_auth):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="No Permission",
                    description="You are not authorized to perform this action.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Common tag fetch
        solved_tag = None
        if is_support:
            solved_tag = thread.parent.get_tag(SOLVED_TAG_ID)
        else:
            solved_tag = thread.parent.get_tag(COMMUNITY_SOLVED_TAG_ID)
        if not solved_tag:
            await interaction.response.send_message("Solved tag not found.", ephemeral=True)
            return

        # Already solved check
        if solved_tag in thread.applied_tags:
            title = "Post Already Solved"
            desc = "This post is already marked as solved."
            await interaction.response.send_message(
                embed=discord.Embed(title=title, description=desc, color=discord.Color.green()),
                ephemeral=True
            )
            return

        await interaction.response.defer()

        # Edit tags: preserve others, add solved tag
        new_tags = [t for t in thread.applied_tags if t.id != (COMMUNITY_SOLVED_TAG_ID if is_community else SOLVED_TAG_ID)]
        new_tags.append(solved_tag)
        await thread.edit(applied_tags=new_tags, reason="Marking post as solved")

        if is_support:
            close_time = await process_solved_thread(thread, interaction.client)
            embed = discord.Embed(
                title="Post Solved",
                description=f"{interaction.user.mention} marked this post as solved.\nIt will be automatically closed and locked <t:{close_time}:R>.",
                color=discord.Color.green()
            )
            view = ui.View()
            view.add_item(NotSolvedButton(self.bot, thread))
            await interaction.followup.send(embed=embed, view=view)
        else:
            embed = discord.Embed(
                title="Post Solved",
                description=f"{interaction.user.mention} marked this community post as solved.",
                color=discord.Color.green()
            )
            view = ui.View()
            view.add_item(CommunityNotSolvedButton(self.bot, thread))
            await interaction.followup.send(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(SolvePost(bot))
