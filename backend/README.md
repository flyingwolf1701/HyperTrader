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

We place our initial order
current_unit = 0, trailing_stop = [-4, -3, -2, -1], trailing_buy =[] notice that order furthest from current_unit is index 0
Price goes up: current_unit = 1, trailing_stop = [-4, -3, -2, -1, 0], trailing_buy =[]. First we place the new stop loss at unit 0 this is critical, then we cancel the unit at index 0 in the trailing_stop list asynchronously. so that trailing_stop = [-3, -2, -1, 0]
all we need for this is to check if current_price >= position_map[current+unit + 1].price if so place new trailing stop at current_unit - 1, then cancel trailing_stop index 0
if we gap up from 1 to 4 really fast, that is ok we will loop through current_price >= position_map[current+unit + 1].price and take action 1 unit at a time until we catch up. this way we don't have to calculate or do anything fancy, its ok if we have a delay. we will catch up

If price goes down: starting at current_unit = 1
current_unit = 0, trailing_stop = [-3, -2, -1, 0], trailing_buy =[]. assume stop at 0 is triggered, no confirmation required. place trailing_buy at 1. system will update the stop loss sale when it gets the data, what is more important is placing the buy order immediately. so that we are now trailing_stop = [-3, -2, -1], trailing_buy =[1].
current_unit = -1, trailing_stop = [-3, -2, -1], trailing_buy =[1]. assume stop at -1 is triggered, no confirmation required. place trailing_buy at 0. so that we are now trailing_stop = [-3, -2], trailing_buy =[1, 0]. notice that the order closest to current_unit is in the last position. 
current_unit = -2, trailing_stop = [-3, -2], trailing_buy =[1, 0]. assume stop at -2 is triggered, no confirmation required. place trailing_buy at -1. so that we are now trailing_stop = [-3], trailing_buy =[1, 0, -1]. 
current_unit = -3, trailing_stop = [-3], trailing_buy =[1, 0, -1]. assume stop at -3 is triggered, no confirmation required. place trailing_buy at -2. so that we are now trailing_stop = [], trailing_buy =[1, 0, -1, -2]. 
current_unit = -4, trailing_stop = [], trailing_buy =[1, 0, -1, -2]. no stops to trigger. place trailing_buy at -3. so that we are now trailing_stop = [], trailing_buy =[1, 0, -1, -2, -3]. notice that trailing_buy's length is > 4. that trigger is to cancel the order at index 0. leaving us with trailing_buy =[0, -1, -2, -3]

If we gap down then we just process 1 unit at a time until we are caught up.

The whip saw section will have to be updated with this in mind as well. Please reread docs\strategy_doc_v11.md. You will see that what I just descripbes is fairly clear. and you will be able to see where you went wrong. Then you can start fixing things!

```

#### How to Run the Script Now
With this fix, you can run the script from the `backend` directory as you were trying to:
```bash
# Make sure you are in the 'backend' directory
python scripts/generate_price_grid.py
```

### 2. Fixing the `pytest` Error

The `pytest` error is happening for the exact same reason: `pytest` can't find the `src` directory when it tries to import your test file. This is made worse because the standard convention is to have the `tests` directory at the same level as `src`, not inside it.

Here is the most robust and conventional way to fix this for good:

**Step 1: Restructure Your Test Directory**
* Move your test directory from `backend/src/test` to `backend/tests`.

**Step 2: Run `pytest` from the Root**
* Navigate to your `backend` directory in the terminal.
* Run the `pytest` command by itself. It will automatically discover and run all your test files.

```bash
# Make sure you are in the 'backend' directory
pytest
```

If you want to run only one file, you can now do so easily:
```bash
# From the 'backend' directory
pytest tests/test_overall.py