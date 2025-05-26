import discord
from discord.ext import commands
from discord import app_commands

from config import (
    SUPPORT_CHANNEL_ID,
    COMMUNITY_SUPPORT_CHANNEL_ID,
    AUTHORIZED_ROLE_ID,
    SOLVED_TAG_ID,
)

class MovePost(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_support_embed(self, thread_msg: discord.Message):
        embed = discord.Embed(title="Note")
        embed.description = (
            "This post has been moved here to the Community support channel as it doesn’t fall within the scope of the Support channel..\n\n"
            "Please remember that everyone in this server helps others voluntarily.\n\n"
            "Do not ping anyone (including Admins, Mods, Community Experts, or Developers) for attention, "
            "and avoid posting your question or request in any other channel.\n\n"
            "Failure to follow these guidelines may result in temporary exclusion from the server.\n\n"
            "While you wait, you can refer to our [documentation](https://coolify.io/docs/) for potential solutions to your issue."
        )
        await thread_msg.channel.send(embed=embed)

    @app_commands.command(name="move_to_community_support", description="Move the current support post to Community Support channel.")
    async def move_community(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not isinstance(interaction.channel, discord.Thread) or \
           interaction.channel.parent_id != SUPPORT_CHANNEL_ID:
            await interaction.followup.send(
                "This command must be used inside a Support post.",
                ephemeral=True
            )
            return

        thread = interaction.channel
        starter = await thread.fetch_message(thread.id)
        is_owner = (starter.author.id == interaction.user.id)
        has_role = any(role.id == AUTHORIZED_ROLE_ID for role in getattr(interaction.user, 'roles', []))
        if not (is_owner or has_role):
            await interaction.followup.send(
                "You are not authorized to move this support post.",
                ephemeral=True
            )
            return

        msgs = [starter]
        async for msg in thread.history(oldest_first=True, limit=None):
            if msg.id != starter.id:
                msgs.append(msg)

        content = "\n\n".join(m.content for m in msgs if m.content and m.content.strip())
        files = []
        for m in msgs:
            for att in m.attachments:
                try:
                    files.append(await att.to_file())
                except Exception:
                    pass

        forum = self.bot.get_channel(COMMUNITY_SUPPORT_CHANNEL_ID)
        if not isinstance(forum, discord.ForumChannel):
            await interaction.followup.send(
                "Community Support channel not found or invalid.",
                ephemeral=True
            )
            return

        title = thread.name or f"Support request from {starter.author.name}"
        initial = f"{starter.author.mention} needs assistance from the Community!"
        if content:
            initial += f"\n\n__**Original Message:**__\n{content}"
        if files:
            initial += f"\n\nAttached {len(files)} file(s)"
        initial += f"\n\n-# This post is moved by {interaction.user.mention}"

        new_thread = await forum.create_thread(
            name=title,
            content=initial,
            files=files
        )
        thread_msg = new_thread.message

        if thread_msg:
            await self.send_support_embed(thread_msg)
        try:
            solved_tag = thread.parent.get_tag(SOLVED_TAG_ID)
            if solved_tag:
                await thread.edit(applied_tags=[solved_tag])

            await thread.send(
                f"Hey {starter.author.mention}, your support post has been moved to Community support channel. Please continue on: {thread_msg.jump_url}"
            )

            await thread.edit(
                name=f"[ Moved to Community ] {thread.name}",
                archived=True,
                locked=True
            )
        except Exception:
            pass

        success_embed = discord.Embed(
            title="Post moved successfully",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=success_embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(MovePost(bot))
