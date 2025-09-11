"""
Asset configuration for Hyperliquid trading
Contains tick sizes and max leverage for all supported assets
"""

from decimal import Decimal
from typing import Dict, Any

# Asset configurations with tick size and max leverage
ASSET_CONFIG: Dict[str, Dict[str, Any]] = {
    "BTC": {
        "tick_size": Decimal("1.0"),
        "max_leverage": 40,
        "sz_decimals": 5  # Will be overridden by API if available
    },
    "ETH": {
        "tick_size": Decimal("0.1"),
        "max_leverage": 25,
        "sz_decimals": 4
    },
    "SOL": {
        "tick_size": Decimal("0.01"),
        "max_leverage": 20,
        "sz_decimals": 3
    },
    "HYPE": {
        "tick_size": Decimal("0.001"),
        "max_leverage": 10,
        "sz_decimals": 2
    },
    "ENA": {
        "tick_size": Decimal("0.0001"),
        "max_leverage": 10,
        "sz_decimals": 1
    },
    "DOGE": {
        "tick_size": Decimal("0.00001"),
        "max_leverage": 10,
        "sz_decimals": 0
    },
    "XRP": {
        "tick_size": Decimal("0.0001"),
        "max_leverage": 20,
        "sz_decimals": 0
    },
    "FARTCOIN": {
        "tick_size": Decimal("0.00001"),
        "max_leverage": 10,
        "sz_decimals": 0
    },
    "PUMP": {
        "tick_size": Decimal("0.00001"),
        "max_leverage": 5,
        "sz_decimals": 0
    },
    "LINK": {
        "tick_size": Decimal("0.001"),
        "max_leverage": 10,
        "sz_decimals": 2
    },
    "AVAX": {
        "tick_size": Decimal("0.001"),
        "max_leverage": 10,
        "sz_decimals": 2
    },
    "SUI": {
        "tick_size": Decimal("0.0001"),
        "max_leverage": 10,
        "sz_decimals": 1
    },
    "AAVA": {
        "tick_size": Decimal("0.01"),
        "max_leverage": 10,
        "sz_decimals": 2
    },
    "ARB": {
        "tick_size": Decimal("0.0001"),
        "max_leverage": 10,
        "sz_decimals": 1
    },
    "PENGU": {
        "tick_size": Decimal("0.00001"),
        "max_leverage": 5,
        "sz_decimals": 0
    },
    "kBONK": {
        "tick_size": Decimal("0.000001"),
        "max_leverage": 10,
        "sz_decimals": 0
    },
    "kPEPE": {
        "tick_size": Decimal("0.000000001"),
        "max_leverage": 10,
        "sz_decimals": 0
    },
    "MNT": {
        "tick_size": Decimal("0.0001"),
        "max_leverage": 5,
        "sz_decimals": 1
    },
    "CRV": {
        "tick_size": Decimal("0.0001"),
        "max_leverage": 10,
        "sz_decimals": 1
    },
    "SEI": {
        "tick_size": Decimal("0.0001"),
        "max_leverage": 10,
        "sz_decimals": 1
    },
    "UNI": {
        "tick_size": Decimal("0.001"),
        "max_leverage": 10,
        "sz_decimals": 2
    },
    "OP": {
        "tick_size": Decimal("0.001"),
        "max_leverage": 10,
        "sz_decimals": 2
    },
    "MOODENG": {
        "tick_size": Decimal("0.00001"),
        "max_leverage": 5,
        "sz_decimals": 0
    },
    "TAO": {
        "tick_size": Decimal("0.1"),
        "max_leverage": 5,
        "sz_decimals": 3
    },
    "INJ": {
        "tick_size": Decimal("0.001"),
        "max_leverage": 10,
        "sz_decimals": 2
    },
    "LDO": {
        "tick_size": Decimal("0.001"),
        "max_leverage": 10,
        "sz_decimals": 2
    },
    "NEAR": {
        "tick_size": Decimal("0.001"),
        "max_leverage": 10,
        "sz_decimals": 2
    },
    "JUP": {
        "tick_size": Decimal("0.0001"),
        "max_leverage": 10,
        "sz_decimals": 1
    },
    "HBAR": {
        "tick_size": Decimal("0.00001"),
        "max_leverage": 5,
        "sz_decimals": 0
    },
    "kSHIB": {
        "tick_size": Decimal("0.000000001"),
        "max_leverage": 10,
        "sz_decimals": 0
    },
    "DOT": {
        "tick_size": Decimal("0.001"),
        "max_leverage": 10,
        "sz_decimals": 2
    },
    "XLM": {
        "tick_size": Decimal("0.00001"),
        "max_leverage": 10,
        "sz_decimals": 0
    },
    "PURR": {
        "tick_size": Decimal("0.0000001"),
        "max_leverage": 3,
        "sz_decimals": 0
    },
}

def get_asset_config(symbol: str) -> Dict[str, Any]:
    """
    Get configuration for a specific asset.
    
    Args:
        symbol: Trading symbol (e.g., "ETH", "BTC")
        
    Returns:
        Dictionary with tick_size, max_leverage, and sz_decimals
        
    Raises:
        ValueError if symbol not found
    """
    if symbol not in ASSET_CONFIG:
        raise ValueError(f"Asset {symbol} not configured. Available assets: {', '.join(ASSET_CONFIG.keys())}")
    
    return ASSET_CONFIG[symbol]

def get_tick_size(symbol: str) -> Decimal:
    """Get tick size for a symbol"""
    return get_asset_config(symbol)["tick_size"]

def get_max_leverage(symbol: str) -> int:
    """Get max leverage for a symbol"""
    return get_asset_config(symbol)["max_leverage"]

def is_valid_leverage(symbol: str, leverage: int) -> bool:
    """Check if leverage is valid for a symbol"""
    max_lev = get_max_leverage(symbol)
    return 1 <= leverage <= max_lev

def round_to_tick(price: Decimal, symbol: str) -> Decimal:
    """
    Round a price to the correct tick size for a symbol.
    
    Args:
        price: Price to round
        symbol: Trading symbol
        
    Returns:
        Price rounded to nearest tick
    """
    tick_size = get_tick_size(symbol)
    # Use Decimal arithmetic to avoid floating point precision issues
    multiplier = price / tick_size
    rounded_multiplier = multiplier.quantize(Decimal('1'), rounding='ROUND_HALF_UP')
    return rounded_multiplier * tick_size

def get_all_symbols() -> list:
    """Get list of all configured symbols"""
    return list(ASSET_CONFIG.keys())