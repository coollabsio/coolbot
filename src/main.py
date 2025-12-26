import discord
from discord.ext import commands
import asyncio
from pathlib import Path
import sys
import os

from config import TOKEN
# Ensure the src directory is on the Python path
sys.path.append(str(Path(__file__).parent))

from utils.database import Database
from tasks.post_closer import PostCloser
from tasks.docs_sync import DocsSync
from tasks.contributors_sync import ContributorsSync
from utils.view_loader import load_persistent_views

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="c!", intents=intents)
bot.post_closer = PostCloser(bot)
bot.docs_sync = DocsSync(bot)
bot.contributors_sync = ContributorsSync(bot)

async def load_extensions(bot: commands.Bot):
    base_path = Path(__file__).parent.absolute()
    directories = ["cogs", "commands"]
    for directory in directories:
        path = base_path / directory
        if not path.exists():
            print(f"Warning: Directory {path} does not exist")
            continue
        sys.path.append(str(base_path))
        for ext in path.glob("*.py"):
            if ext.name == "__init__.py":
                continue
            relative_path = ext.relative_to(base_path)
            module_name = str(relative_path).replace(os.sep, ".")[:-3]  # Remove .py
            if module_name in bot.extensions:
                print(f"Skipping already loaded extension: {module_name}")
                continue
            try:
                await bot.load_extension(module_name)
                print(f"Loaded extension: {module_name}")
            except Exception as e:
                print(f"Failed to load extension {module_name}: {type(e).__name__}: {e}")

async def setup_database(bot):
    bot.db = Database()
    await bot.db.init()
    print("Database initialized")

@bot.event
async def on_connect():
    print("Bot connected to Discord (on_connect event)")

@bot.event
async def on_ready():
    # Run on_ready tasks only once
    if getattr(bot, "ready", False):
        return
    bot.ready = True
    print("Bot is ready, executing on_ready tasks...")
    try:
        await bot.post_closer.initialize_tasks()
    except Exception as e:
        print(f"Error initializing post_closer tasks: {e}")
    try:
        await bot.docs_sync.initialize_tasks()
    except Exception as e:
        print(f"Error initializing docs_sync tasks: {e}")
    try:
        await bot.contributors_sync.initialize_tasks()
    except Exception as e:
        print(f"Error initializing contributors_sync tasks: {e}")
    try:
        await load_persistent_views(bot)
    except Exception as e:
        print(f"Error loading persistent views: {e}")
    try:
        synced_commands = await bot.tree.sync()
        print(f"Successfully synced {len(synced_commands)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    try:
        await asyncio.sleep(1)  # slight delay to avoid race conditions
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="coolLabs"))
        print(f"{bot.user} has connected to Discord!")
    except Exception as e:
        print(f"Error setting presence: {e}")

async def main():
    await setup_database(bot)
    async with bot:
        await load_extensions(bot)
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
