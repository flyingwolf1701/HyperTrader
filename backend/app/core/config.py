"""Configuration and settings for HyperTrader backend."""

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    database_url: str = "postgresql://user:password@localhost/hypertrader"
    
    # Exchange API
    exchange_api_key: Optional[str] = None
    exchange_secret: Optional[str] = None
    exchange_passphrase: Optional[str] = None
    exchange_sandbox: bool = True
    
    # WebSocket
    ws_url: Optional[str] = None
    
    # App
    debug: bool = False
    app_name: str = "HyperTrader"
    
    class Config:
        env_file = ".env"

settings = Settings()
