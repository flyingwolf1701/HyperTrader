"""Exchange integration module"""
from .hyperliquid_sdk import HyperliquidClient

# Backward compatibility aliases
HyperliquidExchangeClient = HyperliquidClient
HyperliquidSDK = HyperliquidClient

__all__ = ['HyperliquidClient', 'HyperliquidExchangeClient', 'HyperliquidSDK']
