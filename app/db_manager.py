import asyncio
import aiosqlite
from typing import Optional, Dict, List
from contextlib import asynccontextmanager


class ConnectionPool:
    def __init__(self, db_path: str, max_pool_size: int = 5):
        self.db_path = db_path
        self.max_pool_size = max_pool_size
        self._pool: List[aiosqlite.Connection] = []
        self._in_use: Dict[int, aiosqlite.Connection] = {}
        self._lock = asyncio.Lock()
        self._id_counter = 0
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool."""
        async with self._lock:
            if self._pool:
                conn = self._pool.pop()
                conn_id = id(conn)
                self._in_use[conn_id] = conn
            else:
                conn = await aiosqlite.connect(self.db_path)
                conn_id = id(conn)
                self._in_use[conn_id] = conn
        
        try:
            yield conn
        except Exception:
            await self._return_connection(conn_id)
            raise
        finally:
            await self._return_connection(conn_id)
    
    async def _return_connection(self, conn_id: int):
        """Return a connection to the pool."""
        async with self._lock:
            if conn_id in self._in_use:
                conn = self._in_use[conn_id]
                del self._in_use[conn_id]
                
                if len(self._pool) < self.max_pool_size:
                    try:
                        await conn.execute("SELECT 1")
                        self._pool.append(conn)
                    except:
                        await conn.close()
                else:
                    await conn.close()
    
    async def close_all(self):
        """Close all connections in the pool."""
        async with self._lock:
            for conn in self._pool + list(self._in_use.values()):
                try:
                    await conn.close()
                except:
                    pass
            self._pool.clear()
            self._in_use.clear()


_db_pool: Optional[ConnectionPool] = None


async def get_db_pool(db_path: str) -> ConnectionPool:
    """Get or create the global database pool."""
    global _db_pool
    if _db_pool is None:
        _db_pool = ConnectionPool(db_path)
    return _db_pool


async def init_db_pool(db_path: str):
    """Initialize the database pool."""
    await get_db_pool(db_path)
