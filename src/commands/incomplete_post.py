import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta, timezone
from utils.database import Database
from config import (
    SUPPORT_CHANNEL_ID,
    SOLVED_TAG_ID,
    COOLIFY_CLOUD_TAG_ID,
    AUTHORIZED_ROLE_ID
)

class IncompletePostView(ui.View):
    """Persistent view for incomplete-post notifications."""
    def __init__(self, bot: commands.Bot, thread: discord.Thread, owner_id: int, message_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.thread = thread
        self.owner_id = owner_id
        self.message_id = message_id
        self.timer_task = None

    async def start_timer(self, delay: float = 12 * 3600):
        """Start the auto-close timer and record delay in pending_closes."""
        await self.bot.db.add_close_task(self.thread.id, int(delay))
        # Schedule auto-close
        self.timer_task = asyncio.create_task(self._auto_close(delay))

    async def _auto_close(self, delay: float):
        await asyncio.sleep(delay)
        try:
            parent = self.thread.parent
            solved_tag = parent.get_tag(SOLVED_TAG_ID)
            coolify = parent.get_tag(COOLIFY_CLOUD_TAG_ID)
            new_tags = []
            if solved_tag:
                new_tags.append(solved_tag)
            if coolify and coolify in self.thread.applied_tags:
                new_tags.append(coolify)
            # Lock first
            await self.thread.edit(locked=True)
            # Send closure message before archiving (to avoid auto-unarchive)
            await self.thread.send(
                embed=discord.Embed(
                    title="Post automatically closed",
                    description="No response from the post owner, so marking this as solved.",
                    color=discord.Color.green()
                )
            )
            # Archive and apply solved tag
            await self.thread.edit(applied_tags=new_tags, archived=True)
            # Cleanup DB
            await self.bot.db.remove_view(self.message_id)
            await self.bot.db.remove_close_task(self.thread.id)
        except Exception as e:
            print(f"Error auto-closing incomplete-post: {e}")
        finally:
            self.bot.incomplete_views.pop(self.thread.id, None)

    async def handle_response(self):
        """Handle post-owner’s reply: cancel close and thank them."""
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        await self.bot.db.remove_close_task(self.thread.id)
        try:
            msg = await self.thread.fetch_message(self.message_id)
            embed = msg.embeds[0]
            embed.title = f"~~{embed.title}~~"
            embed.description = (
                f"~~{embed.description}~~\n\n"
                "Thanks for providing the details! Your post will not be closed automatically."
            )
            await msg.edit(content=None, embed=embed, view=None)
            await self.bot.db.mark_view_solved(self.message_id, True)
        except Exception as e:
            print(f"Error handling response for incomplete-post: {e}")
        finally:
            self.bot.incomplete_views.pop(self.thread.id, None)

class IncompletePost(commands.Cog):
    """Cog implementing the /incomplete-post command, with persistent DB backing."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.incomplete_views = {}

    @app_commands.command(name="incomplete-post", description="Mark the current post as incomplete and request more info.")
    async def incomplete_post(self, interaction: discord.Interaction):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread) or thread.parent_id != SUPPORT_CHANNEL_ID:
            return await interaction.response.send_message(
                "This command can only be used in a support thread.", ephemeral=True)

        starter = await thread.fetch_message(thread.id)
        owner_id = starter.author.id if not starter.author.bot else (
            starter.mentions[0].id if starter.mentions else thread.owner_id
        )
        user = interaction.user
        is_owner = user.id == owner_id
        has_auth = any(r.id == AUTHORIZED_ROLE_ID for r in getattr(user, 'roles', []))
        if not (is_owner or has_auth):
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title="No Permission",
                    description="You are not authorized to mark this post as incomplete.",
                    color=discord.Color.red()
                ), ephemeral=True
            )

        delay_seconds = 12 * 3600
        future_ts = int((datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).timestamp())
        embed = discord.Embed(
            title="Incomplete support post",
            description=(
                "We’re happy to help, but we need a bit more info first.\n\n"
                f"Please take a moment to read the pinned post ( https://discord.com/channels/459365938081431553/1376791448657203201 ) and share the required details <t:{future_ts}:R>.\n\n"
                f"The post will close automatically if you do not respond."
            ),
            color=discord.Color.orange()
        )

        await interaction.response.send_message("Notification sent!", ephemeral=True)
        sent = await thread.send(
            content=f"Hey <@{owner_id}>!",
            embed=embed
        )
        view = IncompletePostView(self.bot, thread, owner_id, sent.id)
        await sent.edit(view=view)
        await view.start_timer(delay_seconds)

        await self.bot.db.add_view(
            message_id=sent.id,
            channel_id=thread.parent_id,
            thread_id=thread.id,
            view_type="incomplete",
            post_owner_id=owner_id,
            is_solved=False
        )
        self.bot.incomplete_views[thread.id] = view

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not isinstance(message.channel, discord.Thread):
            return
        view = self.bot.incomplete_views.get(message.channel.id)
        if view and message.author.id == view.owner_id:
            await view.handle_response()

async def setup(bot: commands.Bot):
    if not hasattr(bot, 'db'):
        bot.db = Database()
        await bot.db.init()
    await bot.add_cog(IncompletePost(bot))
