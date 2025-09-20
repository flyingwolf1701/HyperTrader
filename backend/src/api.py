"""
HyperTrader v10 - FastAPI Application
Provides REST API endpoints for strategy management
Access Swagger UI at: http://localhost:8000/docs
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Optional
from decimal import Decimal
import asyncio
from loguru import logger
from dotenv import load_dotenv

from core.config import StrategyConfig
from core.strategy_runner import StrategyRunner

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="HyperTrader v10 API",
    description="API for managing the v10 long-biased grid trading strategy",
    version="10.0.0"
)

# Add CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global strategy runner instance
strategy_runner: Optional[StrategyRunner] = None


# Pydantic models for API
class StrategyStartRequest(BaseModel):
    """Request model for starting strategy"""
    symbol: str = Field(..., description="Trading symbol (e.g., SOL, BTC, ETH)")
    wallet: str = Field(..., description="Wallet type (e.g., long)")
    unit_size: float = Field(..., gt=0, description="Price movement per unit in USD")
    position_size: float = Field(..., gt=0, description="Total USD amount to allocate")
    leverage: int = Field(..., ge=1, le=100, description="Leverage multiplier (1-100)")
    testnet: bool = Field(True, description="Use testnet (True) or mainnet (False)")

    class Config:
        schema_extra = {
            "example": {
                "symbol": "SOL",
                "wallet": "long",
                "unit_size": 0.5,
                "position_size": 2000,
                "leverage": 20,
                "testnet": True
            }
        }


class StrategyResponse(BaseModel):
    """Response model for strategy operations"""
    status: str
    message: str
    data: Optional[Dict] = None


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "HyperTrader v10 API",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/strategy/start", response_model=StrategyResponse)
async def start_strategy(request: StrategyStartRequest, background_tasks: BackgroundTasks):
    """
    Start the trading strategy with specified parameters.

    This endpoint initializes and starts the v10 grid trading strategy.
    Only one strategy instance can run at a time.
    """
    global strategy_runner

    # Check if strategy is already running
    if strategy_runner and strategy_runner.running:
        raise HTTPException(status_code=400, detail="Strategy is already running")

    # Create configuration
    try:
        config_dict = request.dict()
        config = StrategyConfig.from_dict(config_dict)
        config.validate()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")

    # Log the request
    logger.info(f"Starting strategy via API: {config_dict}")

    # Create and start strategy runner
    strategy_runner = StrategyRunner(config)

    # Start strategy in background
    async def run_strategy_background():
        try:
            result = await strategy_runner.start()
            if result["status"] == "success":
                # Keep strategy running
                await asyncio.gather(*strategy_runner.tasks)
        except Exception as e:
            logger.error(f"Strategy error: {e}")

    background_tasks.add_task(run_strategy_background)

    # Wait a moment for initialization
    await asyncio.sleep(2)

    return StrategyResponse(
        status="success",
        message=f"Strategy starting for {config.symbol}",
        data=config.to_dict()
    )


@app.post("/strategy/stop", response_model=StrategyResponse)
async def stop_strategy():
    """
    Stop the currently running strategy.

    This will cancel all open orders and close connections.
    """
    global strategy_runner

    if not strategy_runner or not strategy_runner.running:
        raise HTTPException(status_code=400, detail="No strategy is running")

    result = await strategy_runner.stop()

    # Clear the runner
    strategy_runner = None

    return StrategyResponse(
        status=result["status"],
        message=result["message"]
    )


@app.get("/strategy/status", response_model=StrategyResponse)
async def get_strategy_status():
    """
    Get the current status of the trading strategy.

    Returns detailed information about the running strategy including:
    - Current grid state
    - Active orders
    - Realized PnL
    - Current unit position
    """
    global strategy_runner

    if not strategy_runner:
        return StrategyResponse(
            status="info",
            message="No strategy instance",
            data={"running": False}
        )

    status = await strategy_runner.get_status()

    return StrategyResponse(
        status="success",
        message="Strategy status retrieved",
        data=status
    )


@app.get("/strategy/config")
async def get_strategy_config():
    """
    Get the current strategy configuration.

    Returns the configuration parameters of the running strategy.
    """
    global strategy_runner

    if not strategy_runner:
        raise HTTPException(status_code=400, detail="No strategy is running")

    return {
        "status": "success",
        "config": strategy_runner.config.to_dict()
    }


@app.post("/strategy/validate")
async def validate_config(request: StrategyStartRequest):
    """
    Validate strategy configuration without starting.

    Useful for checking if parameters are valid before starting the strategy.
    """
    try:
        config_dict = request.dict()
        config = StrategyConfig.from_dict(config_dict)
        config.validate()

        total_exposure = config.position_size * config.leverage

        return {
            "status": "valid",
            "message": "Configuration is valid",
            "details": {
                "symbol": config.symbol,
                "position_size": str(config.position_size),
                "leverage": config.leverage,
                "total_exposure": str(total_exposure),
                "network": "testnet" if config.testnet else "mainnet"
            }
        }
    except ValueError as e:
        return {
            "status": "invalid",
            "message": str(e)
        }


# Run with: uvicorn src.api:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)