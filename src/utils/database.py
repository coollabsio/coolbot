import aiosqlite
import time
from pathlib import Path

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
                      view_type: str, post_owner_id: int = None, is_solved: bool = False):
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
