"""
CCXT data types for exchange operations - SIMPLIFIED
"""
from dataclasses import dataclass
from typing import Dict, Optional, Any
from decimal import Decimal


@dataclass
class Market:
    """
    CCXT Market structure (simplified)
    """
    id: str
    symbol: str
    base: str
    quote: str
    active: bool
    type: str
    spot: bool
    swap: bool
    linear: bool
    inverse: bool
    contractSize: Optional[float] = None
    settle: Optional[str] = None
    taker: float = 0.0
    maker: float = 0.0
    info: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_ccxt_market(cls, market_data: Dict[str, Any]) -> "Market":
        """Create Market instance from CCXT market dictionary"""
        return cls(
            id=market_data.get('id', ''),
            symbol=market_data.get('symbol', ''),
            base=market_data.get('base', ''),
            quote=market_data.get('quote', ''),
            active=market_data.get('active', False),
            type=market_data.get('type', 'spot'),
            spot=market_data.get('spot', False),
            swap=market_data.get('swap', False),
            linear=market_data.get('linear', False),
            inverse=market_data.get('inverse', False),
            contractSize=market_data.get('contractSize'),
            settle=market_data.get('settle'),
            taker=market_data.get('taker', 0.0),
            maker=market_data.get('maker', 0.0),
            info=market_data.get('info')
        )


@dataclass
class Balance:
    """Account balance for a specific currency"""
    currency: str
    free: Decimal
    used: Decimal
    total: Decimal
    
    @classmethod
    def from_ccxt_balance(cls, currency: str, balance_data: Dict[str, Any]) -> "Balance":
        """Create Balance from CCXT balance data"""
        return cls(
            currency=currency,
            free=Decimal(str(balance_data.get("free", 0))),
            used=Decimal(str(balance_data.get("used", 0))),
            total=Decimal(str(balance_data.get("total", 0)))
        )
    
    @classmethod
    def empty(cls, currency: str) -> "Balance":
        """Create empty balance"""
        return cls(
            currency=currency,
            free=Decimal("0"),
            used=Decimal("0"),
            total=Decimal("0")
        )


@dataclass
class Position:
    """Trading position information"""
    symbol: str
    side: str  # "long" or "short"
    contracts: Decimal
    contractSize: Decimal
    unrealizedPnl: Decimal
    markPrice: Decimal
    entryPrice: Decimal
    info: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_ccxt_position(cls, position_data: Dict[str, Any]) -> "Position":
        """Create Position from CCXT position data"""
        return cls(
            symbol=position_data.get("symbol", ""),
            side=position_data.get("side", ""),
            contracts=Decimal(str(position_data.get("contracts", 0))),
            contractSize=Decimal(str(position_data.get("contractSize", 1))),
            unrealizedPnl=Decimal(str(position_data.get("unrealizedPnl", 0) or 0)),
            markPrice=Decimal(str(position_data.get("markPrice", 0) or 0)),
            entryPrice=Decimal(str(position_data.get("info", {}).get("entryPx", 0) or 0)),
            info=position_data.get("info")
        )


@dataclass
class Order:
    """Order information"""
    id: str
    symbol: str
    type: str
    side: str
    price: Decimal
    amount: Decimal
    status: str
    info: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_ccxt_order(cls, order_data: Dict[str, Any]) -> "Order":
        """Create Order from CCXT order data"""
        return cls(
            id=order_data.get("id", ""),
            symbol=order_data.get("symbol", ""),
            type=order_data.get("type", ""),
            side=order_data.get("side", ""),
            price=Decimal(str(order_data.get("price", 0))) if order_data.get("price") is not None else Decimal("0"),
            amount=Decimal(str(order_data.get("amount", 0))) if order_data.get("amount") is not None else Decimal("0"),
            status=order_data.get("status", ""),
            info=order_data.get("info")
        )


@dataclass 
class OrderResult:
    """Simplified order result for strategy operations"""
    id: str
    type: str
    price: Decimal
    eth_amount: Optional[Decimal] = None
    usd_amount: Optional[Decimal] = None
    usd_received: Optional[Decimal] = None
    usd_cost: Optional[Decimal] = None
    status: Optional[str] = None