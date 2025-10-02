# HyperTrader

## Starting the Trading Bot
``` bash
.venv\Scripts\activate
```

**Parameters:**

- `--symbol`: Trading symbol (e.g., SOL, BTC, ETH)
- `--strategy`: Trading strategy (currently only 'long' is implemented)
- `--unit-size-usd`: USD per unit movement (e.g., 0.5 = $0.50 price moves)
- `--position-value-usd`: Total position value in USD (e.g., 100 = $100 position)
- `--leverage`: Leverage multiplier (e.g., 10, 20, 40)
- `--testnet`: Use testnet (default: True for safety) 

**Full Examples:**

```bash
cd backend

# Small position on SOL with 10x leverage (testnet by default)
uv run python src/main.py --symbol SOL --strategy long --unit-size-usd 0.25 --position-value-usd 100 --leverage 10 --testnet

# Medium position on SOL with 20x leverage (testnet)
uv run python src/main.py --symbol SOL --strategy long --unit-size-usd 0.5 --position-value-usd 2000 --leverage 20 --testnet

# Large position on BTC with 40x leverage (testnet)
uv run python src/main.py --symbol BTC --strategy long --unit-size-usd 25 --position-value-usd 2000 --leverage 40 --testnet

# Medium position on ETH with 25x leverage
uv run python src/main.py --symbol ETH --strategy long --unit-size-usd 0.5 --position-value-usd 2500 --leverage 25 --testnet
```

## Utility Commands

```bash
cd backend

# Check account status and all open positions
uv run python scripts/hl_commands.py status

# Close a position AND cancel all open orders for a symbol
uv run python scripts/hl_commands.py close SOL

# Close position on a different symbol
uv run python scripts/hl_commands.py close BTC
uv run python scripts/hl_commands.py close ETH
```

## Emergency Stop

To immediately stop the bot and close everything:

1. Press `Ctrl+C` in the terminal running the bot to stop it
2. Run the close command to close the position and cancel all orders:
   ```bash
   uv run python scripts/hl_commands.py close [SYMBOL]
   ```

## Prompt
first read docs\strategy_doc_v11.md to understand the context of the project. And read backend\pyproject.toml to understand the dependancies.
Read backend\src\exchange to understand how we connect to to Hyperliquid
Read backend\src\main.py and the files under backend\src\strategy to see how we are handling our strategy

## How the bot is supposed to work
1. (working) We place our initial order:
   - current_unit = 0, 
   - trailing_stop = [-4, -3, -2, -1], 
   - trailing_buy =[] 
   - notice that order furthest from current_unit is index 0
2. If the price goes up (from current_unit = 0)
   - current_unit = 1 --> Price went up from unit 0 to unit 1
   - trailing_stop = [-4, -3, -2, -1, 0] --> Place new stop loss at current_unit - 1 (unit 0). 
   - trailing_buy = [] --> Do nothing. 
   - trailing_stop = [-3, -2, -1, 0] --> Cancel the stop loss at index 0 (unit -4).
   - Fragments invested 4/4 
   - First we place the new stop loss at unit 0 this is critical, then we cancel the unit at index 0 in the trailing_stop list.
   - all we need for this is to check if current_price >= position_map[current+unit + 1].price if so place new trailing stop at current_unit - 1, then cancel trailing_stop index 0
   - if we gap up from 1 to 4 really fast, that is ok we will loop through current_price >= position_map[current+unit + 1].price and take action 1 unit at a time until we catch up. this way we don't have to calculate or do anything fancy, its ok if we have a delay. we will catch up
3. If price continues to go up when Fragments invested 4/4 we simply repeat step 2.  
4. If price goes down (from current_unit = 1)
   - current_unit = 0 -->price went down from unit 1 to unit 0
   - trailing_stop = [-3, -2, -1] --> Stop loss at unit 0 was triggered 
   - trailing_buy = [1] --> assume stop at 0 is triggered, no confirmation required. place trailing_buy at current_unit 1. 
   - Fragments invested 3/4 
   - Note: It is critical that the system playce the buy order immediately after checking if we already have an active buy at that unit.
   - Note: We should only have one active order per unit at a time
   - Note: system will update the stop loss sale in position_map when it gets the data from hyperliquid, what is more important is placing the buy order immediately. 
5. If price goes down (from current_unit = 0)
   - current_unit = -1 --> price went down from unit 0 to unit -1
   - trailing_stop = [-3, -2] --> Stop loss at unit -1 was triggered
   - trailing_buy = [1, 0] --> assume stop at -1 is triggered, no confirmation required. place trailing_buy at current_unit 0. 
   - Fragments invested 2/4 
