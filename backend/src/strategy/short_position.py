"""
Short Position tracking for accurate P&L calculation
"""
from decimal import Decimal
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class ShortPosition:
    """Track individual short positions for accurate P&L calculation"""
    usd_amount: Decimal      # Original USD amount shorted
    entry_price: Decimal     # Price when short was opened
    eth_amount: Decimal      # ETH amount of the short
    unit_opened: int         # Unit level when opened (for tracking)
    
    def get_current_value(self, current_price: Decimal) -> Decimal:
        """Calculate current value including unrealized P&L"""
        pnl_per_eth = self.entry_price - current_price  # Profit if price dropped
        total_pnl = pnl_per_eth * self.eth_amount
        return self.usd_amount + total_pnl
    
    def get_pnl(self, current_price: Decimal) -> Decimal:
        """Get current P&L of this short position"""
        pnl_per_eth = self.entry_price - current_price
        return pnl_per_eth * self.eth_amount
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence"""
        return {
            "usd_amount": float(self.usd_amount),
            "entry_price": float(self.entry_price),
            "eth_amount": float(self.eth_amount),
            "unit_opened": self.unit_opened
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShortPosition':
        """Create from dictionary"""
        return cls(
            usd_amount=Decimal(str(data["usd_amount"])),
            entry_price=Decimal(str(data["entry_price"])),
            eth_amount=Decimal(str(data["eth_amount"])),
            unit_opened=data["unit_opened"]
        )
