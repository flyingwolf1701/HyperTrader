import os
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
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
    hyperliquid_base_url: str = "https://api.hyperliquid-testnet.xyz"
    
    # HyperLiquid Sub-Wallet Configuration
    hyperliquid_testnet_subwallet_long: Optional[str] = None
    hyperliquid_testnet_subwallet_long_private: Optional[str] = None
    
    # WebSocket Configuration
    hyperliquid_ws_url: str = "wss://api.hyperliquid-testnet.xyz/ws"
    ws_heartbeat_interval: int = 30
    ws_reconnect_attempts: int = 5
    
    # Trading Configuration
    default_leverage: int = 10
    max_positions: int = 20
    portfolio_cash_reserve_percent: int = 10
    spot_savings_percent: int = 0
    unit_percentage: float = 5.0
    
    # Logging Configuration
    log_level: str = "DEBUG"
    log_file: str = "logs/hypertrader.log"
    
    # Security (for future production use)
    secret_key: str = "default-secret-key"
    access_token_expire_minutes: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from .env


# Global settings instance
settings = Settings()


def get_long_subwallet_credentials(testnet: bool = True):
    """Get the appropriate sub-wallet credentials for long positions"""
    if testnet:
        wallet_key = (settings.hyperliquid_testnet_subwallet_long 
                     if settings.hyperliquid_testnet_subwallet_long 
                     else settings.hyperliquid_wallet_key)
        private_key = (settings.hyperliquid_testnet_subwallet_long_private 
                      if settings.hyperliquid_testnet_subwallet_long_private 
                      else settings.hyperliquid_private_key)
    else:
        # For mainnet, fall back to main wallet for now
        wallet_key = settings.hyperliquid_wallet_key
        private_key = settings.hyperliquid_private_key
    
    return wallet_key, private_key