6. If price goes down (from current_unit = -1)
   - current_unit = -2 --> price went down from unit -1 to unit -2
   - trailing_stop = [-3] --> Stop loss at unit -2 was triggered
   - trailing_buy =[1, 0, -1] --> assume stop at -2 is triggered, no confirmation required. place trailing_buy at current_unit -1. 
   - Fragments invested 1/4 
7. If price goes down (from current_unit = -2)
   - current_unit = -3 --> price went down from unit -2 to unit -3
   - trailing_stop = [] --> Stop loss at unit -3 was triggered
   - trailing_buy = [1, 0, -1, -2] --> assume stop at -3 is triggered, no confirmation required. place trailing_buy at current_unit -2.  
   - Fragments invested 0/4 
8. If price goes down (from current_unit = -3)
   - current_unit = -4 --> price went down from unit -3 to unit -4
   - trailing_stop = [] --> Fully out of position
   - trailing_buy = [1, 0, -1, -2, -3] --> new buy order placed at current_unit + 1, cancel the order at index 0. --> trailing_buy = [0, -1, -2, -3]
   - Fragments invested 0/4 
   - Note: trailing_buy's length is > 4. that trigger is to cancel the order at index 0. leaving us with trailing_buy = [0, -1, -2, -3]
9. If price continues to go down when Fragments invested 0/4 we simply repeat step 8.
10. If price goes up (from current_unit = -4)
   - current_unit = -3 --> price went up from unit -4 to unit -3
   - trailing_stop = [-4] --> Place new stop loss at current_unit - 1 (unit -4). 
   - trailing_buy = [0, -1, -2] --> buy order at unit -3 triggered
   - Fragments invested 1/4
11. If price goes up (from current_unit = -3)
   - current_unit = -2 --> price went up from unit -3 to unit -2
   - trailing_stop = [-4, -3] --> Place new stop loss at current_unit - 1 (unit -3). 
   - trailing_buy = [0, -1,] --> buy order at unit -2 triggered
   - Fragments invested 2/4
12. If price goes up (from current_unit = -2)
   - current_unit = -1 --> price went up from unit -2 to unit -1
   - trailing_stop = [-4, -3, -2] --> Place new stop loss at current_unit - 1 (unit -2). 
   - trailing_buy = [0] --> buy order at unit -1 triggered
   - Fragments invested 3/4
13. If price goes up (from current_unit = -1)
   - current_unit = 0 --> price went up from unit -1 to unit 0
   - trailing_stop = [-4, -3, -2, -1] --> Place new stop loss at current_unit - 1 (unit -1). 
   - trailing_buy = [] --> buy order at unit 0 triggered
   - Fragments invested 4/4
14. At this point we are back to step 2

Whipsaws: when price rapidly goes down then up then down up then down then up again (3 -> 2 -> 3 -> 2 -> 3)

1. **initial order placement unit 0**
   trailing_buy = []
   current_unit = 0, price = $200, unit_size = $5.00 
   trailing_stop = [-4, -3, -2, -1]
   fragments = 4/4
### Trailing down smooth  
2. **down unit: 0 -> -1**
   Trailing_buy = [0]
   current_unit = -1, price = $195, unit_size = $5.00 
   trailing_stop = [-4, -3, -2]
   fragments 3/4
3. **down  unit: -1 -> -2**
   Trailing_buy = [0, -1]
   current_unit = -2, price = $190, unit_size = $5.00 
   trailing_stop = [-4, -3]
   fragments 2/4
4. **down unit: -2 -> -3**
   Trailing_buy = [0, -1, -2]
   current_unit = -3, price = $185, unit_size = $5.00 
   trailing_stop = [-4]
   fragments 1/4
5. **down unit: -3 -> -4**
   Trailing_buy = [0, -1, -2, -3]
   current_unit = -4, price = $180, unit_size = $5.00 
   trailing_stop = []
   fragments 0/4
6. **down unit: -4 -> -5**
   Trailing_buy =[-1, -2, -3, -4]
   current_unit = -5, price = $175, unit_size = $5.00 
   trailing_stop = []
   fragments 0/4
7. **down unit: -5 -> -6**
   Trailing_buy = [-2, -3, -4, -5]
   current_unit = -6, price = $170, unit_size = $5.00 
   trailing_stop = []
   fragments 0/4
8. **down unit: -6 -> -7**
   Trailing_buy = [-3, -4, -5, -6]
   current_unit = -7, price = $165, unit_size = $5.00 
   trailing_stop = []
   fragments 0/4
### Trailing Up Smooth 
9. **up unit: -7 -> -6**
   Trailing_buy = [-3, -4, -5]
   current_unit = -6, price = $170, unit_size = $5.00 
   trailing_stop = [-7]
   fragments 1/4
10. **up unit: -6 -> -5**
   Trailing_buy = [-3, -4]
   current_unit = -5, price = $175, unit_size = $5.00 
   trailing_stop = [-7, -6]
   fragments 2/4
