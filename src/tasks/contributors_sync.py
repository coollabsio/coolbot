import asyncio
import aiohttp
from typing import List

class ContributorsSync:
    def __init__(self, bot):
        self.bot = bot

    async def initialize_tasks(self):
        """Start the contributors sync background task"""
        asyncio.create_task(self.contributors_sync_loop())
        asyncio.create_task(self.cleanup_verification_tokens_loop())

    async def contributors_sync_loop(self):
        """Periodic task to sync contributors every 12 hours"""
        while True:
            try:
                synced_count = await self.sync_contributors_from_github()
                if synced_count > 0:
                    print(f"Contributors database updated - {synced_count} contributors synced")
            except Exception as e:
                print(f"Error in contributors sync loop: {e}")
            await asyncio.sleep(43200)  # Wait 12 hours (43200 seconds)

    async def sync_contributors_from_github(self) -> int:
        """Sync contributors from GitHub API for all configured repos"""
        from config import GITHUB_REPOS

        total_contributors = 0

        async with aiohttp.ClientSession() as session:
            for repo in GITHUB_REPOS:
                if not repo.strip():
                    continue

                try:
                    contributors = await self.fetch_repo_contributors(session, repo.strip())
                    for contributor in contributors:
                        await self.bot.db.add_contributor(contributor['login'], repo)
                        total_contributors += 1
                except Exception as e:
                    print(f"Error syncing contributors for repo {repo}: {e}")

        return total_contributors

    async def cleanup_verification_tokens_loop(self):
        """Periodic task to clean up expired verification tokens"""
        while True:
            try:
                await self.bot.db.cleanup_expired_tokens()
            except Exception as e:
                print(f"Error cleaning up verification tokens: {e}")
            await asyncio.sleep(3600)  # Clean up every hour

    async def fetch_repo_contributors(self, session: aiohttp.ClientSession, repo: str) -> List[dict]:
        """Fetch contributors for a specific repo from GitHub API"""
        url = f"https://api.github.com/repos/{repo}/contributors"
        contributors = []

        page = 1
        while True:
            params = {'page': page, 'per_page': 100}
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    print(f"Error fetching contributors for {repo}: {response.status}")
                    break

                page_contributors = await response.json()
                if not page_contributors:
                    break

                contributors.extend(page_contributors)
                page += 1

                # GitHub API rate limiting
                await asyncio.sleep(0.1)

        return contributors