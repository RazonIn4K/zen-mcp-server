"""
Redis storage backend for conversation threads

This module provides a Redis-based alternative to in-memory storage for storing
conversation contexts. It enables multi-agent scenarios where multiple MCP server
processes need to share conversation state.

⚠️  SHARED STORAGE: Unlike the in-memory backend, this Redis backend allows
    conversation state to be shared across multiple processes and agents.
    This is essential for scenarios where multiple Claude sessions or different
    AI agents need to collaborate on the same conversation threads.

Key Features:
- Cross-process conversation sharing via Redis
- TTL support with automatic expiration (handled by Redis)
- Connection pooling for efficient resource usage
- Automatic reconnection on connection failures
- Drop-in replacement for InMemoryStorage
- Graceful fallback to in-memory storage if Redis is unavailable

Configuration:
    REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)
    REDIS_PASSWORD: Optional Redis password
    REDIS_SSL: Enable SSL for Redis connection (default: false)
    REDIS_KEY_PREFIX: Prefix for all Redis keys (default: "zen:")
    REDIS_CONNECTION_TIMEOUT: Connection timeout in seconds (default: 5)
    REDIS_SOCKET_TIMEOUT: Socket timeout in seconds (default: 5)

Usage:
    Set USE_REDIS_STORAGE=1 in environment to enable Redis backend.
    Falls back to in-memory storage if Redis connection fails.
"""

import logging
import threading
from typing import Optional

from utils.env import get_env

logger = logging.getLogger(__name__)


