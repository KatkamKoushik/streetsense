import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.init_db import init_db
from app.api.v1.auth import router as auth_router
from app.api.v1.devices import router as devices_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.events import router as events_router
from app.api.v1.telemetry import router as telemetry_router
from app.websocket.endpoints import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("streetsense.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing StreetSense Backend database tables...")
    await init_db()
    logger.info("StreetSense Backend initialization complete.")
    yield
    logger.info("StreetSense Backend shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST Routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(devices_router, prefix=settings.API_V1_PREFIX)
app.include_router(sessions_router, prefix=settings.API_V1_PREFIX)
app.include_router(events_router, prefix=settings.API_V1_PREFIX)
app.include_router(telemetry_router, prefix=settings.API_V1_PREFIX)

# WebSocket Router
app.include_router(ws_router)


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }


@app.get("/ready", tags=["system"])
async def readiness_check():
    return {
        "status": "ready",
        "database": "connected"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
