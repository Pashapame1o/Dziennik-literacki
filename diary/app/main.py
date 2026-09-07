from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from diary.app.routes import router
from diary.core.portfolio import storage
from diary.core.settings import get_settings

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Applies pending migrations eagerly at startup rather than on the first
    # request, so a broken DB path/schema fails loudly at `diary serve` time
    # instead of inside a background generation task later.
    storage.get_connection(get_settings().db_path).close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Dziennik literacki", lifespan=_lifespan)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
