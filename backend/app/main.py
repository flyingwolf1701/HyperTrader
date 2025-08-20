# backend\app\main.py

from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.session import async_engine
from app.schemas.plan import Base as PlanBase
from app.schemas.favorite import Base as FavoriteBase
# Import the new routers
from app.api import endpoints, websockets

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown events.
    """
    async with async_engine.begin() as conn:
        # On startup, create all database tables
        await conn.run_sync(PlanBase.metadata.create_all)
        await conn.run_sync(FavoriteBase.metadata.create_all)
    
    print("--- Database tables created ---")
    yield
    # On shutdown, you can add cleanup logic here
    print("--- Application shutting down ---")


# Initialize the FastAPI application with the lifespan manager
app = FastAPI(
    title="HyperTrader Backend",
    lifespan=lifespan
)

# Include the API routers
app.include_router(endpoints.router, prefix="/api/v1")
app.include_router(websockets.router)

@app.get("/")
def read_root():
    """
    A simple root endpoint to confirm the API is running.
    """
    return {"status": "HyperTrader Backend is running"}