import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.api.routes import router
from app.config import settings
from app.db import engine, init_db
from app.pipeline.policies import sync_policies
from app.pipeline.run import start_scan_in_background

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        sync_policies(session, settings.policies_dir)
    scheduler = None
    if settings.enable_scheduler:
        scheduler = BackgroundScheduler()
        # Weekly, at a fixed time; unlike an interval, this doesn't reset when --reload restarts the server.
        scheduler.add_job(
            start_scan_in_background, "cron", day_of_week=settings.scan_day_of_week, hour=settings.scan_hour, minute=0
        )
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Regulatory Change Monitor", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/health")
def health():
    return {"ok": True, "demo_mode": settings.demo_mode, "model": settings.anthropic_model}
