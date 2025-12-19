import aiosqlite
import time
from pathlib import Path
from typing import Optional

class Database:
    def __init__(self):
        database_dir = Path("database")
        database_dir.mkdir(exist_ok=True)
        self.db_path = database_dir / "bot.db"

    async def init(self):
        """Initialize database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS persistent_views (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    thread_id INTEGER NOT NULL,
                    view_type TEXT NOT NULL,
                    post_owner_id INTEGER,
                    is_solved BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS pending_closes (
                    thread_id INTEGER PRIMARY KEY,
                    close_at INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS doc_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    link TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS doc_sync_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            await db.commit()

    async def create_tables(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS users (
                                id INTEGER PRIMARY KEY,
                                name TEXT NOT NULL,
                                balance INTEGER NOT NULL)''')
            await db.commit()

    async def add_user(self, user_id: int, name: str, balance: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('INSERT INTO users (id, name, balance) VALUES (?, ?, ?)', (user_id, name, balance))
            await db.commit()

    async def get_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM users WHERE id = ?', (user_id,)) as cursor:
                return await cursor.fetchone()

    async def update_balance(self, user_id: int, balance: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET balance = ? WHERE id = ?', (balance, user_id))
            await db.commit()

    async def delete_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM users WHERE id = ?', (user_id,))
            await db.commit()

    async def add_view(self, message_id: int, channel_id: int, thread_id: int,
                      view_type: str, post_owner_id: Optional[int] = None, is_solved: bool = False):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO persistent_views 
                (message_id, channel_id, thread_id, view_type, post_owner_id, is_solved)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (message_id, channel_id, thread_id, view_type, post_owner_id, is_solved))
            await db.commit()

    async def remove_view(self, message_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM persistent_views WHERE message_id = ?", (message_id,))
            await db.commit()

    async def get_all_views(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM persistent_views") as cursor:
                return await cursor.fetchall()

    async def get_pending_closes(self):
        """Fetch all pending close tasks"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM pending_closes") as cursor:
                return await cursor.fetchall()

    async def add_close_task(self, thread_id: int, close_at: int):
        """Add a new thread close task to the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO pending_closes (thread_id, close_at)
                VALUES (?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                close_at = excluded.close_at
            """, (thread_id, close_at))
            await db.commit()

    async def mark_view_solved(self, message_id: int, is_solved: bool):
        """Update the solved status of a persistent view"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE persistent_views 
                SET is_solved = ?
                WHERE message_id = ?
            """, (is_solved, message_id))
            await db.commit()

    async def remove_close_task(self, thread_id: int):
        """Remove a thread close task from the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM pending_closes WHERE thread_id = ?", (thread_id,))
            await db.commit()

    # Doc entries methods
    async def add_doc_entry(self, name: str, link: str):
        """Add a new doc entry"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO doc_entries (name, link) VALUES (?, ?)", (name, link))
            await db.commit()

    async def get_doc_entries(self):
        """Get all doc entries"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM doc_entries") as cursor:
                return await cursor.fetchall()

    async def clear_doc_entries(self):
        """Clear all doc entries"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM doc_entries")
            await db.commit()

    # Doc sync metadata methods
    async def set_sync_metadata(self, key: str, value: str):
        """Set sync metadata key-value pair"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO doc_sync_metadata (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value))
            await db.commit()

    async def get_sync_metadata(self, key: str):
        """Get sync metadata value by key"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM doc_sync_metadata WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def sync_docs_from_url(self, url: str) -> tuple[bool, dict]:
        """Sync docs from URL with ETag checking. Returns (updated, status_info)."""
        import aiohttp
        import json

        status_info = {
            "url": url,
            "current_etag": None,
            "used_etag_header": False,
            "response_status": None,
            "response_etag": None,
            "docs_count": 0,
            "updated": False,
            "error": None
        }

        current_etag = await self.get_sync_metadata("docs_etag")
        status_info["current_etag"] = current_etag

        headers = {}
        if current_etag:
            headers["If-None-Match"] = current_etag
            status_info["used_etag_header"] = True

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    status_info["response_status"] = response.status
                    status_info["response_etag"] = response.headers.get("ETag")

                    if response.status == 304:  # Not modified
                        return False, status_info
                    elif response.status != 200:
                        status_info["error"] = f"HTTP {response.status}"
                        return False, status_info

                    new_etag = response.headers.get("ETag")
                    docs_data = await response.json()
                    status_info["docs_count"] = len(docs_data)

                    # Clear and repopulate
                    await self.clear_doc_entries()
                    for entry in docs_data:
                        await self.add_doc_entry(entry["name"], entry["link"])

                    status_info["updated"] = True

                    # Update ETag
                    if new_etag:
                        await self.set_sync_metadata("docs_etag", new_etag)

                    return True, status_info
        except Exception as e:
            status_info["error"] = str(e)
            return False, status_info
