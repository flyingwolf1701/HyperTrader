# backend/app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

from app.core.config import settings
from app.db.session import init_db, close_db
from app.api import endpoints, websockets
from app.services.exchange import exchange_manager
from app.services.market_data import market_data_manager

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper()))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events, managing all necessary services.
    """
    logger.info("--- Starting HyperTrader Backend ---")
    
    # Initialize the database connection pool.
    await init_db()
    logger.info("Database connection initialized.")
    
    # Initialize the exchange manager to handle trading operations.
    await exchange_manager.initialize()
    logger.info("Exchange manager initialized.")
    
    # Start the market data manager to listen for live price feeds.
    market_data_manager.start()
    logger.info("Market data manager started.")
    
    yield
    
    # --- Cleanup on Shutdown ---
    logger.info("--- Shutting Down HyperTrader Backend ---")
    
    # Stop all background services gracefully.
    await market_data_manager.stop()
    logger.info("Market data manager stopped.")
    
    await exchange_manager.close()
    logger.info("Exchange manager connection closed.")

    await close_db()
    logger.info("Database connection closed.")
    
    logger.info("--- Shutdown complete. ---")


app = FastAPI(
    title=settings.APP_NAME,
    description="Advanced crypto trading bot with hedging strategy",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware to allow the frontend to connect.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include both REST API and WebSocket routers.
app.include_router(endpoints.router, prefix="/api/v1")
app.include_router(websockets.router)


@app.get("/")
async def root():
    return {"message": "HyperTrader API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
