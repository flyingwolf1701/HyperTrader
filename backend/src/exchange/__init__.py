"""Exchange integration module"""
from .hyperliquid_sdk import HyperliquidClient
from .wallet_config import WalletConfig, WalletType

# Backward compatibility aliases
HyperliquidExchangeClient = HyperliquidClient
HyperliquidSDK = HyperliquidClient

__all__ = ['HyperliquidClient', 'HyperliquidExchangeClient', 'HyperliquidSDK', 'WalletConfig', 'WalletType']
