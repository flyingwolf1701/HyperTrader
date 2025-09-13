# Profit Tracking System Guide

## Overview
The ProfitTracker provides comprehensive P&L tracking for the sliding window strategy, making it easy to understand performance despite the complexity of multiple orders and unit-based trading.

## Features

### Real-Time P&L Tracking
- **Realized P&L**: Tracks actual profits/losses from closed trades
- **Unrealized P&L**: Monitors current position value vs cost basis
- **Total P&L**: Combined realized + unrealized performance
- **Fees Tracking**: Accounts for all trading fees

### Trade Analytics
- **Win Rate**: Percentage of profitable trades
- **Trade Count**: Total, winning, and losing trades
- **Max Profit/Drawdown**: Peak performance metrics
- **Runtime Tracking**: Session duration monitoring

### Unit-Level Performance
- Tracks P&L by unit level to identify profitable zones
- Shows which price levels generate the most profit
- Helps optimize unit size and window placement

## How It Works

### 1. Initialization
When a position is established, ProfitTracker records:
```python
profit_tracker = ProfitTracker(
    symbol="ETH",
    initial_position_size=Decimal("0.5"),  # 0.5 ETH
    entry_price=Decimal("4500.00")
)
```

### 2. Trade Recording
Every fill is automatically tracked:
- **Stop-Loss Sells**: Recorded with realized P&L
- **Limit Buys**: Added to position, updates average entry
- **Market Orders**: Tracked with appropriate type

### 3. P&L Calculation

#### For Sells:
```
P&L = (Sell Price - Average Entry) * Size - Fees
```

#### For Position:
```
Unrealized = (Current Price - Average Entry) * Position Size
Total P&L = Realized + Unrealized - Total Fees
```

## Output Examples

### Periodic Summary (Every 5 Minutes)
```
============================================================
💰 PROFIT SUMMARY - ETH
============================================================
Position: 0.500000 @ $4500.00
Current Price: $4520.00
🟢 Realized P&L: $45.23
🟢 Unrealized P&L: $10.00
🟢 Total P&L: $55.23
Fees Paid: $2.50
Win Rate: 66.7% (2W/1L)
Total Trades: 4
Runtime: 2.5 hours
============================================================
```

### Trade Logging
```
📊 TRADE: SELL 0.125000 ETH @ $4525.00 (Unit -1) P&L: $3.13
📊 TRADE: BUY 0.125000 ETH @ $4515.00 (Unit 1)
```

## Understanding the Metrics

### Win Rate
- Calculated only on closed trades (sells)
- Higher win rate indicates strategy effectiveness
- Target: >50% for profitability after fees

### Unit Performance
Shows which levels are most profitable:
```python
unit_stats = profit_tracker.get_unit_performance()
# Returns: {
#   -2: {'pnl': 15.50, 'trades': 3},
#   -1: {'pnl': -5.25, 'trades': 2},
#   1: {'pnl': 8.75, 'trades': 1}
# }
```

### Average Entry Price
Updates dynamically with each buy:
- Initial: Entry price
- After buys: Weighted average of all purchases
- Critical for accurate P&L calculation

## Strategy Insights

### Profitable Patterns
1. **Tight Stops + Quick Rebuys**: Minimize losses, capture rebounds
2. **Unit Size Optimization**: Smaller units = more trades = smoother P&L
3. **Window Management**: 4 orders balance risk/opportunity

### Loss Patterns
1. **Trending Markets**: Multiple stops hit without rebuys
2. **Wide Units**: Miss profitable reversals
3. **Slow Execution**: Slippage on fills

## Integration Points

### Main.py
- Initialized with position creation
- Updated on every order fill
- Logged periodically (every 5 min)
- Final summary on shutdown

### Order Fills
```python
# Automatically tracked in handle_order_fill()
if filled_order_type == OrderType.STOP_LOSS_SELL:
    profit_tracker.add_trade(
        trade_type=TradeType.STOP_LOSS,
        side='sell',
        unit=filled_unit,
        price=filled_price,
        size=filled_size
    )
```

## Benefits

1. **Clarity**: Understand P&L despite complex order management
2. **Accountability**: Track every trade and fee
3. **Optimization**: Identify profitable/unprofitable patterns
4. **Confidence**: See real-time performance metrics
5. **Analysis**: Post-session performance review

## Future Enhancements

- Export to CSV for analysis
- Graphical P&L visualization
- Risk metrics (Sharpe ratio, etc.)
- Multi-symbol portfolio tracking
- Tax reporting features