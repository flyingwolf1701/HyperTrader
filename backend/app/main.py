import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import init_db, close_db_connection
from app.api import endpoints, websockets
from app.services.exchange import exchange_manager
from app.services.market_data import market_data_manager

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    logger.info("--- Starting HyperTrader Backend ---")
    
    # Initialize database
    await init_db()
    logger.info("Database connection initialized.")
    
    # Initialize exchange manager
    await exchange_manager.initialize()
    logger.info("Exchange manager initialized.")
    
    # Start market data monitoring
    # CORRECTED: Changed from .start() to .start_monitoring()
    await market_data_manager.start_monitoring()
    logger.info("Market data manager started.")
    
    yield  # Application is now running
    
    # --- Shutdown Events ---
    logger.info("--- Shutting Down HyperTrader Backend ---")
    await market_data_manager.stop_monitoring()
    await exchange_manager.close()
    await close_db_connection()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="HyperTrader API",
    description="Backend for the HyperTrader 4-phase hedging strategy bot.",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(endpoints.router, prefix="/api/v1")
app.include_router(websockets.router)

@app.get("/health")
def health_check():
    return {"status": "healthy", "app": "HyperTrader"}
