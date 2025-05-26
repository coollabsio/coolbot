import discord
from discord.ext import commands
from config import (
    SUPPORT_CHANNEL_ID,
    UNANSWERED_TAG_ID,
    SOLVED_TAG_ID,
    NOT_SOLVED_TAG_ID,
    WAITING_FOR_REPLY_TAG_ID
)

class AutoAddCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle new threads, replies, and update tags accordingly."""
        if not isinstance(message.channel, discord.Thread) or message.channel.parent_id != SUPPORT_CHANNEL_ID:
            return
        if message.id == message.channel.id:
            await self.handle_new_thread(message)  # Pass the starter message instead of the thread
        elif message.author != self.bot.user:
            await self.handle_reply(message)
            await self.update_waiting_tag(message.channel)

    async def handle_new_thread(self, message: discord.Message):
        """Add 'Unanswered' tag and send a support embed to new threads, if applicable."""
        thread = message.channel  # The thread is the message's channel
        unanswered_tag = thread.parent.get_tag(UNANSWERED_TAG_ID)
        if unanswered_tag and unanswered_tag not in thread.applied_tags:
            new_tags = thread.applied_tags + [unanswered_tag]
            await thread.edit(applied_tags=new_tags)
        if message.author != self.bot.user:  # Only send embed if the starter message isn't from the bot
            support_embed = discord.Embed(title="Note", description=(
                "Please remember that everyone in this server helps others voluntarily.\n\n"
                "Do not ping anyone (including Admins, Mods, Community Experts, or Developers) for attention, "
                "and avoid posting your question or request in any other channel.\n\n"
                "Failure to follow these guidelines may result in temporary exclusion from the server.\n\n"
                "While you wait, you can refer to our [documentation](https://coolify.io/docs/) for potential solutions."
            ))
            await thread.send(embed=support_embed)

    async def handle_reply(self, message: discord.Message):
        """Replace 'Unanswered' with 'Not Solved' when someone replies, if applicable."""
        thread = message.channel
        applied_tags = thread.applied_tags
        unanswered_tag = thread.parent.get_tag(UNANSWERED_TAG_ID)
        not_solved_tag = thread.parent.get_tag(NOT_SOLVED_TAG_ID)
        if unanswered_tag in applied_tags and not_solved_tag:
            post_creator = await self.get_post_creator(thread)
            if message.author != post_creator:
                new_tags = [tag for tag in applied_tags if tag != unanswered_tag] + [not_solved_tag]
                await thread.edit(applied_tags=new_tags)

    async def update_waiting_tag(self, thread: discord.Thread):
        """Add or remove 'Waiting for Reply' tag based on the last message and post status."""
        post_creator = await self.get_post_creator(thread)
        async for msg in thread.history(limit=1):
            last_message = msg
        waiting_tag = thread.parent.get_tag(WAITING_FOR_REPLY_TAG_ID)
        unanswered_tag = thread.parent.get_tag(UNANSWERED_TAG_ID)
        solved_tag = thread.parent.get_tag(SOLVED_TAG_ID)
        if not waiting_tag or not unanswered_tag:
            return
        if solved_tag in thread.applied_tags:
            return     
        is_unanswered = unanswered_tag in thread.applied_tags
        if last_message.author == post_creator:
            if not is_unanswered and waiting_tag not in thread.applied_tags:
                new_tags = thread.applied_tags + [waiting_tag]
                await thread.edit(applied_tags=new_tags)
        else:
            if waiting_tag in thread.applied_tags:
                new_tags = [tag for tag in thread.applied_tags if tag != waiting_tag]
                await thread.edit(applied_tags=new_tags)

    async def get_post_creator(self, thread: discord.Thread) -> discord.Member:
        """Determine the actual creator of the post, accounting for bot-created threads."""
        starter_message = await thread.fetch_message(thread.id)
        if starter_message and starter_message.author == self.bot.user:
            mentions = starter_message.mentions
            if mentions:
                return mentions[0]
        return thread.owner

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoAddCog(bot))