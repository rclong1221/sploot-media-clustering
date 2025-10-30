from __future__ import annotations

from __future__ import annotations

from redis.asyncio import Redis

from ..config import get_settings

_redis_client: Redis | None = None


def _build_client() -> Redis:
    settings = get_settings()
    kwargs = {
        "username": settings.redis_username,
        "password": settings.redis_password,
        "decode_responses": True,
        "health_check_interval": settings.redis_healthcheck_interval,
        "socket_connect_timeout": settings.redis_socket_connect_timeout,
        "socket_timeout": settings.redis_socket_timeout,
        "retry_on_timeout": settings.redis_retry_on_timeout,
        "max_connections": settings.redis_pool_max_connections,
    }
    if settings.redis_ssl:
        kwargs["ssl"] = True
        if settings.redis_ssl_ca_certs:
            kwargs["ssl_ca_certs"] = settings.redis_ssl_ca_certs

    filtered_kwargs = {key: value for key, value in kwargs.items() if value is not None}

    return Redis.from_url(settings.redis_url, **filtered_kwargs)


def get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = _build_client()
    return _redis_client


async def redis_alive() -> bool:
    client = get_redis_client()
    try:
        await client.ping()
        return True
    except Exception:  # pragma: no cover
        return False
