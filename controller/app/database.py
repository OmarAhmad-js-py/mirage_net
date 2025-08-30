import redis
import json
from typing import Optional, Dict, Any
import os

class RedisDB:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.client = redis.from_url(self.redis_url, decode_responses=True)
    
    def set_key(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        try:
            serialized = json.dumps(value)
            if expire:
                return self.client.setex(key, expire, serialized)
            else:
                return self.client.set(key, serialized)
        except (TypeError, redis.RedisError) as e:
            print(f"Redis set error: {e}")
            return False
    
    def get_key(self, key: str) -> Optional[Any]:
        try:
            value = self.client.get(key)
            return json.loads(value) if value else None
        except (TypeError, json.JSONDecodeError, redis.RedisError) as e:
            print(f"Redis get error: {e}")
            return None
    
    def delete_key(self, key: str) -> bool:
        try:
            return bool(self.client.delete(key))
        except redis.RedisError as e:
            print(f"Redis delete error: {e}")
            return False
    
    def get_all_keys(self, pattern: str = "*") -> list[str]:
        try:
            return self.client.keys(pattern)
        except redis.RedisError as e:
            print(f"Redis keys error: {e}")
            return []