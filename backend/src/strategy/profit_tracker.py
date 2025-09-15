"""
Profit Tracking System for HyperTrader
Tracks P&L, trades, and performance metrics for the sliding window strategy
"""

from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class TradeType(Enum):
    """Type of trade executed"""
    INITIAL_ENTRY = "initial_entry"
    STOP_LOSS = "stop_loss"
    LIMIT_BUY = "limit_buy"
    MARKET_BUY = "market_buy"
    MARKET_SELL = "market_sell"
    STOP_LIMIT_BUY = "stop_limit_buy"


@dataclass
class Trade:
    """Individual trade record"""
    timestamp: datetime
    trade_type: TradeType
    side: str  # 'buy' or 'sell'
    unit: int
    price: Decimal
    size: Decimal
    usd_value: Decimal
    order_id: Optional[str] = None
    fees: Decimal = Decimal("0")
    
    @property
    def net_value(self) -> Decimal:
        """Net USD value after fees"""
        if self.side == 'buy':
            return self.usd_value + self.fees  # Cost basis
        else:
            return self.usd_value - self.fees  # Proceeds
    

@dataclass
class PositionSnapshot:
    """Snapshot of position at a point in time"""
    timestamp: datetime
    current_price: Decimal
    position_size: Decimal
    position_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    total_pnl: Decimal
    current_unit: int
    active_stops: List[int]
    active_buys: List[int]
    win_rate: Decimal
    total_trades: int


