import redis.asyncio as aioredis
import json
import os
from typing import Optional

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Глобальный пул соединений
_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


# ── Токены ──

TOKEN_TTL = 3500  # чуть меньше чем срок жизни токена (3600 сек)

def _token_key(user_id: int, channel_name: str, role: str) -> str:
    return f"token:{user_id}:{channel_name}:{role}"


async def cache_token(user_id: int, channel_name: str, role: str, token_data: dict):
    """Кэшировать токен в Redis."""
    r = await get_redis()
    key = _token_key(user_id, channel_name, role)
    await r.setex(key, TOKEN_TTL, json.dumps(token_data))


async def get_cached_token(user_id: int, channel_name: str, role: str) -> Optional[dict]:
    """Получить токен из кэша (None если не найден или истёк)."""
    r = await get_redis()
    key = _token_key(user_id, channel_name, role)
    data = await r.get(key)
    if data:
        return json.loads(data)
    return None


async def invalidate_token(user_id: int, channel_name: str, role: str):
    """Удалить токен из кэша (при завершении звонка)."""
    r = await get_redis()
    key = _token_key(user_id, channel_name, role)
    await r.delete(key)


# ── Активные звонки ──

CALL_TTL = 7200  # 2 часа максимум

def _call_key(channel_name: str) -> str:
    return f"call:active:{channel_name}"


async def set_active_call(channel_name: str, call_data: dict):
    """Отметить звонок как активный."""
    r = await get_redis()
    await r.setex(_call_key(channel_name), CALL_TTL, json.dumps(call_data))


async def get_active_call(channel_name: str) -> Optional[dict]:
    """Проверить активен ли звонок в канале."""
    r = await get_redis()
    data = await r.get(_call_key(channel_name))
    return json.loads(data) if data else None


async def remove_active_call(channel_name: str):
    """Убрать звонок из активных."""
    r = await get_redis()
    await r.delete(_call_key(channel_name))


# ── Health check ──

async def ping_redis() -> bool:
    try:
        r = await get_redis()
        return await r.ping()
    except Exception:
        return False
