import discord
from discord.ext import commands
from discord import app_commands
import logging

from config import (
    PRIVATE_DATA_THREAD_ID,
    AUTHORIZED_ROLE_ID
)

logger = logging.getLogger(__name__)

async def forward_private_details(submitter: discord.Member, executor: discord.Member, bot: commands.Bot, details: str, thread: discord.Thread):
    """
    Forwards the submitted details to the private data thread as an embed, pinging the executor.
    """
    private_thread = bot.get_channel(PRIVATE_DATA_THREAD_ID)
    if private_thread is None:
        logger.error(f"Private data thread {PRIVATE_DATA_THREAD_ID} not found.")
        return

    post_link = f"https://discord.com/channels/{submitter.guild.id}/{thread.id}"

    embed = discord.Embed(
        description=(
            f"- From:\n"
            f"  - {submitter.mention}\n"
            f"- Submission\n"
            f"  - {details or '*No content provided*'}\n"
            f"- Link to post\n"
            f"  - {post_link}"
        ),
        color=discord.Color.blurple()
    )
    try:
        await private_thread.send(
            content=f"Hey {executor.mention}, you have received a submission.",
            embed=embed
        )
    except Exception as e:
        logger.error(f"Failed to send to private data thread: {e}")

class PrivateSubmitView(discord.ui.View):
    """
    Button view for the selected user to submit private details.
    """
    def __init__(self, executor: discord.Member, target: discord.Member, bot: commands.Bot, prompt: str):
        super().__init__(timeout=None)
        self.executor = executor
        self.target = target
        self.bot = bot
        self.prompt = prompt

    @discord.ui.button(label="Submit Information", style=discord.ButtonStyle.primary, custom_id="private_submit")
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message(
                "You are not authorized to submit this information.", ephemeral=True
            )
        modal = PrivateInfoModal(self.executor, self.target, self.bot, self.prompt, interaction.message, interaction.channel)
        await interaction.response.send_modal(modal)

class PrivateInfoModal(discord.ui.Modal, title="Provide Private Details"):
    """
    Modal to collect one field of private details.
    """
    def __init__(self, executor: discord.Member, target: discord.Member, bot: commands.Bot, prompt: str, original_msg: discord.Message, thread: discord.Thread):
        super().__init__()
        self.executor = executor
        self.target = target
        self.bot = bot
        self.prompt = prompt
        self.original_msg = original_msg
        self.thread = thread

        self.details = discord.ui.TextInput(
            label=prompt,
            style=discord.TextStyle.long,
            placeholder="Type your response here...",
            required=True
        )
        self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction):
        content = self.details.value
        await forward_private_details(self.target, self.executor, self.bot, content, self.thread)
        try:
            await self.original_msg.edit(
                embed=discord.Embed(
                    description=f"{self.executor.mention} received your submission.",
                    color=discord.Color.green()
                ),
                view=None
            )
        except Exception as e:
            logger.error(f"Failed to edit original submission message: {e}")
        await interaction.response.defer()  # silently close modal without a message

class UserPickerView(discord.ui.View):
    """
    View to pick a user to request private details from.
    """
    def __init__(self, post: discord.Thread, executor: discord.Member, bot: commands.Bot, members: list):
        super().__init__(timeout=60)
        self.post = post
        self.executor = executor
        self.bot = bot
        options = []
        if members:
            for m in members:
                full_member = self.post.guild.get_member(m.id) or m
                label = getattr(full_member, "display_name", str(full_member))
                options.append(discord.SelectOption(label=label, value=str(m.id)))
        else:
            options = [
                discord.SelectOption(
                    label="No members available",
                    value="none",
                    default=True,
                    description="No members are following this post."
                )
            ]
        self.select = discord.ui.Select(
            placeholder="Select a user",
            min_values=1,
            max_values=1,
            options=options
        )
        self.select.callback = self.on_user_select
        self.add_item(self.select)

    async def on_user_select(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected = self.select.values[0]
        if selected == "none":
            return await interaction.followup.send("No valid members available.", ephemeral=True)
        selected_user = self.post.guild.get_member(int(selected))
        if not selected_user:
            return await interaction.followup.send("User not found.", ephemeral=True)

        embed = discord.Embed(
            description=f"{self.executor.mention} needs some details from you. Please click the button below to submit.",
            color=discord.Color.yellow()
        )
        view = PrivateSubmitView(self.executor, selected_user, self.bot, prompt="Details:")
        await self.post.send(content=f"Hey {selected_user.mention}!", embed=embed, view=view)
        await interaction.delete_original_response()  # closes the ephemeral picker message
        self.stop()

class PrivateDetailsCog(commands.Cog):
    """
    Cog to handle private-details command.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="request-private-details", description="Request private details from a user")
    async def private_details(self, interaction: discord.Interaction):
        if AUTHORIZED_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
        if not isinstance(interaction.channel, discord.Thread):
            return await interaction.response.send_message(
                "This command can only be used in a thread.", ephemeral=True
            )

        post = interaction.channel
        try:
            members = await post.fetch_members()
        except Exception as e:
            logger.error(f"Failed to fetch thread members: {e}")
            members = []

        embed = discord.Embed(
            title="Request Private Details",
            description="Select the user to request private details from.",
            color=discord.Color.blue()
        )
        view = UserPickerView(post, interaction.user, self.bot, members)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(PrivateDetailsCog(bot))
