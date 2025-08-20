from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

from app.core.config import settings
from app.db.session import init_db, close_db
from app.api import endpoints, websockets
from app.services.exchange import exchange_manager

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting HyperTrader backend...")
    
    # Initialize database connection
    await init_db()
    logger.info("Database connection initialized")
    
    # Initialize exchange manager
    await exchange_manager.initialize()
    logger.info("Exchange manager initialized")
    
    yield
    
    # Cleanup
    logger.info("Shutting down HyperTrader backend...")
    await exchange_manager.close()
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    description="Advanced crypto trading bot with hedging strategy",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(endpoints.router, prefix="/api/v1")
app.include_router(websockets.router, prefix="/ws")


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