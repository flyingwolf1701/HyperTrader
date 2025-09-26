# HyperTrader

## Starting the Trading Bot

**Parameters:**

- `--symbol`: Trading symbol (e.g., SOL, BTC, ETH)
- `--strategy`: Trading strategy (e.g., long, short)
- `--unit-size`: USD per unit movement (e.g., 0.5 = $0.50 price moves)
- `--position-size`: Position value in USD (e.g., 100 = $100 position)
- `--leverage`: Leverage multiplier (e.g., 10, 20, 40)
- `--testnet`: Use testnet (default: True during dev phase) no flag = False 

**Full Examples:**

```bash
cd backend

# Small position on SOL with 10x leverage
uv run python src/main.py --symbol SOL --strategy long --unit-size 0.5 --position-size 100 --leverage 10 --testnet

# Medium position on SOL with 20x leverage
uv run python src/main.py --symbol SOL --strategy long --unit-size 0.5 --position-size 2000 --leverage 20 --testnet

# Large position on BTC with 40x leverage
uv run python src/main.py --symbol BTC --strategy long --unit-size 25 --position-size 20000 --leverage 40 --testnet

# Medium position on ETH with 25x leverage
uv run python src/main.py --symbol ETH --strategy long --unit-size 1 --position-size 12500 --leverage 25 --testnet
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