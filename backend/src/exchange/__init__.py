"""Exchange integration module"""
from .exchange_client import HyperliquidExchangeClient

# Backward compatibility alias
HyperliquidSDK = HyperliquidExchangeClient

__all__ = ['HyperliquidExchangeClient', 'HyperliquidSDK']
