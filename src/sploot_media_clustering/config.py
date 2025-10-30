from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    environment: Literal["local", "development", "staging", "production"] = "local"
    app_name: str = "sploot-media-clustering"

    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_username: str | None = None
    redis_password: str | None = None
    redis_ssl: bool = False
    redis_ssl_ca_certs: str | None = None
    redis_pool_max_connections: int = 20
    redis_socket_timeout: float | None = None
    redis_socket_connect_timeout: float = 5.0
    redis_healthcheck_interval: int = 30
    redis_retry_on_timeout: bool = True

    internal_token: str = "changeme"
    namespace: str = "sploot.media.clusters"

    cluster_ttl_seconds: int = 86400
    max_cluster_size: int = 24
    cluster_stream_key: str = "streams:media.cluster"
    cluster_dead_letter_stream: str = "streams:media.cluster.deadletter"
    cluster_stream_maxlen: int = 10000
    cluster_stream_approximate_trim: bool = True
    cluster_consumer_group: str = "media-clustering-workers"
    cluster_worker_consumer_name: str = "media-clustering-worker"
    cluster_read_timeout_ms: int = 5000
    cluster_read_count: int = 16
    cluster_retry_idle_ms: int = 60000
    cluster_max_attempts: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
