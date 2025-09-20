"""
Configuration management for HyperTrader v10 strategy
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class StrategyConfig:
    """Configuration parameters for v10 trading strategy"""

    # Required parameters
    symbol: str                    # Asset to trade (e.g., "SOL", "BTC")
    wallet: str                    # Wallet type (e.g., "long")
    unit_size: Decimal             # Price movement per unit in USD
    position_size: Decimal         # Total USD amount to allocate
    leverage: int                  # Leverage multiplier

    # Optional parameters with defaults
    testnet: bool = True           # Use testnet (True) or mainnet (False)

    @classmethod
    def from_args(cls, args) -> 'StrategyConfig':
        """Create config from command-line arguments"""
        return cls(
            symbol=args.symbol,
            wallet=args.wallet,
            unit_size=Decimal(str(args.unit_size)),
            position_size=Decimal(str(args.position_size)),
            leverage=args.leverage,
            testnet=args.testnet
        )

    @classmethod
    def from_dict(cls, data: dict) -> 'StrategyConfig':
        """Create config from dictionary (for API)"""
        return cls(
            symbol=data['symbol'],
            wallet=data['wallet'],
            unit_size=Decimal(str(data['unit_size'])),
            position_size=Decimal(str(data['position_size'])),
            leverage=data['leverage'],
            testnet=data.get('testnet', True)
        )

    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return {
            'symbol': self.symbol,
            'wallet': self.wallet,
            'unit_size': str(self.unit_size),
            'position_size': str(self.position_size),
            'leverage': self.leverage,
            'testnet': self.testnet
        }

    def validate(self) -> bool:
        """Validate configuration parameters"""
        if self.leverage < 1 or self.leverage > 100:
            raise ValueError(f"Leverage must be between 1 and 100, got {self.leverage}")

        if self.position_size <= 0:
            raise ValueError(f"Position size must be positive, got {self.position_size}")

        if self.unit_size <= 0:
            raise ValueError(f"Unit size must be positive, got {self.unit_size}")

        if self.symbol not in ['SOL', 'BTC', 'ETH', 'ARB', 'DOGE', 'MATIC', 'OP']:
            # Add more valid symbols as needed
            raise ValueError(f"Unsupported symbol: {self.symbol}")

        return True