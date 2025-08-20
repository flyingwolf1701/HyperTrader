# backend/app/main.py

from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.session import async_engine
from app.schemas.plan import Base as PlanBase
from app.schemas.favorite import Base as FavoriteBase
# Routers will be created and imported later
# from app.api.endpoints import router as api_router
# from app.api.websockets import router as ws_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown events.
    """
    async with async_engine.begin() as conn:
        # On startup, create all database tables based on the SQLAlchemy models
        # This is suitable for development, but for production, a migration tool like Alembic is recommended.
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
# app.include_router(api_router, prefix="/api/v1")
# app.include_router(ws_router)

@app.get("/")
def read_root():
    """
    A simple root endpoint to confirm the API is running.
    """
    return {"status": "HyperTrader Backend is running"}
