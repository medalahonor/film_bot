"""FastAPI application entry point."""
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import config
from api.routers import admin, kinopoisk, leaderboard, movies, ratings, sessions, users, votes
from bot.log_handler import InMemoryLogHandler

# Configure logging with in-memory handler for /api/admin/logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
_mem_handler = InMemoryLogHandler()
_mem_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(name)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
))
logging.getLogger().addHandler(_mem_handler)

app = FastAPI(title="FilmBot API", version="1.0.0")

# Allow WebApp origin (and localhost for development)
_origins = ["http://localhost:5173", "http://localhost:3000"]
if config.webapp_origin:
    _origins.append(config.webapp_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(sessions.router)
app.include_router(movies.router)
app.include_router(leaderboard.router)
app.include_router(kinopoisk.router)
app.include_router(votes.router)
app.include_router(ratings.router)
app.include_router(admin.router)
app.include_router(users.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
