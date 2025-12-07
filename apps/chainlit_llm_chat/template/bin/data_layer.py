"""
Custom SQLite Data Layer for Chainlit

Creates user-specific SQLite databases for chat persistence.
Each user gets their own database at ~/.chainlit_data/chat.db
"""

import json
import os
import aiosqlite
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List
from chainlit.data import BaseDataLayer
from utils import ensure_secure_permissions
from chainlit.types import (
    Feedback,
    ThreadDict,
    Pagination,
    PageInfo,
    PaginatedResponse,
)
from chainlit.step import StepDict
from chainlit.element import ElementDict
from chainlit.user import User, PersistedUser


def get_user_db_path() -> Path:
    """Get the path to a user's SQLite database."""
    if os.getenv("CHAINLIT_DATA_DIR"):
        base_data_dir = Path(os.environ["CHAINLIT_DATA_DIR"])
    else:
        base_data_dir = Path.home() / ".chainlit_data"
    
    # Create base directory with restricted permissions
    if not base_data_dir.exists():
        base_data_dir.mkdir(parents=True)
    ensure_secure_permissions(base_data_dir, is_dir=True)
    
    db_path = base_data_dir / "chat.db"
    
    # Ensure DB file has restricted permissions if it exists
    if db_path.exists():
        ensure_secure_permissions(db_path)
            
    return db_path


