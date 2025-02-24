import discord
from discord.ext import commands
import re
import asyncio
from config import SUPPORT_CHANNEL_ID, SOLVED_TAG_ID
from commands.solved import SolvedButton

suggested_threads = set()

class SuggestionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_post_owner_id(self, thread: discord.Thread) -> int:
        """
        Fetch the starter message to determine the actual post owner.
        If the starter was sent by the bot, and it mentioned a user,
        then return that mentioned user's ID.
        Otherwise, return the author of the starter message or thread owner.
        """
        try:
            starter = await thread.fetch_message(thread.id)
        except Exception:
            return thread.owner_id
        if not starter.author.bot:
            return starter.author.id
        elif starter.mentions:
            return starter.mentions[0].id
        else:
            return thread.owner_id

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if not isinstance(message.channel, discord.Thread):
                return
            if message.channel.parent_id != SUPPORT_CHANNEL_ID:
                return

            # Ignore if thread is locked or archived.
            if message.channel.archived or message.channel.locked:
                return

            # Ignore the starter message (often has ID equal to thread ID).
            if message.id == message.channel.id:
                return

            # Determine the actual post owner.
            actual_owner_id = await self.get_post_owner_id(message.channel)
            if message.author.id != actual_owner_id:
                return

            # Check if a suggestion was already sent in this thread.
            if message.channel.id in suggested_threads:
                return

            # If the post is already marked as solved, do nothing.
            solved_tag = message.channel.parent.get_tag(SOLVED_TAG_ID)
            if solved_tag in message.channel.applied_tags:
                return

            content = message.content.lower()
            if not content:
                return

            # Define regex patterns.
            positive_pattern = r'(^solved$|solved\b|^ty$|\sty|thank|work|fixed|thx|tysm|appreciate|resolved|success|cheers|issue resolved|thank you|helped|problem solved|finally|woohoo)'
            negative_pattern = r"(doesn'?t|isn'?t|not?|but|before|won't|still|yet|having trouble|still having issues|no|never|wrong|nope|not quite|not really|unfortunately|regrettably|sadly)"

            # Do not send a suggestion if negative phrases are detected.
            if re.search(negative_pattern, content, re.IGNORECASE):
                return

            # Only proceed if the message matches the positive indicators.
            if not re.search(positive_pattern, content, re.IGNORECASE):
                return

            # Build the suggestion embed and view
            embed = discord.Embed(
                title="Mark as Solved?",
                description=(
                    "It looks like your issue might be solved. "
                    "If that's the case, please click the button below to mark this post as solved."
                ),
                color=discord.Color.green()
            )
            
            # Create the button and add it to the view
            solved_button = SolvedButton(self.bot, message.channel)
            view = discord.ui.View(timeout=None)
            view.add_item(solved_button)

            try:
                sent_message = await message.reply(
                    embed=embed,
                    view=view,
                    mention_author=True,
                    allowed_mentions=discord.AllowedMentions(
                        users=True,
                        roles=False,
                        everyone=False
                    )
                )
                suggested_threads.add(message.channel.id)
            except (discord.Forbidden, discord.HTTPException, Exception):
                pass

        except Exception:
            pass

async def setup(bot: commands.Bot):
    await bot.add_cog(SuggestionCog(bot))
