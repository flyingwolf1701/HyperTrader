"""
HyperTrader FastAPI Application

Main FastAPI application with CORS configuration and API router setup.
Serves as the backend for the HyperTrader Fibonacci hedging trading system.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager for startup and shutdown tasks."""
    # Startup tasks
    print(f"🚀 Starting HyperTrader backend on {settings.api_host}:{settings.api_port}")
    print(f"📈 Environment: {settings.environment}")
    print(f"🔗 CORS enabled for: {settings.allowed_origins}")
    
    yield
    
    # Shutdown tasks
    print("🛑 Shutting down HyperTrader backend")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="HyperTrader API",
        description="FastAPI backend for HyperTrader Fibonacci hedging trading system",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )
    
    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint for monitoring."""
        return JSONResponse(
            content={
                "status": "healthy",
                "service": "HyperTrader API",
                "version": "0.1.0",
                "environment": settings.environment,
            }
        )
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return JSONResponse(
            content={
                "message": "HyperTrader API",
                "description": "Fibonacci hedging trading system backend",
                "docs": "/docs" if settings.debug else None,
                "health": "/health",
            }
        )
    
    return app


# Create the FastAPI application instance
app = create_app()