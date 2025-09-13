# Order Auditor System Guide

## Problem Solved
After hours of trading with multiple unit changes, orders can get chaotic:
- Duplicate orders at the same price level
- Missing orders that should exist
- Orphan orders that don't match any unit
- Orders that should have been cancelled but weren't

The OrderAuditor ensures your actual exchange orders always match your intended sliding window state.

## How It Works

### 1. Regular Audits
Every 2 minutes (and after each unit change), the system:
- Fetches all live orders from the exchange
- Compares them to expected orders (trailing_stop + trailing_buy lists)
- Identifies discrepancies
- Auto-corrects issues

### 2. Discrepancy Detection

#### Missing Orders
- Expected: Stop at unit -2
- Actual: No order at that price
- Action: Place the missing stop order

#### Duplicate Orders
- Expected: 1 stop at unit -1
- Actual: 3 stops at $115,816
- Action: Keep first, cancel duplicates

#### Orphan Orders
- Orders that don't match any expected unit price
- Usually from failed cancellations or manual interference
- Action: Cancel these orders

#### Unexpected Orders
- Orders at units not in trailing_stop or trailing_buy
- Leftover from old window positions
- Action: Cancel these orders

### 3. Auto-Correction
When discrepancies are found:
1. Cancels unwanted orders first
2. Places missing orders second
3. Verifies corrections after 30 seconds

## Audit Output Examples

### Healthy Audit
```
🔍 AUDIT #15 - Starting order reconciliation
✅ AUDIT PASSED - All orders correctly placed
```

### Problematic Audit
```
🔍 AUDIT #16 - Starting order reconciliation
⚠️ AUDIT FAILED - Found 5 discrepancies
❌ MISSING ORDERS at units: [-2, 1]
❌ DUPLICATE ORDERS at units: [-1]
   Unit -1: 2 duplicates - ['39047123456', '39047123457']
❌ ORPHAN ORDERS (not matching any unit): 3
   Order 39047123458 at $115,500.00
🔧 AUTO-CORRECTION: 5 cancels, 2 places
✅ Cancelled order 39047123456
✅ Cancelled order 39047123457
✅ Cancelled order 39047123458
✅ Placed stop order at unit -2
✅ Placed buy order at unit 1
✅ AUTO-CORRECTION COMPLETE - 7 total corrections made
```

## Audit Triggers

### Scheduled Audits
- Every 2 minutes during normal operation
- Ensures gradual drift is caught and corrected

### Forced Audits
- 2 seconds after every unit change
- Catches issues when orders are most likely to get chaotic
- Verifies sliding window operations completed correctly

### Post-Correction Audits
- 30 seconds after any correction
- Verifies corrections were successful

## Configuration

### Price Tolerance
Orders are matched to units with a $0.50 tolerance:
```python
order_auditor = OrderAuditor(
    symbol="BTC",
    unit_size_usd=Decimal("50"),
    tolerance=Decimal("0.50")  # $0.50 price tolerance
)
```

### Audit Frequency
- Regular: Every 2 minutes
- After unit change: 2 seconds delay
- After correction: 30 seconds delay

## Benefits

### 1. Prevents Order Chaos
Your screenshot showed multiple stops at similar prices - the auditor prevents this accumulation.

### 2. Maintains Window Integrity
Always ensures exactly 4 orders in your sliding window.

### 3. Reduces Slippage
Duplicate orders can cause unexpected fills and slippage.

### 4. Saves Fees
Cancels unnecessary orders that would waste fees.

### 5. Peace of Mind
Know that your orders always match your strategy's intent.

## Statistics Tracking

The auditor tracks:
- Total audits performed
- Total corrections made
- Last audit time and status
- Number of discrepancies found

Access via:
```python
summary = order_auditor.get_summary()
# {
#   'audit_count': 42,
#   'corrections_made': 15,
#   'last_healthy': True,
#   'last_discrepancies': 0
# }
```

## Manual Intervention

If auto-correction fails repeatedly:
1. Check exchange status/maintenance
2. Verify API permissions
3. Check for rate limits
4. Consider manual order cleanup
5. Restart bot after clearing orders

## Integration with Strategy

The auditor works seamlessly with:
- **UnitTracker**: Uses trailing_stop and trailing_buy lists
- **PositionMap**: Matches orders to expected prices
- **SDK Client**: Fetches live orders and executes corrections

## Best Practices

1. **Let it run**: Don't manually place/cancel orders while bot is running
2. **Monitor logs**: Watch for repeated correction failures
3. **Check after restarts**: Force an audit after bot restarts
4. **Adjust tolerance**: Increase if orders aren't matching due to price precision

## Troubleshooting

### Orders Not Matching Units
- Increase price tolerance
- Check for decimal precision issues
- Verify position_map prices are correct

### Corrections Failing
- Check API rate limits
- Verify exchange connectivity
- Check order minimum sizes
- Review error messages in logs

### Too Many Audits
- Normal after volatile periods
- Should stabilize once corrections applied
- Check if external interference (manual trading)

The OrderAuditor is your safety net, ensuring that no matter how chaotic the market or how many unit changes occur, your actual orders always match your intended strategy!