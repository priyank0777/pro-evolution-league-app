from contextlib import asynccontextmanager
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, SessionLocal, engine
from app.routers import admin, auth, matches, preferences, standings, teams
from app.seed import seed_initial_data
from app.services.scheduler import enforce_expired_match_deadlines

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def scheduled_auto_draw_job():
    """Background task to automatically assign 0-0 draws to matches past Friday midnight."""
    db = SessionLocal()
    try:
        enforce_expired_match_deadlines(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database schema, seed Admin + SystemSettings, and start deadline scheduler."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
        enforce_expired_match_deadlines(db)
    finally:
        db.close()

    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_auto_draw_job, "interval", minutes=5, id="friday_auto_draw")
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="2v2 eFootball League Tournament Management API",
    description="Production-ready 2v2 eFootball League platform with partner preference matchmaking, round-robin fixture generation, and live statistics.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST API Routers
app.include_router(auth.router)
app.include_router(preferences.router)
app.include_router(teams.router)
app.include_router(matches.router)
app.include_router(standings.router)
app.include_router(admin.router)

# Mount Static Assets & SPA Entrypoint
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/api/health")
def health_check():
    """Health check endpoint to verify database & backend readiness."""
    return {"status": "ok", "service": "2v2-efootball-league"}


@app.get("/", include_in_schema=False)
def serve_spa():
    """Serve the Single Page Application (SPA) frontend."""
    return FileResponse(str(STATIC_DIR / "index.html"))
