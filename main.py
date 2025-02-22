import discord
from discord.ext import commands
import asyncio
from pathlib import Path

from config import TOKEN

intents = discord.Intents.all()  # Enable all intents
bot = commands.Bot(command_prefix="c!", intents=intents)

async def load_extensions(bot: commands.Bot):
    # List the directories you want to load extensions from.
    directories = ["cogs", "commands"]
    for directory in directories:
        path = Path(f"./{directory}")
        # Look for Python files in the directory (non-recursively).
        for ext in path.glob("*.py"):
            if ext.name == "__init__.py":
                continue  # Skip __init__.py files
            module_name = f"{directory}.{ext.stem}"
            try:
                await bot.load_extension(module_name)
                print(f"Loaded extension: {module_name}")
            except Exception as e:
                print(f"Failed to load extension {module_name}: {e}")

@bot.event
async def on_ready():
    synced_commands = await bot.tree.sync()
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="coolLabs"))
    print(f"Successfully synced {len(synced_commands)} commands")
    print(f"{bot.user} has connected to Discord!")

async def main():
    async with bot:
        await load_extensions(bot)
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
