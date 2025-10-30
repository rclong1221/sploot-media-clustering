from collections.abc import Callable
from fastapi import FastAPI

from .config import get_settings
from .routes.internal import router as internal_router
from .services.clustering import cluster_service


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, docs_url=None, redoc_url=None)

    @app.get("/healthz", tags=["health"], summary="Service health probe")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.on_event("startup")
    async def _startup() -> None:
        await cluster_service.ensure_consumer_group()

    app.include_router(internal_router, prefix="/internal", tags=["internal"])
    return app
