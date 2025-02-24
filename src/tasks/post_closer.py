import asyncio
import discord
from typing import Optional

class PostCloser:
    def __init__(self, bot):
        self.bot = bot
        self.close_tasks = {}

    async def initialize_tasks(self):
        """Load and start pending close tasks from database"""
        tasks = await self.bot.db.get_pending_closes()
        for task in tasks:
            thread_id = task['thread_id']
            channel = self.bot.get_channel(thread_id)
            if channel and isinstance(channel, discord.Thread):
                if not (channel.locked or channel.archived):
                    self.close_tasks[thread_id] = asyncio.create_task(
                        self.close_post(channel, task['close_at'])
                    )
                else:
                    await self.bot.db.remove_close_task(thread_id)

    async def schedule_close(self, thread: discord.Thread, delay: int = 3600):
        """Schedule a thread to be closed after the specified delay"""
        if thread.id in self.close_tasks:
            self.close_tasks[thread.id].cancel()
        
        self.close_tasks[thread.id] = asyncio.create_task(
            self.close_post(thread, delay)
        )
        await self.bot.db.add_close_task(thread.id, delay)

    async def cancel_close(self, thread_id: int):
        """Cancel a scheduled thread close"""
        if thread_id in self.close_tasks:
            self.close_tasks[thread_id].cancel()
            self.close_tasks.pop(thread_id)
        await self.bot.db.remove_close_task(thread_id)

    async def close_post(self, thread: discord.Thread, delay: int):
        """Close and lock a thread after the specified delay"""
        await asyncio.sleep(delay)
        try:
            await thread.edit(archived=True, locked=True, reason="Auto archive solved post")
            print(f"Thread {thread.id} archived and locked.")
        except Exception as e:
            print(f"Error archiving thread {thread.id}: {e}")
        finally:
            self.close_tasks.pop(thread.id, None)
            await self.bot.db.remove_close_task(thread.id)
