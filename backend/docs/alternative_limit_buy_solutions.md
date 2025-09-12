# Alternative Solutions for Limit Buy Orders Above Market

## The Problem
- **Take Profit (TP) orders don't work for entries** - they execute immediately at market price
- Regular limit buys above market are invalid
- We need orders that wait for price to rise before buying

## Working Solutions

### Solution 1: Price Monitoring with Instant Execution (RECOMMENDED)
**How it works:**
- Track target buy levels in memory (not as orders)
- Monitor price continuously via WebSocket
- When price crosses target level, immediately place market or limit order

**Implementation:**
```python
class PendingBuyTracker:
    def __init__(self):
        self.pending_buys = {}  # unit -> (price, size)
    
    def add_pending_buy(self, unit, price, size):
        self.pending_buys[unit] = (price, size)
    
    async def check_and_execute(self, current_price):
        for unit, (target_price, size) in list(self.pending_buys.items()):
            if current_price >= target_price:
                # Price reached! Place immediate order
                await place_market_order("buy", size)
                del self.pending_buys[unit]
```

**Pros:**
- Guaranteed to work
- Full control over execution logic
- Can add sophisticated conditions

**Cons:**
- Requires continuous monitoring
- Not "fire and forget"

### Solution 2: Use Stop Orders on Short Position (Complex)
**How it works:**
- Open a small short position
- Use stop-loss on the short (which is a buy) at target price
- When triggered, it buys to cover short + extra for long

**Pros:**
- Uses native order types
- Set and forget

**Cons:**
- Requires maintaining short position
- Complex position management
- Risk of liquidation

### Solution 3: Alerts + Manual/Semi-Auto Execution
**How it works:**
- Set price alerts at target levels
- When alert triggers, automatically or manually place buy
- Can use Telegram/Discord bots for notifications

**Pros:**
- Simple to implement
- Human oversight

**Cons:**
- Not fully automated
- Delay in execution

### Solution 4: Use Different Exchange Features
Some exchanges offer:
- **OCO (One-Cancels-Other) orders**
- **Conditional orders**
- **If-Then orders**

Need to check if Hyperliquid has these in their roadmap.

### Solution 5: Ladder of Regular Limit Orders (Partial Solution)
**How it works:**
- Place regular limit buys at decreasing prices below market
- As price drops, orders fill
- Not for buying on the way up, but captures dips

**Pros:**
- Works with standard orders
- Captures volatility

**Cons:**
- Opposite of what we want (buys on drops, not rises)

## Recommended Implementation

### Hybrid Approach: Memory Tracking + Instant Execution

```python
class SmartBuyManager:
    def __init__(self, sdk_client):
        self.sdk_client = sdk_client
        self.pending_buys = {}  # unit -> BuyTarget
        self.last_check_price = None
    
    def schedule_buy_at_unit(self, unit: int, price: Decimal, size: Decimal):
        """Schedule a buy when price reaches this level"""
        self.pending_buys[unit] = {
            'price': price,
            'size': size,
            'added_at': datetime.now(),
            'status': 'pending'
        }
        logger.info(f"📌 Scheduled buy at unit {unit}: {size} @ ${price}")
    
    async def check_pending_buys(self, current_price: Decimal):
        """Check if any pending buys should execute"""
        if not self.pending_buys:
            return
        
        # Only check if price moved up significantly
        if self.last_check_price and current_price <= self.last_check_price:
            return
        
        executed = []
        for unit, target in self.pending_buys.items():
            if current_price >= target['price'] and target['status'] == 'pending':
                # Execute buy!
                logger.warning(f"🎯 Price hit ${target['price']} - Executing buy for unit {unit}")
                
                # Use limit order slightly above current to ensure fill
                limit_price = current_price + Decimal("1")  
                result = await self.sdk_client.place_limit_order(
                    symbol=self.symbol,
                    is_buy=True,
                    price=limit_price,
                    size=target['size'],
                    reduce_only=False,
                    post_only=False  # Allow taker
                )
                
                if result.success:
                    logger.info(f"✅ Buy executed for unit {unit}")
                    target['status'] = 'executed'
                    executed.append(unit)
                else:
                    logger.error(f"❌ Buy failed for unit {unit}: {result.error_message}")
        
        # Clean up executed orders
        for unit in executed:
            del self.pending_buys[unit]
        
        self.last_check_price = current_price
```

## Implementation Plan

1. **Remove stop limit buy attempts** - they don't work for entries
2. **Add PendingBuyTracker class** to main.py
3. **Track pending buys** instead of placing orders
4. **Check on every price update** from WebSocket
5. **Execute immediately** when price reached

## Benefits
- **100% reliable** - no order type complications
- **Fast execution** - triggers instantly on price cross
- **Flexible** - can add complex conditions
- **Transparent** - clear logging of what's waiting

## Code Changes Needed

1. Replace `_place_limit_buy_order` logic for above-market orders
2. Add `PendingBuyTracker` class
3. Call `check_pending_buys()` in `_handle_price_update()`
4. Track pending buys in position map with special status
5. Show pending buys in status logs