class ProfitTracker:
    """
    Comprehensive profit tracking for sliding window strategy
    """
    
    def __init__(self, symbol: str, initial_position_size: Decimal, entry_price: Decimal):
        """
        Initialize profit tracker
        
        Args:
            symbol: Trading symbol (e.g., "ETH")
            initial_position_size: Initial position size in asset
            entry_price: Entry price for initial position
        """
        self.symbol = symbol
        self.initial_position_size = initial_position_size
        self.entry_price = entry_price
        
        # Trade tracking
        self.trades: List[Trade] = []
        self.winning_trades = 0
        self.losing_trades = 0
        
        # Position tracking
        self.current_position_size = initial_position_size
        self.average_entry_price = entry_price
        self.total_bought = initial_position_size
        self.total_sold = Decimal("0")
        
        # P&L tracking
        self.realized_pnl = Decimal("0")
        self.fees_paid = Decimal("0")
        
        # Unit-based tracking
        self.unit_pnl: Dict[int, Decimal] = {}  # P&L by unit level
        self.unit_trades: Dict[int, List[Trade]] = {}  # Trades by unit
        
        # Performance metrics
        self.max_drawdown = Decimal("0")
        self.max_profit = Decimal("0")
        self.session_start = datetime.now()
        
        # Add initial entry trade
        self.add_trade(
            trade_type=TradeType.INITIAL_ENTRY,
            side='buy',
            unit=0,
            price=entry_price,
            size=initial_position_size,
            fees=Decimal("0")
        )
        
        logger.info(f"ProfitTracker initialized for {symbol} - Entry: ${entry_price:.2f}, Size: {initial_position_size}")
    
    def add_trade(self, trade_type: TradeType, side: str, unit: int, 
                  price: Decimal, size: Decimal, fees: Decimal = Decimal("0"),
                  order_id: Optional[str] = None) -> Trade:
        """
        Record a new trade and update P&L
        
        Args:
            trade_type: Type of trade
            side: 'buy' or 'sell'
            unit: Unit level where trade occurred
            price: Execution price
            size: Trade size in asset
            fees: Trading fees in USD
            order_id: Optional order ID
            
        Returns:
            Trade object that was recorded
        """
        # Create trade record
        usd_value = price * size
        trade = Trade(
            timestamp=datetime.now(),
            trade_type=trade_type,
            side=side,
            unit=unit,
            price=price,
            size=size,
            usd_value=usd_value,
            order_id=order_id,
            fees=fees
        )
        
        self.trades.append(trade)
        self.fees_paid += fees
        
        # Update unit tracking
        if unit not in self.unit_trades:
            self.unit_trades[unit] = []
        self.unit_trades[unit].append(trade)
        
        # Update position and P&L
        if side == 'buy':
            self._process_buy(trade)
        else:
            self._process_sell(trade)
        
        # Log the trade
        pnl_str = f"P&L: ${self.realized_pnl:.2f}" if side == 'sell' else ""
        logger.info(
            f"📊 TRADE: {side.upper()} {size:.6f} {self.symbol} @ ${price:.2f} "
            f"(Unit {unit}) {pnl_str}"
        )
        
        return trade
    
    def _process_buy(self, trade: Trade):
        """Process a buy trade"""
        # Update position
        old_value = self.current_position_size * self.average_entry_price
        new_value = trade.size * trade.price
        self.current_position_size += trade.size
        self.total_bought += trade.size
        
        # Update average entry price
        if self.current_position_size > 0:
            self.average_entry_price = (old_value + new_value) / self.current_position_size
    
    def _process_sell(self, trade: Trade):
        """Process a sell trade and calculate realized P&L"""
        if self.current_position_size <= 0:
            logger.warning("Sell trade with no position!")
            return
        
        # Calculate P&L for this trade
        cost_basis = trade.size * self.average_entry_price
        proceeds = trade.usd_value
        trade_pnl = proceeds - cost_basis - trade.fees
        
        self.realized_pnl += trade_pnl
        
        # Update win/loss tracking
        if trade_pnl > 0:
            self.winning_trades += 1
        elif trade_pnl < 0:
            self.losing_trades += 1
        
        # Update unit P&L
        if trade.unit not in self.unit_pnl:
            self.unit_pnl[trade.unit] = Decimal("0")
        self.unit_pnl[trade.unit] += trade_pnl
        
        # Update position
        self.current_position_size -= trade.size
        self.total_sold += trade.size
        
        # Update max drawdown/profit
        if self.realized_pnl < self.max_drawdown:
            self.max_drawdown = self.realized_pnl
        if self.realized_pnl > self.max_profit:
            self.max_profit = self.realized_pnl
    
    def get_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized P&L at current price"""
        if self.current_position_size <= 0:
            return Decimal("0")
        
        current_value = self.current_position_size * current_price
        cost_basis = self.current_position_size * self.average_entry_price
        return current_value - cost_basis
    
    def get_total_pnl(self, current_price: Decimal) -> Decimal:
        """Get total P&L (realized + unrealized)"""
        return self.realized_pnl + self.get_unrealized_pnl(current_price)
    
    def get_win_rate(self) -> Decimal:
        """Calculate win rate percentage"""
        total_closed = self.winning_trades + self.losing_trades
        if total_closed == 0:
            return Decimal("0")
        return Decimal(self.winning_trades) / Decimal(total_closed) * 100
    
    def get_position_snapshot(self, current_price: Decimal, current_unit: int,
                            active_stops: List[int], active_buys: List[int]) -> PositionSnapshot:
        """Get comprehensive position snapshot"""
        unrealized = self.get_unrealized_pnl(current_price)
        total = self.get_total_pnl(current_price)
        
        return PositionSnapshot(
            timestamp=datetime.now(),
            current_price=current_price,
            position_size=self.current_position_size,
            position_value=self.current_position_size * current_price,
            unrealized_pnl=unrealized,
            realized_pnl=self.realized_pnl,
            total_pnl=total,
            current_unit=current_unit,
            active_stops=active_stops.copy(),
            active_buys=active_buys.copy(),
            win_rate=self.get_win_rate(),
            total_trades=len(self.trades)
        )
    
    def get_summary(self, current_price: Decimal) -> Dict:
        """Get profit tracking summary"""
        unrealized = self.get_unrealized_pnl(current_price)
        total = self.get_total_pnl(current_price)
        runtime = (datetime.now() - self.session_start).total_seconds() / 3600  # Hours
        
        return {
            'symbol': self.symbol,
            'runtime_hours': round(runtime, 2),
            'current_position': float(self.current_position_size),
            'average_entry': float(self.average_entry_price),
            'current_price': float(current_price),
            'realized_pnl': float(self.realized_pnl),
            'unrealized_pnl': float(unrealized),
            'total_pnl': float(total),
            'fees_paid': float(self.fees_paid),
            'total_trades': len(self.trades),
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': float(self.get_win_rate()),
            'max_profit': float(self.max_profit),
            'max_drawdown': float(self.max_drawdown),
            'total_bought': float(self.total_bought),
            'total_sold': float(self.total_sold)
        }
    
    def log_profit_summary(self, current_price: Decimal):
        """Log a formatted profit summary"""
        summary = self.get_summary(current_price)
        
        # Format P&L with colors
        realized_color = "🟢" if summary['realized_pnl'] >= 0 else "🔴"
        unrealized_color = "🟢" if summary['unrealized_pnl'] >= 0 else "🔴"
        total_color = "🟢" if summary['total_pnl'] >= 0 else "🔴"
        
        logger.info("=" * 60)
        logger.info(f"💰 PROFIT SUMMARY - {self.symbol}")
        logger.info("=" * 60)
        logger.info(f"Position: {summary['current_position']:.6f} @ ${summary['average_entry']:.2f}")
        logger.info(f"Current Price: ${summary['current_price']:.2f}")
        logger.info(f"{realized_color} Realized P&L: ${summary['realized_pnl']:.2f}")
        logger.info(f"{unrealized_color} Unrealized P&L: ${summary['unrealized_pnl']:.2f}")
        logger.info(f"{total_color} Total P&L: ${summary['total_pnl']:.2f}")
        logger.info(f"Fees Paid: ${summary['fees_paid']:.2f}")
        logger.info(f"Win Rate: {summary['win_rate']:.1f}% ({summary['winning_trades']}W/{summary['losing_trades']}L)")
        logger.info(f"Total Trades: {summary['total_trades']}")
        logger.info(f"Runtime: {summary['runtime_hours']:.1f} hours")
        logger.info("=" * 60)
    
    def get_unit_performance(self) -> Dict[int, Dict]:
        """Get P&L breakdown by unit level"""
        unit_stats = {}
        
        for unit, trades in self.unit_trades.items():
            sells = [t for t in trades if t.side == 'sell']
            buys = [t for t in trades if t.side == 'buy']
            
            unit_stats[unit] = {
                'total_trades': len(trades),
                'buys': len(buys),
                'sells': len(sells),
                'pnl': float(self.unit_pnl.get(unit, Decimal("0"))),
                'avg_price': float(sum(t.price for t in trades) / len(trades)) if trades else 0
            }
        
        return unit_stats