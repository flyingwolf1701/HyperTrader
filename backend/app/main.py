from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.logging import configure_logging, setup_standard_logging_intercept
from app.api import endpoints
from app.services.exchange import exchange_manager
from app.services.market_data import market_data_manager
from app.services.websocket import websocket_manager
from app.services.unit_tracker import unit_tracker

# Configure loguru logging
configure_logging()
setup_standard_logging_intercept()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    logger.info("--- Starting HyperTrader Backend ---")
    
    
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

@app.get("/health")
def health_check():
    return {"status": "healthy", "app": "HyperTrader"}
