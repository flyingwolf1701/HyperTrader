"""
Pending Buy Tracker for HyperTrader
Tracks buy orders that should execute when price rises to target levels
Since Hyperliquid doesn't support stop limit buys for entries, we track in memory
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from loguru import logger


@dataclass
class PendingBuy:
    """Represents a pending buy order waiting for price to rise"""
    unit: int
    target_price: Decimal
    size: Decimal
    fragment_usd: Decimal
    created_at: datetime
    status: str = 'pending'  # pending, executing, executed, failed
    order_id: Optional[str] = None


class PendingBuyTracker:
    """
    Tracks buy orders that should execute when price rises.
    This replaces stop limit buy orders which don't work for entries.
    """
    
    def __init__(self, symbol: str):
        """
        Initialize the pending buy tracker.
        
        Args:
            symbol: Trading symbol (e.g., "BTC")
        """
        self.symbol = symbol
        self.pending_buys: Dict[int, PendingBuy] = {}
        self.last_check_price: Optional[Decimal] = None
        self.executed_count = 0
        self.failed_count = 0
        
    def add_pending_buy(self, unit: int, target_price: Decimal, size: Decimal, fragment_usd: Decimal) -> bool:
        """
        Add a pending buy order that will execute when price reaches target.
        
        Args:
            unit: Unit level for this buy
            target_price: Price at which to execute buy
            size: Size in base currency
            fragment_usd: USD value of the order
            
        Returns:
            True if added successfully
        """
        if unit in self.pending_buys:
            logger.warning(f"Unit {unit} already has pending buy at ${self.pending_buys[unit].target_price:.2f}")
            return False
        
        pending_buy = PendingBuy(
            unit=unit,
            target_price=target_price,
            size=size,
            fragment_usd=fragment_usd,
            created_at=datetime.now()
        )
        
        self.pending_buys[unit] = pending_buy
        logger.warning(f"📌 PENDING BUY SCHEDULED at unit {unit}: {size:.6f} {self.symbol} @ ${target_price:.2f}")
        logger.info(f"   Will execute when price rises to ${target_price:.2f} (Value: ${fragment_usd:.2f})")
        
        return True
    
    def check_for_executions(self, current_price: Decimal) -> List[PendingBuy]:
        """
        Check if any pending buys should execute at current price.
        
        Args:
            current_price: Current market price
            
        Returns:
            List of pending buys that should execute
        """
        if not self.pending_buys:
            return []
        
        # Skip if price hasn't moved up
        if self.last_check_price and current_price <= self.last_check_price:
            return []
        
        ready_to_execute = []
        
        for unit, pending_buy in self.pending_buys.items():
            if pending_buy.status != 'pending':
                continue
                
            # Check if price has reached target
            if current_price >= pending_buy.target_price:
                logger.warning(f"🎯 PRICE REACHED ${current_price:.2f} >= Target ${pending_buy.target_price:.2f}")
                logger.info(f"   Triggering buy for unit {unit}")
                pending_buy.status = 'executing'
                ready_to_execute.append(pending_buy)
        
        self.last_check_price = current_price
        return ready_to_execute
    
    def mark_executed(self, unit: int, order_id: str) -> None:
        """
        Mark a pending buy as successfully executed.
        
        Args:
            unit: Unit level of executed buy
            order_id: Order ID from exchange
        """
        if unit in self.pending_buys:
            self.pending_buys[unit].status = 'executed'
            self.pending_buys[unit].order_id = order_id
            self.executed_count += 1
            logger.info(f"✅ Pending buy at unit {unit} marked as executed (Order: {order_id})")
            
            # Remove from pending
            del self.pending_buys[unit]
    
    def mark_failed(self, unit: int, reason: str) -> None:
        """
        Mark a pending buy as failed.
        
        Args:
            unit: Unit level of failed buy
            reason: Reason for failure
        """
        if unit in self.pending_buys:
            self.pending_buys[unit].status = 'failed'
            self.failed_count += 1
            logger.error(f"❌ Pending buy at unit {unit} failed: {reason}")
            
            # Keep in pending for retry
            self.pending_buys[unit].status = 'pending'
    
    def cancel_pending_buy(self, unit: int) -> bool:
        """
        Cancel a pending buy order.
        
        Args:
            unit: Unit level to cancel
            
        Returns:
            True if cancelled successfully
        """
        if unit in self.pending_buys:
            logger.info(f"Cancelling pending buy at unit {unit}")
            del self.pending_buys[unit]
            return True
        return False
    
    def get_pending_summary(self) -> Dict:
        """
        Get summary of pending buy orders.
        
        Returns:
            Dictionary with pending buy information
        """
        pending_units = []
        total_value = Decimal("0")
        
        for unit, pending_buy in self.pending_buys.items():
            if pending_buy.status == 'pending':
                pending_units.append(unit)
                total_value += pending_buy.fragment_usd
        
        return {
            'pending_count': len(pending_units),
            'pending_units': pending_units,
            'total_value_usd': float(total_value),
            'executed_total': self.executed_count,
            'failed_total': self.failed_count
        }
    
    def get_pending_at_unit(self, unit: int) -> Optional[PendingBuy]:
        """
        Get pending buy at specific unit.
        
        Args:
            unit: Unit level to check
            
        Returns:
            PendingBuy if exists, None otherwise
        """
        return self.pending_buys.get(unit)
    
    def clear_all(self) -> int:
        """
        Clear all pending buy orders.
        
        Returns:
            Number of orders cleared
        """
        count = len(self.pending_buys)
        self.pending_buys.clear()
        logger.info(f"Cleared {count} pending buy orders")
        return count
    
    def log_status(self) -> None:
        """Log current status of pending buys."""
        if not self.pending_buys:
            logger.debug("No pending buy orders")
            return
        
        logger.info(f"📊 PENDING BUYS: {len(self.pending_buys)} orders waiting")
        for unit, pending_buy in sorted(self.pending_buys.items()):
            wait_time = (datetime.now() - pending_buy.created_at).total_seconds()
            logger.info(
                f"   Unit {unit}: ${pending_buy.target_price:.2f} "
                f"({pending_buy.size:.6f} {self.symbol}) "
                f"- Waiting {wait_time:.0f}s"
            )