class RedisStorage:
    """Redis-based storage for conversation threads with cross-process sharing."""

    def __init__(self):
        self._redis_client = None
        self._connection_lock = threading.Lock()
        self._key_prefix = get_env("REDIS_KEY_PREFIX", "zen:") or "zen:"
        self._connected = False
        self._connection_error_logged = False

        # Attempt initial connection
        self._connect()

    def _connect(self) -> bool:
        """
        Establish Redis connection with error handling.

        Returns:
            bool: True if connection successful, False otherwise
        """
        if self._connected and self._redis_client is not None:
            return True

        with self._connection_lock:
            # Double-check after acquiring lock
            if self._connected and self._redis_client is not None:
                return True

            try:
                import redis

                redis_url = get_env("REDIS_URL", "redis://localhost:6379/0") or "redis://localhost:6379/0"
                redis_password = get_env("REDIS_PASSWORD", "") or None
                redis_ssl = (get_env("REDIS_SSL", "false") or "false").lower() in ("true", "1", "yes")
                connection_timeout = int(get_env("REDIS_CONNECTION_TIMEOUT", "5") or "5")
                socket_timeout = int(get_env("REDIS_SOCKET_TIMEOUT", "5") or "5")

                # Create connection pool for efficient resource usage
                pool = redis.ConnectionPool.from_url(
                    redis_url,
                    password=redis_password,
                    socket_connect_timeout=connection_timeout,
                    socket_timeout=socket_timeout,
                    ssl=redis_ssl,
                    decode_responses=True,  # Return strings instead of bytes
                    max_connections=10,  # Limit connections per process
                )

                self._redis_client = redis.Redis(connection_pool=pool)

                # Test connection
                self._redis_client.ping()
                self._connected = True
                self._connection_error_logged = False

                logger.info(f"Redis storage connected: {redis_url.split('@')[-1]}")  # Log URL without password
                return True

            except ImportError:
                if not self._connection_error_logged:
                    logger.warning(
                        "Redis package not installed. Install with: pip install redis. "
                        "Falling back to in-memory storage."
                    )
                    self._connection_error_logged = True
                return False

            except Exception as e:
                if not self._connection_error_logged:
                    logger.warning(f"Redis connection failed: {e}. Falling back to in-memory storage.")
                    self._connection_error_logged = True
                self._connected = False
                return False

    def _get_full_key(self, key: str) -> str:
        """Add prefix to key for namespace isolation."""
        return f"{self._key_prefix}{key}"

    def set_with_ttl(self, key: str, ttl_seconds: int, value: str) -> bool:
        """
        Store value with expiration time.

        Args:
            key: Storage key
            ttl_seconds: Time-to-live in seconds
            value: Value to store

        Returns:
            bool: True if stored successfully, False otherwise
        """
        if not self._connect():
            return False

        try:
            full_key = self._get_full_key(key)
            self._redis_client.setex(full_key, ttl_seconds, value)
            logger.debug(f"Redis: Stored key {key} with TTL {ttl_seconds}s")
            return True

        except Exception as e:
            logger.warning(f"Redis set failed for key {key}: {e}")
            self._connected = False
            return False

    def get(self, key: str) -> Optional[str]:
        """
        Retrieve value if not expired.

        Args:
            key: Storage key

        Returns:
            str: Stored value if found and not expired, None otherwise
        """
        if not self._connect():
            return None

        try:
            full_key = self._get_full_key(key)
            value = self._redis_client.get(full_key)

            if value:
                logger.debug(f"Redis: Retrieved key {key}")
            return value

        except Exception as e:
            logger.warning(f"Redis get failed for key {key}: {e}")
            self._connected = False
            return None

    def setex(self, key: str, ttl_seconds: int, value: str) -> bool:
        """
        Redis-compatible setex method.

        Args:
            key: Storage key
            ttl_seconds: Time-to-live in seconds
            value: Value to store

        Returns:
            bool: True if stored successfully, False otherwise
        """
        return self.set_with_ttl(key, ttl_seconds, value)

    def delete(self, key: str) -> bool:
        """
        Delete a key from storage.

        Args:
            key: Storage key to delete

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if not self._connect():
            return False

        try:
            full_key = self._get_full_key(key)
            self._redis_client.delete(full_key)
            logger.debug(f"Redis: Deleted key {key}")
            return True

        except Exception as e:
            logger.warning(f"Redis delete failed for key {key}: {e}")
            self._connected = False
            return False

    def exists(self, key: str) -> bool:
        """
        Check if a key exists in storage.

        Args:
            key: Storage key to check

        Returns:
            bool: True if key exists, False otherwise
        """
        if not self._connect():
            return False

        try:
            full_key = self._get_full_key(key)
            return bool(self._redis_client.exists(full_key))

        except Exception as e:
            logger.warning(f"Redis exists check failed for key {key}: {e}")
            self._connected = False
            return False

    def refresh_ttl(self, key: str, ttl_seconds: int) -> bool:
        """
        Refresh the TTL of an existing key without changing its value.

        Args:
            key: Storage key
            ttl_seconds: New time-to-live in seconds

        Returns:
            bool: True if TTL refreshed successfully, False otherwise
        """
        if not self._connect():
            return False

        try:
            full_key = self._get_full_key(key)
            result = self._redis_client.expire(full_key, ttl_seconds)
            if result:
                logger.debug(f"Redis: Refreshed TTL for key {key} to {ttl_seconds}s")
            return bool(result)

        except Exception as e:
            logger.warning(f"Redis TTL refresh failed for key {key}: {e}")
            self._connected = False
            return False

    def get_all_thread_ids(self) -> list[str]:
        """
        Get all conversation thread IDs (for debugging/monitoring).

        Returns:
            list[str]: List of thread IDs
        """
        if not self._connect():
            return []

        try:
            pattern = self._get_full_key("thread:*")
            keys = self._redis_client.keys(pattern)
            # Strip prefix and "thread:" to get just the IDs
            prefix_len = len(self._key_prefix) + len("thread:")
            return [key[prefix_len:] for key in keys]

        except Exception as e:
            logger.warning(f"Redis keys lookup failed: {e}")
            self._connected = False
            return []

    def get_thread_count(self) -> int:
        """
        Get the number of active conversation threads.

        Returns:
            int: Number of active threads
        """
        if not self._connect():
            return 0

        try:
            pattern = self._get_full_key("thread:*")
            # Use SCAN for efficiency on large datasets
            count = 0
            cursor = 0
            while True:
                cursor, keys = self._redis_client.scan(cursor, match=pattern, count=100)
                count += len(keys)
                if cursor == 0:
                    break
            return count

        except Exception as e:
            logger.warning(f"Redis thread count failed: {e}")
            self._connected = False
            return 0

    def is_connected(self) -> bool:
        """
        Check if Redis connection is active.

        Returns:
            bool: True if connected, False otherwise
        """
        if not self._connected or self._redis_client is None:
            return False

        try:
            self._redis_client.ping()
            return True
        except Exception:
            self._connected = False
            return False

    def shutdown(self) -> None:
        """Graceful shutdown of Redis connection."""
        if self._redis_client is not None:
            try:
                self._redis_client.close()
                logger.info("Redis storage connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
            finally:
                self._redis_client = None
                self._connected = False


class HybridStorage:
    """
    Hybrid storage that uses Redis when available, falling back to in-memory.

    This class provides seamless failover between Redis and in-memory storage,
    ensuring the system continues to work even if Redis becomes unavailable.
    """

    def __init__(self):
        self._redis_storage: Optional[RedisStorage] = None
        self._memory_storage = None
        self._use_redis = (get_env("USE_REDIS_STORAGE", "0") or "0").lower() in ("1", "true", "yes")
        self._init_lock = threading.Lock()

        if self._use_redis:
            self._init_redis()

    def _init_redis(self) -> bool:
        """Initialize Redis storage."""
        with self._init_lock:
            if self._redis_storage is None:
                self._redis_storage = RedisStorage()
            return self._redis_storage.is_connected()

    def _get_memory_storage(self):
        """Get or create in-memory storage fallback."""
        if self._memory_storage is None:
            with self._init_lock:
                if self._memory_storage is None:
                    from utils.storage_backend import InMemoryStorage

                    self._memory_storage = InMemoryStorage()
        return self._memory_storage

    def _get_active_storage(self):
        """Get the currently active storage backend."""
        if self._use_redis and self._redis_storage is not None and self._redis_storage.is_connected():
            return self._redis_storage
        return self._get_memory_storage()

    def set_with_ttl(self, key: str, ttl_seconds: int, value: str) -> None:
        """Store value with expiration time."""
        storage = self._get_active_storage()
        storage.set_with_ttl(key, ttl_seconds, value)

    def get(self, key: str) -> Optional[str]:
        """Retrieve value if not expired."""
        storage = self._get_active_storage()
        return storage.get(key)

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        """Redis-compatible setex method."""
        self.set_with_ttl(key, ttl_seconds, value)

    def shutdown(self) -> None:
        """Graceful shutdown of all storage backends."""
        if self._redis_storage is not None:
            self._redis_storage.shutdown()
        if self._memory_storage is not None:
            self._memory_storage.shutdown()


# Global singleton instance
_hybrid_storage_instance: Optional[HybridStorage] = None
_hybrid_storage_lock = threading.Lock()


def get_redis_storage_backend() -> HybridStorage:
    """
    Get the global hybrid storage instance (singleton pattern).

    This function returns a HybridStorage instance that will use Redis
    when USE_REDIS_STORAGE=1 and Redis is available, otherwise falling
    back to in-memory storage.

    Returns:
        HybridStorage: Thread-safe hybrid storage backend
    """
    global _hybrid_storage_instance
    if _hybrid_storage_instance is None:
        with _hybrid_storage_lock:
            if _hybrid_storage_instance is None:
                _hybrid_storage_instance = HybridStorage()
                use_redis = (get_env("USE_REDIS_STORAGE", "0") or "0").lower() in ("1", "true", "yes")
                if use_redis:
                    logger.info("Initialized hybrid storage with Redis backend")
                else:
                    logger.info("Initialized hybrid storage with in-memory backend")
    return _hybrid_storage_instance
