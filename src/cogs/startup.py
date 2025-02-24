import discord
from discord.ext import commands
from datetime import datetime

from config import STARTUP_LOG_THREAD_ID

class StartupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await self.send_startup_log()

    async def send_startup_log(self):
        thread = self.bot.get_channel(STARTUP_LOG_THREAD_ID)
        if thread:
            # Using datetime.now() to capture local time
            timestamp = int(datetime.now().timestamp())
            message = f"[ <t:{timestamp}:T> (<t:{timestamp}:R>) ] {self.bot.user.name} connected to Discord!"
            await thread.send(message)
        else:
            print(f"Warning: Startup log thread with ID {STARTUP_LOG_THREAD_ID} not found.")

async def setup(bot: commands.Bot):
    await bot.add_cog(StartupCog(bot))
