import discord
from discord.ext import commands, tasks
import typing
import asyncio
from config import (
    SUPPORT_CHANNEL_ID,
    AUTHORIZED_ROLE_ID,
    SOLVED_TAG_ID,
    COOLIFY_CLOUD_TAG_ID
)
from datetime import datetime, timedelta, timezone

class ConfirmCloseView(discord.ui.View):
    def __init__(self, bot: commands.Bot, post: discord.Thread, authorized_role_id: int, post_owner_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.post = post
        self.authorized_role_id = authorized_role_id
        self.post_owner_id = post_owner_id
        self.timer_task = None
        self.message = None
        self.custom_id = f"confirm_close_{post.id}"

    def is_authorized(self, user: discord.Member):
        return user.id == self.post_owner_id or any(role.id == self.authorized_role_id for role in user.roles)

    async def update_embed(self, interaction: discord.Interaction, solved: typing.Optional[bool]):
        embed = interaction.message.embeds[0]
        embed.title = f"~~{embed.title}~~"
        if solved is None:
            embed.description = f"~~{embed.description}~~\n\n<@{self.post_owner_id}> said this post is not solved, so we will keep it open."
        else:
            embed.description = f"~~{embed.description}~~\n\n<@{self.post_owner_id}> said this post is solved."
        await interaction.edit_original_response(embed=embed, view=None)

    async def start_timer(self):
        self.timer_task = asyncio.create_task(self.auto_close())

    async def auto_close(self):
        """Simple 5-minute timer for post auto-close"""
        await asyncio.sleep(300)  # 5 minutes
        try:
            # Close the thread after timer expires
            solved_tag = self.post.parent.get_tag(SOLVED_TAG_ID)
            coolify_tag = self.post.parent.get_tag(COOLIFY_CLOUD_TAG_ID)
            
            new_tags = [solved_tag]
            if coolify_tag and coolify_tag in self.post.applied_tags:
                new_tags.append(coolify_tag)

            await self.post.edit(applied_tags=new_tags, locked=True, archived=True)
            await self.post.send(
                embed=discord.Embed(
                    title="Post Automatically Closed",
                    description="This post has been marked as solved due to inactivity from the post owner.",
                    color=discord.Color.green()
                )
            )
            await self.bot.db.remove_view(self.message.id)
        except Exception as e:
            print(f"Error auto-closing thread: {e}")

    @discord.ui.button(label="Mark as Solved", style=discord.ButtonStyle.green, custom_id="confirm_solve")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_authorized(interaction.user):
            embed = discord.Embed(description="You are not authorized to close this post.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        
        if self.timer_task:
            self.timer_task.cancel()  # Stop timer since user confirmed manually
            
        solved_tag = interaction.channel.parent.get_tag(SOLVED_TAG_ID)
        coolify_tag = interaction.channel.parent.get_tag(COOLIFY_CLOUD_TAG_ID)
        
        new_tags = [solved_tag]
        if coolify_tag and coolify_tag in self.post.applied_tags:
            new_tags.append(coolify_tag)

        await self.post.edit(applied_tags=new_tags, archived=True, locked=True)
        await self.update_embed(interaction, solved=True)
        await self.bot.db.remove_view(interaction.message.id)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray, custom_id="confirm_cancel")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_authorized(interaction.user):
            embed = discord.Embed(description="You are not authorized to cancel this action.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        
        if self.timer_task:
            self.timer_task.cancel()  # Stop timer if user cancels
            
        await self.update_embed(interaction, solved=None)
        await self.bot.db.remove_view(interaction.message.id)

class AutoCloseCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if payload.message_id == payload.channel_id:
            thread = self.bot.get_channel(payload.channel_id)
            if isinstance(thread, discord.Thread) and thread.parent_id == SUPPORT_CHANNEL_ID:
                cached_message = payload.cached_message
                await self.handle_starter_delete(thread, cached_message)

    async def handle_starter_delete(self, thread: discord.Thread, cached_message: typing.Optional[discord.Message]):
        if thread.archived or thread.locked:
            return
        post_owner_id = await self.get_post_owner_id(thread, cached_message)
        future_timestamp = int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())
        embed = discord.Embed(
            title="First Message Deleted",
            description=f"The first message in this post has been deleted.\n\n**Would you like to mark this as solved?**\n\n*If no action is taken, this post will automatically close <t:{future_timestamp}:R>.*",
            color=discord.Color.orange()
        )
        view = ConfirmCloseView(self.bot, thread, AUTHORIZED_ROLE_ID, post_owner_id)
        message = await thread.send(content=f"Hey <@{post_owner_id}> !", embed=embed, view=view)
        view.message = message  
        
        # Add view to the database
        await self.bot.db.add_view(
            message_id=message.id,
            channel_id=thread.parent_id, 
            thread_id=thread.id, 
            view_type="confirm_close",
            post_owner_id=post_owner_id
        )
        
        self.bot.add_view(view, message_id=message.id)
        await view.start_timer()

    async def get_post_owner_id(self, thread: discord.Thread, cached_message: typing.Optional[discord.Message]) -> int:
        if cached_message:
            if cached_message.author == self.bot.user:
                if cached_message.mentions:
                    return cached_message.mentions[0].id
                return thread.owner_id
            return cached_message.author.id
        else:
            async for msg in thread.history(limit=1, oldest_first=True):
                if msg.author == self.bot.user and msg.mentions:
                    return msg.mentions[0].id
            return thread.owner_id

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # Check threads in the support channel for posts by the leaving member
        channel = self.bot.get_channel(SUPPORT_CHANNEL_ID)
        if not channel:
            return
        # Iterate over active threads in the support channel
        for thread in channel.threads:
            if thread.owner_id == member.id and not thread.archived and not thread.locked:
                future_timestamp = int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())
                embed = discord.Embed(
                    title="Post Owner Left",
                    description=(
                        f"<@{member.id}> has left the server.\n\n"
                        f"This post will automatically close <t:{future_timestamp}:R>."
                    ),
                    color=discord.Color.orange()
                )
                await thread.send(embed=embed)
                # Add close task to db
                await self.bot.db.add_close_task(thread.id, future_timestamp)
                self.bot.loop.create_task(self._owner_leave_auto_close(thread))

    async def _owner_leave_auto_close(self, thread: discord.Thread):
        await asyncio.sleep(300)  # 5 minutes delay
        try:
            solved_tag = thread.parent.get_tag(SOLVED_TAG_ID)
            coolify_tag = thread.parent.get_tag(COOLIFY_CLOUD_TAG_ID)
            new_tags = [solved_tag]
            if coolify_tag and coolify_tag in thread.applied_tags:
                new_tags.append(coolify_tag)
            await thread.edit(applied_tags=new_tags, locked=True, archived=True,)
            await thread.send(
                embed=discord.Embed(
                    title="Post Solved",
                    description="This post has been marked as solved since the owner left the server.",
                    color=discord.Color.green()
                )
            )
            # Remove close task from db
            await self.bot.db.remove_close_task(thread.id)
        except Exception as e:
            print(f"Error auto-closing thread on owner leave: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoCloseCog(bot))
