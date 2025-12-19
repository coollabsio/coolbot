import discord
from discord.ext import commands
from discord import app_commands
from config import UNANSWERED_TAG_ID, NOT_SOLVED_TAG_ID, WAITING_FOR_REPLY_TAG_ID
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def autocomplete_doc_search(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    docs = await interaction.client.db.get_doc_entries()  # type: ignore
    return [app_commands.Choice(name=doc['name'], value=doc['name']) for doc in docs if current.lower() in doc['name'].lower()][:25]

class DocUserPickerView(discord.ui.View):
    """
    View to pick a user to ping with doc results.
    """
    def __init__(self, post: discord.Thread, executor: discord.Member, bot: commands.Bot, query: str, results: list):
        super().__init__(timeout=60)
        self.post = post
        self.executor = executor
        self.bot = bot
        self.query = query
        self.results = results

        self.select = discord.ui.Select(
            placeholder="Select a user to ping",
            min_values=1,
            max_values=1,
            options=[]
        )
        self.select.callback = self.on_user_select
        self.add_item(self.select)

    async def setup_options(self):
        """Setup the select options after initialization"""
        options = []
        try:
            members = await self.post.fetch_members()
            if members:
                for m in members:
                    full_member = self.post.guild.get_member(m.id) or m
                    label = getattr(full_member, "display_name", str(full_member))
                    options.append(discord.SelectOption(label=label, value=str(m.id)))
                options.append(discord.SelectOption(
                    label="No ping",
                    value="none",
                    description="Send without pinging anyone"
                ))
            else:
                options = [
                    discord.SelectOption(
                        label="No members available",
                        value="none",
                        default=True,
                        description="No members are following this post."
                    )
                ]
        except Exception as e:
            logger.error(f"Failed to fetch thread members: {e}")
            options = [
                discord.SelectOption(
                    label="Error fetching members",
                    value="error",
                    default=True,
                    description="Could not load members."
                )
            ]

        self.select.options = options

    async def on_user_select(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected = self.select.values[0]

        target_user = None
        if selected not in ["none", "error"]:
            target_user = self.post.guild.get_member(int(selected))
            if not target_user:
                return await interaction.followup.send("User not found.", ephemeral=True)

        # Send the doc results
        await self.send_doc_results(interaction, target_user)

        # Remove tags
        await self.update_thread_tags()

        await interaction.delete_original_response()
        self.stop()

    async def send_doc_results(self, interaction: discord.Interaction, target_user: Optional[discord.Member] = None):
        """Send the documentation results to the thread"""
        response_message = ""
        for entry in self.results:
            if target_user:
                message = f"Hey {target_user.mention}, please follow this guide to solve your issue: {entry['link']}"
                if "youtube.com" in entry['link'].lower():
                    message = f"Hey {target_user.mention}, please follow this video tutorial to solve your issue: {entry['link']}"
            else:
                message = f"Please follow this guide to solve your issue: {entry['link']}"
                if "youtube.com" in entry['link'].lower():
                    message = f"Please follow this video tutorial to solve your issue: {entry['link']}"
            response_message += f"{message}\n"

        await self.post.send(response_message, suppress_embeds=True)

    async def update_thread_tags(self):
        """Update thread tags after responding"""
        applied_tags = self.post.applied_tags
        tags_to_remove_ids = [WAITING_FOR_REPLY_TAG_ID, UNANSWERED_TAG_ID]

        unanswered_tag_removed = False
        new_tags = []
        for tag in applied_tags:
            if tag.id not in tags_to_remove_ids:
                new_tags.append(tag)
            if tag.id == UNANSWERED_TAG_ID:
                unanswered_tag_removed = True

        if unanswered_tag_removed:
            if self.post.parent and isinstance(self.post.parent, discord.ForumChannel):
                not_solved_tag = self.post.parent.get_tag(NOT_SOLVED_TAG_ID)
                if not_solved_tag:
                    new_tags.append(not_solved_tag)

        if len(new_tags) != len(applied_tags):
            await self.post.edit(applied_tags=new_tags, reason="Bot responded, removed awaiting response and/or unanswered tag")

class DocSearch(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="doc-search", description="Search documentation")
    @app_commands.guild_only()
    @app_commands.autocomplete(query=autocomplete_doc_search)
    async def doc_search(self, interaction: discord.Interaction, query: str):
        docs = await self.bot.db.get_doc_entries()  # type: ignore
        results = []
        for entry in docs:
            if query.lower() in entry['name'].lower():
                results.append(entry)

        if not results:
            await interaction.response.send_message("No matching documents found.", ephemeral=True)
            return

        if not isinstance(interaction.channel, discord.Thread):
            # Not in a thread - send directly
            await interaction.response.defer()
            response_message = ""
            for entry in results:
                message = f"Please follow this guide to solve your issue: {entry['link']}"
                if "youtube.com" in entry['link'].lower():
                    message = f"Please follow this video tutorial to solve your issue: {entry['link']}"
                response_message += f"{message}\n"
            await interaction.followup.send(response_message, suppress_embeds=True)
            return

        # In a thread - show user picker
        embed = discord.Embed(
            title="Select User to Ping",
            description="Choose a user to notify with the documentation link.",
            color=discord.Color.blue()
        )
        view = DocUserPickerView(interaction.channel, interaction.user, self.bot, query, results)  # type: ignore
        await view.setup_options()
        embed.description = "Choose a user to notify with the documentation links, or select 'No ping' to send without mentioning anyone."
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(DocSearch(bot))