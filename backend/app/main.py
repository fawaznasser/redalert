from __future__ import annotations

import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.locations import router as locations_router
from app.api.routes.raw_messages import router as raw_messages_router
from app.api.routes.regions import router as regions_router
from app.api.routes.stats import router as stats_router
from app.config import settings
from app.db import Base, engine
from app.services.live_updates import live_updates
from app.services.telegram_listener import TelegramListener

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

telegram_listener = TelegramListener()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    live_updates.bind_loop(asyncio.get_running_loop())
    if settings.start_telegram_listener_in_api:
        await telegram_listener.start()
    yield
    if settings.start_telegram_listener_in_api:
        await telegram_listener.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(events_router)
app.include_router(locations_router)
app.include_router(raw_messages_router)
app.include_router(regions_router)
app.include_router(stats_router)
