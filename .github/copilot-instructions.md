# Copilot Instructions for HyperTrader

## Project Overview
- **HyperTrader** is a real-time crypto trading system implementing a long-biased, 4-phase grid strategy (see `docs/strategy_doc_v10.md`).
- The architecture is split into a Python backend (core trading logic, order management, exchange integration) and a Nuxt 3/Vue 3 frontend (real-time dashboard, controls, visualization).

## Key Components & Data Flow
- **Backend (Python, `backend/`)**
  - Entry: `src/main.py` (see class `HyperTrader`)
  - Core logic: `src/strategy/` (sliding window, position map, unit tracker)
  - Exchange integration: `src/exchange/` (Hyperliquid SDK, WebSocket client)
  - Data models: `src/strategy/data_models.py`
  - All trading is based on a 4-order sliding window (see `UnitTracker` and `calculate_initial_position_map`).
- **Frontend (Nuxt 3, `frontend/`)**
  - Connects to backend at `http://localhost:3000` (default)
  - Real-time updates via WebSocket
  - UI: `app.vue`, `error.vue`, and components in `frontend/`

## Developer Workflows
- **Backend**
  - Run bot: `cd backend && uv run python src/main.py --symbol SOL --wallet long --unit-size 5.0 --position-size 200 --leverage 10 --testnet`
  - Utilities: `uv run python scripts/hl_commands.py status` (status), `hl_commands.py close SYMBOL` (close position)
  - Tests: `uv run python -m pytest tests/ -v` (all), `tests/test_simple.py` (core), `--cov=src` for coverage
- **Frontend**
  - Install: `bun install` or `npm install`
  - Dev server: `bun dev` or `npm run dev` (runs at `http://localhost:3001`)

## Project-Specific Patterns & Conventions
- **Strategy**: Always maintain exactly 4 active orders (see `docs/strategy_doc_v10.md`).
- **Fragments**: Position is split into 4 equal fragments for buy/sell logic.
- **Sliding Window**: Orders are dynamically shifted as price moves (see `UnitTracker`).
- **Data Models**: All state and events use centralized models in `data_models.py`.
- **Testing**: Use `pytest` with coverage; see `backend/README.md` for test file purposes.
- **Logging**: Uses `loguru` for structured logging.

## Integration & External Dependencies
- **Exchange**: Hyperliquid SDK (see `exchange/hyperliquid_sdk.py`)
- **WebSocket**: Real-time price and order updates (see `exchange/websocket_client.py`)
- **Frontend**: Expects backend running locally; communicates via REST/WebSocket.

## References
- Strategy: `docs/strategy_doc_v10.md`
- Data flow: `docs/data_flow.md` (if present)
- Main logic: `backend/src/main.py`, `backend/src/strategy/`
- Frontend: `frontend/README.md`

---

**For AI agents:**
- Always reference the above files for architecture and workflow.
- Follow the 4-order sliding window rule in all trading logic.
- Use the provided test suite for validation before deploying changes.
- When in doubt, check `docs/` for strategy and implementation details.
