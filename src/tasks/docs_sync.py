import asyncio

COOLBOT_JSON_URL = "https://next.coolify.io/docs/coolbot.json"

class DocsSync:
    def __init__(self, bot):
        self.bot = bot

    async def initialize_tasks(self):
        """Start the docs sync background task"""
        asyncio.create_task(self.docs_sync_loop())

    async def docs_sync_loop(self):
        """Periodic task to sync docs every hour"""
        while True:
            try:
                updated, status_info = await self.bot.db.sync_docs_from_url(COOLBOT_JSON_URL)
                if updated:
                    print(f"Docs database updated from remote URL - {status_info['docs_count']} entries")
            except Exception as e:
                print(f"Error in docs sync loop: {e}")
            await asyncio.sleep(3600)  # Wait 1 hour