async def init_database(db_path: Path) -> None:
    """Initialize the SQLite database with required tables."""
    async with aiosqlite.connect(db_path) as db:
        # Enforce restricted permissions immediately after creation
        ensure_secure_permissions(db_path)

        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                identifier TEXT UNIQUE NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                name TEXT,
                metadata TEXT,
                tags TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            
            CREATE TABLE IF NOT EXISTS steps (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                parent_id TEXT,
                name TEXT,
                type TEXT,
                input TEXT,
                output TEXT,
                metadata TEXT,
                start_time TEXT,
                end_time TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (thread_id) REFERENCES threads(id)
            );
            
            CREATE TABLE IF NOT EXISTS elements (
                id TEXT PRIMARY KEY,
                thread_id TEXT,
                step_id TEXT,
                type TEXT NOT NULL,
                name TEXT,
                display TEXT,
                url TEXT,
                path TEXT,
                content TEXT,
                mime TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (thread_id) REFERENCES threads(id),
                FOREIGN KEY (step_id) REFERENCES steps(id)
            );
            
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                step_id TEXT NOT NULL,
                value INTEGER NOT NULL,
                strategy TEXT,
                comment TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (step_id) REFERENCES steps(id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_threads_user ON threads(user_id);
            CREATE INDEX IF NOT EXISTS idx_steps_thread ON steps(thread_id);
            CREATE INDEX IF NOT EXISTS idx_elements_thread ON elements(thread_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_step ON feedback(step_id);
        """)
        await db.commit()


class SQLiteDataLayer(BaseDataLayer):
    """User-specific SQLite data layer for Chainlit."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.db_path = get_user_db_path()
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Ensure the database is initialized."""
        if not self._initialized:
            await init_database(self.db_path)
            self._initialized = True
    
    async def _get_db(self):
        """Get a database connection."""
        await self._ensure_initialized()
        return aiosqlite.connect(self.db_path)
    
    # User methods
    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        """Get a user by identifier."""
        async with await self._get_db() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE identifier = ?",
                (identifier,)
            )
            row = await cursor.fetchone()
            
            if row:
                return PersistedUser(
                    id=row["id"],
                    identifier=row["identifier"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    createdAt=row["created_at"]
                )
            return None
    
    async def create_user(self, user: User) -> Optional[PersistedUser]:
        """Create a new user."""
        import uuid
        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        async with await self._get_db() as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (id, identifier, metadata, created_at) VALUES (?, ?, ?, ?)",
                (user_id, user.identifier, json.dumps(user.metadata), created_at)
            )
            await db.commit()
            
            return PersistedUser(
                id=user_id,
                identifier=user.identifier,
                metadata=user.metadata or {},
                createdAt=created_at
            )
    
    # Thread methods
    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """Get a thread by ID."""
        async with await self._get_db() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM threads WHERE id = ?",
                (thread_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                # Get steps for this thread
                steps_cursor = await db.execute(
                    "SELECT * FROM steps WHERE thread_id = ? ORDER BY created_at",
                    (thread_id,)
                )
                steps_rows = await steps_cursor.fetchall()
                steps = []
                for step_row in steps_rows:
                    steps.append({
                        "id": step_row["id"],
                        "threadId": step_row["thread_id"],
                        "parentId": step_row["parent_id"],
                        "name": step_row["name"],
                        "type": step_row["type"],
                        "input": step_row["input"],
                        "output": step_row["output"],
                        "metadata": json.loads(step_row["metadata"]) if step_row["metadata"] else {},
                        "startTime": step_row["start_time"],
                        "endTime": step_row["end_time"],
                        "createdAt": step_row["created_at"]
                    })
                
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "userId": row["user_id"],
                    "userIdentifier": row["user_id"],  # Required by Chainlit for thread switching
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "createdAt": row["created_at"],
                    "steps": steps
                }
            return None
    
    async def create_thread(
        self,
        thread_id: str,
        user_id: Optional[str] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Create a new thread."""
        created_at = datetime.now(timezone.utc).isoformat()
        # Use provided user_id or fall back to self.user_id
        effective_user_id = user_id or self.user_id
        
        async with await self._get_db() as db:
            await db.execute(
                """INSERT OR IGNORE INTO threads (id, user_id, name, metadata, tags, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    thread_id,
                    effective_user_id,
                    name or f"Chat {created_at[:10]}",
                    json.dumps(metadata) if metadata else None,
                    json.dumps(tags) if tags else None,
                    created_at
                )
            )
            await db.commit()
    
    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Update an existing thread."""
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
        
        updates.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(thread_id)
        
        if updates:
            async with await self._get_db() as db:
                await db.execute(
                    f"UPDATE threads SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                await db.commit()
    
    async def delete_thread(self, thread_id: str) -> None:
        """Delete a thread and all its data."""
        async with await self._get_db() as db:
            await db.execute("DELETE FROM feedback WHERE step_id IN (SELECT id FROM steps WHERE thread_id = ?)", (thread_id,))
            await db.execute("DELETE FROM elements WHERE thread_id = ?", (thread_id,))
            await db.execute("DELETE FROM steps WHERE thread_id = ?", (thread_id,))
            await db.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            await db.commit()
    
    async def list_threads(
        self,
        pagination: Pagination,
        filters: Optional[Dict] = None
    ) -> PaginatedResponse[ThreadDict]:
        """List threads with pagination."""
        async with await self._get_db() as db:
            db.row_factory = aiosqlite.Row
            
            # Build query - each user has their own database, so list all threads
            query = "SELECT * FROM threads"
            params = []
            
            # Add ordering
            query += " ORDER BY created_at DESC"
            
            # Add pagination
            query += f" LIMIT {pagination.first + 1}"
            if pagination.cursor:
                # Decode cursor (it's the offset)
                query += f" OFFSET {int(pagination.cursor)}"
            
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            
            threads = []
            for row in rows[:pagination.first]:
                threads.append({
                    "id": row["id"],
                    "name": row["name"],
                    "userId": row["user_id"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "createdAt": row["created_at"],
                    "steps": []
                })
            
            has_next = len(rows) > pagination.first
            
            return PaginatedResponse(
                data=threads,
                pageInfo=PageInfo(
                    hasNextPage=has_next,
                    startCursor=pagination.cursor or "0",
                    endCursor=str(int(pagination.cursor or 0) + len(threads))
                )
            )
    
    # Step methods
    async def create_step(self, step_dict: StepDict) -> None:
        """Create a new step."""
        created_at = datetime.now(timezone.utc).isoformat()
        
        async with await self._get_db() as db:
            await db.execute(
                """INSERT INTO steps 
                   (id, thread_id, parent_id, name, type, input, output, metadata, start_time, end_time, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    step_dict.get("id"),
                    step_dict.get("threadId"),
                    step_dict.get("parentId"),
                    step_dict.get("name"),
                    step_dict.get("type"),
                    step_dict.get("input"),
                    step_dict.get("output"),
                    json.dumps(step_dict.get("metadata")) if step_dict.get("metadata") else None,
                    step_dict.get("startTime"),
                    step_dict.get("endTime"),
                    created_at
                )
            )
            await db.commit()
    
    async def update_step(self, step_dict: StepDict) -> None:
        """Update an existing step."""
        async with await self._get_db() as db:
            await db.execute(
                """UPDATE steps SET 
                   name = ?, type = ?, input = ?, output = ?, 
                   metadata = ?, start_time = ?, end_time = ?
                   WHERE id = ?""",
                (
                    step_dict.get("name"),
                    step_dict.get("type"),
                    step_dict.get("input"),
                    step_dict.get("output"),
                    json.dumps(step_dict.get("metadata")) if step_dict.get("metadata") else None,
                    step_dict.get("startTime"),
                    step_dict.get("endTime"),
                    step_dict.get("id")
                )
            )
            await db.commit()
    
    async def delete_step(self, step_id: str) -> None:
        """Delete a step."""
        async with await self._get_db() as db:
            await db.execute("DELETE FROM feedback WHERE step_id = ?", (step_id,))
            await db.execute("DELETE FROM elements WHERE step_id = ?", (step_id,))
            await db.execute("DELETE FROM steps WHERE id = ?", (step_id,))
            await db.commit()
    
    # Element methods
    async def create_element(self, element) -> None:
        """Create a new element."""
        created_at = datetime.now(timezone.utc).isoformat()
        
        # Handle both dict and object access (Chainlit may pass Element objects)
        def get_attr(obj, key, default=None):
            if hasattr(obj, 'get'):
                return obj.get(key, default)
            return getattr(obj, key, default)
        
        # Map camelCase to snake_case for object attributes
        element_id = get_attr(element, "id") or getattr(element, "id", None)
        thread_id = get_attr(element, "threadId") or getattr(element, "thread_id", None)
        step_id = get_attr(element, "stepId") or getattr(element, "step_id", None) or getattr(element, "for_id", None)
        element_type = get_attr(element, "type") or getattr(element, "type", None)
        name = get_attr(element, "name") or getattr(element, "name", None)
        display = get_attr(element, "display") or getattr(element, "display", None)
        url = get_attr(element, "url") or getattr(element, "url", None)
        path = get_attr(element, "path") or getattr(element, "path", None)
        content = get_attr(element, "content") or getattr(element, "content", None)
        mime = get_attr(element, "mime") or getattr(element, "mime", None)
        metadata = get_attr(element, "metadata") or getattr(element, "metadata", None)
        
        async with await self._get_db() as db:
            await db.execute(
                """INSERT OR IGNORE INTO elements 
                   (id, thread_id, step_id, type, name, display, url, path, content, mime, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    element_id,
                    thread_id,
                    step_id,
                    element_type,
                    name,
                    display,
                    url,
                    path,
                    content if isinstance(content, (str, bytes, type(None))) else str(content),
                    mime,
                    json.dumps(metadata) if metadata else None,
                    created_at
                )
            )
            await db.commit()
    
    async def get_element(
        self, thread_id: str, element_id: str
    ) -> Optional[ElementDict]:
        """Get an element by ID."""
        async with await self._get_db() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM elements WHERE id = ? AND thread_id = ?",
                (element_id, thread_id)
            )
            row = await cursor.fetchone()
            
            if row:
                return {
                    "id": row["id"],
                    "threadId": row["thread_id"],
                    "stepId": row["step_id"],
                    "type": row["type"],
                    "name": row["name"],
                    "display": row["display"],
                    "url": row["url"],
                    "path": row["path"],
                    "content": row["content"],
                    "mime": row["mime"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                }
            return None
    
    async def delete_element(self, element_id: str) -> None:
        """Delete an element."""
        async with await self._get_db() as db:
            await db.execute("DELETE FROM elements WHERE id = ?", (element_id,))
            await db.commit()
    
    # Feedback methods
    async def upsert_feedback(self, feedback: Feedback) -> str:
        """Create or update feedback."""
        import uuid
        feedback_id = feedback.id or str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        async with await self._get_db() as db:
            await db.execute(
                """INSERT OR REPLACE INTO feedback 
                   (id, step_id, value, strategy, comment, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    feedback_id,
                    feedback.forId,
                    feedback.value,
                    feedback.strategy,
                    feedback.comment,
                    created_at
                )
            )
            await db.commit()
        
        return feedback_id
    
    async def delete_feedback(self, feedback_id: str) -> None:
        """Delete feedback."""
        async with await self._get_db() as db:
            await db.execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))
            await db.commit()
    
    # Required abstract methods
    async def build_debug_url(self) -> str:
        return ""
    
    async def close(self) -> None:
        """Close any open database connections."""
        # aiosqlite connections are handled per-query, no persistent connection to close
        pass
    
    async def get_thread_author(self, thread_id: str) -> Optional[str]:
        """Get the author/user ID of a thread."""
        async with await self._get_db() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT user_id FROM threads WHERE id = ?",
                (thread_id,)
            )
            row = await cursor.fetchone()
            return row["user_id"] if row else None


# Factory function to create data layer for a user
_data_layers: Dict[str, SQLiteDataLayer] = {}


def get_data_layer(user_id: str) -> SQLiteDataLayer:
    """Get or create a data layer for a user."""
    if user_id not in _data_layers:
        _data_layers[user_id] = SQLiteDataLayer(user_id)
    return _data_layers[user_id]
