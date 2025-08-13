from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Database
    database_url: str = Field(..., description="PostgreSQL database URL")
    
    # Application
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=3000)
    
    # CORS
    frontend_url: str = Field(default="http://localhost:3001")
    allowed_origins: List[str] = Field(default=["http://localhost:3001", "http://127.0.0.1:3001"])
    
    # HyperLiquid API
    hyperliquid_api_key: str = Field(..., description="HyperLiquid API key")
    hyperliquid_secret_key: str = Field(..., description="HyperLiquid secret key")
    hyperliquid_testnet: bool = Field(default=True)
    hyperliquid_base_url: str = Field(default="https://api.hyperliquid.xyz")
    
    # WebSocket
    hyperliquid_ws_url: str = Field(default="wss://api.hyperliquid.xyz/ws")
    ws_heartbeat_interval: int = Field(default=30)
    ws_reconnect_attempts: int = Field(default=5)
    
    # Trading Configuration
    default_leverage: int = Field(default=1)
    max_positions: int = Field(default=20)
    portfolio_cash_reserve_percent: int = Field(default=20)
    spot_savings_percent: int = Field(default=10)
    
    # Risk Management
    max_drawdown_percent: int = Field(default=23)
    fibonacci_levels: List[float] = Field(default=[0.23, 0.38, 0.50, 0.618])
    stop_loss_trailing_percent: int = Field(default=2)
    
    # Logging
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="logs/hypertrader.log")
    
    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production")
    access_token_expire_minutes: int = Field(default=30)


# Global settings instance
settings = Settings()
