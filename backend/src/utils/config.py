import os
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database Configuration
    database_url: str
    
    # Application Settings
    environment: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # CORS Settings
    frontend_url: str = "http://localhost:3001"
    allowed_origins: List[str] = ["http://localhost:3001", "http://127.0.0.1:3001"]
    
    # HyperLiquid API Configuration
    hyperliquid_wallet_key: str
    hyperliquid_private_key: str
    hyperliquid_testnet: bool = True
    
    # Trading Configuration
    default_leverage: int = 10
    unit_percentage: float = 5.0
    
    # Logging Configuration
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()