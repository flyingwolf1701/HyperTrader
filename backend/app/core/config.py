import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from decimal import Decimal

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    HYPERLIQUID_WALLET_KEY: str = os.getenv("HYPERLIQUID_WALLET_KEY", "")
    HYPERLIQUID_PRIVATE_KEY: str = os.getenv("HYPERLIQUID_PRIVATE_KEY", "")
    HYPERLIQUID_TESTNET: bool = os.getenv("HYPERLIQUID_TESTNET", "True").lower() in ('true', '1', 't')
    
    
    API_PORT: int = int(os.getenv("API_PORT", 8000))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ('true', '1', 't')

    # --- NEW: Add configurable unit percentage ---
    # Loads the unit percentage from .env, defaulting to 5.0% if not set.
    UNIT_PERCENTAGE: float = float(os.getenv("UNIT_PERCENTAGE", "5.0"))

    class Config:
        case_sensitive = True

# Create a single settings instance for the application to use
settings = Settings()
