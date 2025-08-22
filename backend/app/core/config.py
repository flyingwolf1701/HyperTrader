# backend/app/core/config.py

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional
import os
from decimal import Decimal


class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "HyperTrader"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 3000
    
    # Database Configuration
    DATABASE_URL: str = Field(..., description="Database connection URL")
    
    # CORS Settings
    FRONTEND_URL: str = "http://localhost:3001"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3001", "http://127.0.0.1:3001"]
    
    # HyperLiquid API Configuration
    HYPERLIQUID_API_KEY: str = Field(..., description="HyperLiquid API key")
    HYPERLIQUID_SECRET_KEY: str = Field(..., description="HyperLiquid secret key")
    HYPERLIQUID_TESTNET: bool = True
    HYPERLIQUID_BASE_URL: str = "https://api.hyperliquid.xyz"
    
    # WebSocket Configuration
    HYPERLIQUID_WS_URL: str = "wss://api.hyperliquid.xyz/ws"
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_RECONNECT_ATTEMPTS: int = 5
    
    # --- Trading Configuration ---
    SYMBOL: str = "ETH" # <-- THIS LINE WAS ADDED
    DEFAULT_LEVERAGE: int = 1
    MAX_POSITIONS: int = 20
    PORTFOLIO_CASH_RESERVE_PERCENT: Decimal = Decimal("10")
    SPOT_SAVINGS_PERCENT: Decimal = Decimal("0")
    
    # Risk Management
    MAX_DRAWDOWN_PERCENT: Decimal = Decimal("23")
    FIBONACCI_LEVELS: List[Decimal] = [
        Decimal("0.23"), 
        Decimal("0.38"), 
        Decimal("0.50"), 
        Decimal("0.618")
    ]
    STOP_LOSS_TRAILING_PERCENT: Decimal = Decimal("2")
    
    # Logging
    LOG_FILE: Optional[str] = "logs/hypertrader.log"
    
    # Security (for future use)
    SECRET_KEY: Optional[str] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_SECRET: Optional[str] = None
    
    @validator('ALLOWED_ORIGINS')
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            import ast
            try:
                return ast.literal_eval(v)
            except:
                return [v]
        return v
    
    @validator('DATABASE_URL')
    def validate_database_url(cls, v):
        if not v:
            raise ValueError("DATABASE_URL is required")
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "sslmode=" in v:
            if "sslmode=require" in v:
                v = v.replace("sslmode=require", "ssl=require")
            elif "sslmode=prefer" in v:
                v = v.replace("sslmode=prefer", "ssl=prefer")
        if "&channel_binding=require" in v:
            v = v.replace("&channel_binding=require", "")
        if "?channel_binding=require" in v:
            v = v.replace("?channel_binding=require", "")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


# Create global settings instance
settings = Settings()