11. **up unit: -5 -> -4**
   Trailing_buy = [-3]
   current_unit = -4, price = $180, unit_size = $5.00 
   trailing_stop = [-7, -6, -5]
   fragments 3/4
12. **up unit: -4 -> -3**
   Trailing_buy = []
   current_unit = -3, price = $185, unit_size = $5.00 
   trailing_stop = [-7, -6, -5, -4]
   fragments 4/4  
13. **up unit: -3 -> -2**
   Trailing_buy = []
   current_unit = -2, price = $190, unit_size = $5.00 
   trailing_stop = [-6, -5, -4, -3]
   fragments 4/4
14. **up unit: -2 -> -1**
   Trailing_buy = []
   current_unit = -1, price = $195, unit_size = $5.00 
   trailing_stop = [-5, -4, -3, -2]
   fragments 4/4

### Whipsaw Volitility
  
### Example 1 - OLD
15. **up unit: -1 -> 0**
   Trailing_buy = []
   current_unit = 0, price = $200, unit_size = $5.00 
   trailing_stop = [-4, -3, -2, -1]
   fragments 4/4
16. **down unit: 0 -> -1**
   Trailing_buy = [0]
   current_unit = -1, price = $195, unit_size = $5.00 
   trailing_stop = [-4, -3, -2]
   fragments 3/4
17. **up unit: -1 -> 0**
   Trailing_buy = []
   current_unit = 0, price = $200, unit_size = $5.00 
   trailing_stop = [-4, -3, -2, -1]
   fragments 4/4
### Example 2 - NEW whipsaw then continue down
18. **up unit: -1 -> 0**
   Trailing_buy = []
   current_unit = 0, price = $200, unit_size = $5.00 
   trailing_stop = [-4, -3, -2, -1]
   fragments 4/4
19. **down unit: 0 -> -1**
   Trailing_buy = [0]
   current_unit = -1, price = $195, unit_size = $5.00 
   trailing_stop = [-4, -3, -2]
   fragments 3/4
20. **up unit: -1 -> 0** whipsaw detected
   Trailing_buy = []
   current_unit = 0, price = $200, unit_size = $5.00 
   trailing_stop = [-5, -4, -3, -2] # We need to have 4 sell orders at this point instead of placing it at unit -1 we place it at unit -5 to give a little breathing room. 
   fragments 4/4
21. **down unit: 0 -> -1** Notice, Nothing changes no sell is triggered. If we continued down, we would continue on the trailing down smooth path. 
   Trailing_buy = []
   current_unit = -1, price = $195, unit_size = $5.00 
   trailing_stop = [-5, -4, -3, -2]
   fragments 4/4
22. **down unit: -1 -> -2** If we continued down, we would continue on the trailing down smooth path. 
   Trailing_buy = [-1]
   current_unit = -2, price = $190, unit_size = $5.00 
   trailing_stop = [-5, -4, -3]
   fragments 3/4
23. **up unit: -2 -> -1** and if we continued up, we would continue on the trailing up smooth path. 
   Trailing_buy = []
   current_unit = -1, price = $195, unit_size = $5.00 
   trailing_stop = [-5, -4, -3, -2]
   fragments 4/4
### Example 2 - NEW whipsaw then continue up
24. **up unit: -1 -> 0** 
   Trailing_buy = []
   current_unit = 0, price = $200, unit_size = $5.00 
   trailing_stop = [-4, -3, -2, -1]
   fragments 4/4
25. **down unit: 0 -> -1**
   Trailing_buy = [0]
   current_unit = -1, price = $195, unit_size = $5.00 
   trailing_stop = [-4, -3, -2]
   fragments 3/4
26. **up unit: -1 -> 0** whipsaw detected
   Trailing_buy = []
   current_unit = 0, price = $200, unit_size = $5.00 
   trailing_stop = [-5, -4, -3, -2] # We need to have 4 sell orders at this point instead of placing it at unit -1 we place it at unit -5 to give a little breathing room. 
   fragments 4/4
27. **up unit: 0 -> 1** Notice, Nothing changes no buy is triggered. If we continued up, we would continue on the trailing up smooth path. 
   Trailing_buy = []
   current_unit = 1, price = $205, unit_size = $5.00 
   trailing_stop = [-5, -4, -3, -2]
   fragments 4/4
28. **up unit: 1 -> 2** This is where we need to catch up
   Trailing_buy = []
   current_unit = 2, price = $210, unit_size = $5.00 
   was trailing_stop = [-5, -4, -3, -2] #here we add both -1 and -2 and cancel/remove -5 and -4
   to trailing_stop = [-3, -2, -1, 0]
   fragments 4/4