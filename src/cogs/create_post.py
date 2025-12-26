import discord
from discord.ext import commands
from discord.ui import View, button, Button

from config import (
    GENERAL_CHANNEL_ID,
    SUPPORT_CHANNEL_ID,
    COMMUNITY_SUPPORT_CHANNEL_ID,
    AUTHORIZED_ROLE_ID,
    POST_CREATE_LOG_THREAD_ID,
)

class ChannelSelectView(View):
    def __init__(self, cog, message, replied_message):
        super().__init__(timeout=60)
        self.cog = cog
        self.message = message
        self.replied_message = replied_message

    @button(label="Support Channel", style=discord.ButtonStyle.primary)
    async def support_channel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except:
            pass
        await self.cog.process_move(
            interaction,
            self.message,
            self.replied_message,
            target_channel_id=SUPPORT_CHANNEL_ID,
            assistance_text="needs assistance with Coolify"
        )
        self.stop()

    @button(label="Community Support Channel", style=discord.ButtonStyle.secondary)
    async def community_channel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except:
            pass
        await self.cog.process_move(
            interaction,
            self.message,
            self.replied_message,
            target_channel_id=COMMUNITY_SUPPORT_CHANNEL_ID,
            assistance_text="needs assistance from the Community"
        )
        self.stop()

class CreatePost(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # ignore our own messages
        if message.author == self.bot.user:
            return

        # only react in general when bot is mentioned on a reply
        if (
            message.channel.id == GENERAL_CHANNEL_ID
            and message.reference
            and self.bot.user in message.mentions
        ):
            authorized_role = discord.utils.get(
                message.guild.roles, id=AUTHORIZED_ROLE_ID
            )
            # delete pings from unauthorized users silently
            if authorized_role not in message.author.roles:
                await message.delete()
                return

            # fetch the original message and show embed with buttons
            replied = await message.channel.fetch_message(message.reference.message_id)
            view = ChannelSelectView(self, message, replied)
            embed = discord.Embed(description="Which channel would you like to move this message to?")
            await message.reply(
                embed=embed,
                mention_author=True,
                view=view
            )
            return
        await self.bot.process_commands(message)

    async def process_move(
        self,
        interaction: discord.Interaction,
        message: discord.Message,
        replied_message: discord.Message,
        target_channel_id: int,
        assistance_text: str
    ):
        try:
            # gather content and files
            msgs = await self.get_messages_to_move(message, replied_message)
            content = self.compile_content(msgs)
            files = await self.get_files(msgs)

            # validate target forum channel
            forum = self.bot.get_channel(target_channel_id)
            if not forum or not isinstance(forum, discord.ForumChannel):
                raise ValueError(f"Channel {target_channel_id} not found or not a ForumChannel")

            # build thread
            title = self.generate_title(msgs, replied_message)
            initial = f"{replied_message.author.mention} {assistance_text}!"
            if content:
                initial += f"\n\n__**Original Message:**__\n{content}"
            if files:
                initial += f"\n\nAttached **{len(files)}** files"

            thread = await forum.create_thread(
                name=title,
                content=initial,
                files=files
            )
            thread_msg = thread.message

            # post-move actions
            if thread_msg:
                await self.send_support_embed(thread_msg)
                await self.send_general_notification(replied_message, thread_msg)
                await self.send_log(message, replied_message, content, files, thread_msg)

            # cleanup originals
            await self.delete_original_messages(msgs)
            try:
                await message.delete()
            except:
                pass

        except Exception as e:
            await self.handle_error(e)

    async def get_messages_to_move(self, message, replied_message):
        msgs = [replied_message]
        async for msg in message.channel.history(
            limit=None,
            after=replied_message.created_at
        ):
            if msg.author == replied_message.author and msg.created_at < message.created_at:
                msgs.append(msg)
            elif msg.id == message.id:
                break
        return sorted(msgs, key=lambda m: m.created_at)

    def compile_content(self, messages):
        return "\n\n".join(m.content for m in messages if m.content.strip())

    def generate_title(self, messages, replied_message):
        snippet = messages[0].content or f"Support request from {replied_message.author.name}"
        return snippet[:100].strip() or "Support Request"

    async def get_files(self, messages):
        files = []
        for msg in messages:
            for att in msg.attachments:
                try:
                    files.append(await att.to_file())
                except discord.HTTPException:
                    print(f"Failed to download: {att.filename}")
        return files

    async def send_support_embed(self, thread_msg):
        embed = discord.Embed(title="Note")
        embed.description = (
            "Please remember that everyone in this community helps others voluntarily.\n\n"
            "Do not ping anyone (including Admins, Mods, Community Experts, or Developers) for attention, "
            "and avoid posting your question or request in any other channel.\n\n"
            "Failure to follow these guidelines may result in temporary exclusion from the community.\n\n"
            "While you wait, you can refer to our [documentation](https://coolify.io/docs/) for potential solutions to your issue."
        )
        await thread_msg.channel.send(embed=embed)

    async def send_general_notification(self, replied_message, thread_msg):
        gen = self.bot.get_channel(GENERAL_CHANNEL_ID)
        if gen:
          await gen.send(
              f"Hey {replied_message.author.mention}! We’ve moved your message to the support channel so it’s easier for everyone to assist. You can continue the conversation here: {thread_msg.jump_url}\n"
              "-# Friendly reminder: Using the support channels for questions (even quick yes/no ones) helps us get you answers faster and keeps things organized!"
          )


    async def send_log(self, message, replied_message, content, files, thread_msg):
        logs = self.bot.get_channel(POST_CREATE_LOG_THREAD_ID)
        if logs:
            log = discord.Embed(title="Post moved successfully.")
            log.add_field(name="Owner", value=replied_message.author.mention, inline=False)
            log.add_field(name="Moved by", value=message.author.mention, inline=False)
            log.add_field(name="Characters", value=len(content), inline=False)
            log.add_field(name="Attachments", value=f"{len(files)} files", inline=False)
            log.add_field(name="Location", value=thread_msg.jump_url, inline=False)
            await logs.send(embed=log)

    async def delete_original_messages(self, messages):
        for m in messages:
            try:
                await m.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

    async def handle_error(self, error):
        print(f"Error handling support request: {error}")
        logs = self.bot.get_channel(POST_CREATE_LOG_THREAD_ID)
        if logs:
            await logs.send(embed=discord.Embed(description=str(error)))

async def setup(bot: commands.Bot):
    await bot.add_cog(CreatePost(bot))
