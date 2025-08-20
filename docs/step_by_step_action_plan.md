This document provides a sequential, step-by-step plan for building the full-stack HyperTrader application. Each phase builds upon the last, ensuring a logical and structured development process from backend setup to frontend deployment.
Note: This plan assumes the project dependencies are already installed as specified in the pyproject.toml and package.json files using the uv package manager.
Phase 1: Backend Foundation & Project Setup
Goal: Establish the project structure, configure the FastAPI backend, and connect to the database.
Create File Structure: Create the hypertrader directory with the backend and frontend subdirectories as outlined in the architectural plan.
Activate Backend Environment:
Navigate into backend/.
Activate the virtual environment managed by uv (e.g., source .venv/bin/activate).
Configure Environment (.env):
Create a .env file in the backend/ root.
Add your DATABASE_URL for Neon PostgreSQL and your Hyperliquid API_KEY and SECRET.
Setup FastAPI Entrypoint (/app/main.py):
Create the basic FastAPI app instance.
Implement startup and shutdown events to manage the database connection pool.
Include the API routers that will be created in a later step.
Implement Configuration (/app/core/config.py):
Use Pydantic's BaseSettings to create a Settings class that automatically loads variables from the .env file. This provides a single, type-safe source for all configuration.
Establish Database Connection (/app/db/session.py):
Using SQLAlchemy 2.0, create an AsyncEngine and an async_sessionmaker.
Write a dependency function (get_db_session) that yields an async session to be used in API endpoints.
Phase 2: Backend Models & Services
Goal: Define all data structures and create the service layer that interacts with the database and the exchange.
Define Pydantic Model (/app/models/state.py):
Create the SystemState Pydantic BaseModel.
Ensure all financial fields (EntryPrice, UnitValue, etc.) are explicitly typed using from decimal import Decimal.
Define SQLAlchemy Models (/app/schemas/):
Create a SQLAlchemy ORM model for TradingPlan. It should have an ID, a symbol, and a JSONB column to store the SystemState object.
Create a model for UserFavorite with columns for user_id (for future multi-user support) and symbol.
Build Exchange Service (/app/services/exchange.py):
Create an ExchangeManager class.
In its __init__, initialize the ccxt.async_support version of the Hyperliquid exchange, passing in API keys from the config and setting enableRateLimit=True.
Implement async wrapper methods:
place_order(symbol, type, side, amount)
fetch_markets()
get_current_price(symbol)
Phase 3: Core Trading Logic & API Endpoints
Goal: Implement the heart of the trading bot and expose it via REST and WebSocket APIs.
Implement Trading Logic (/app/services/trading_logic.py):
Following the four-phase model, create the functions: handleAdvancePhase, handleRetracementPhase, handleDeclinePhase, and handleRecoveryPhase.
Each function will accept a SystemState object, perform its logic, and return the modified state. If a trade is needed, it will call the ExchangeManager service.
Create the main OnUnitChange function that acts as the central controller, determining the phase and calling the appropriate handler.
Implement the performSystemReset function.
Build REST API (/app/api/endpoints.py):
Create a new APIRouter.
Implement the endpoints defined in the plan (/trade/start, /exchange/pairs, /user/favorites), injecting the DB session and services as dependencies.
Build WebSocket (/app/api/websockets.py):
Create another APIRouter for the WebSocket at /ws/{symbol}.
This endpoint will contain the main application loop:
Load the SystemState from the database.
Connect to the exchange's public price feed WebSocket.
Listen for price ticks in an infinite loop.
On each tick, calculate the currentUnit.
If the unit has changed, call OnUnitChange, await the result.
Save the updated state to the database.
Broadcast the new state to all connected frontend clients.
Phase 4: Frontend Foundation & State Management
Goal: Set up the Nuxt project and establish the real-time connection to the backend.
Initialize Nuxt Project:
Navigate into frontend/.
Run npx nuxi@latest init . to create the Nuxt 3 project.
Define Types: Create a types/ directory and define a TypeScript interface for SystemState that exactly matches the Pydantic model.
Create State Composables (/composables/):
useSystemState.ts: Implement a simple composable using useState to hold the global SystemState object.
useWebSocket.ts: Create a composable that manages the WebSocket connection to the FastAPI backend. It should have connect(symbol) and disconnect() methods. The onmessage handler should parse the incoming data and update the useSystemState composable.
Phase 5: Frontend UI Development
Goal: Build the user interface components and pages.
Build Components (/components/):
Create each of the UI components as planned: StatusIndicator.vue, AllocationDisplay.vue, PnlTracker.vue, etc.
These components should be "dumb"—they receive data as props and display it. They will get their data from the pages.
Build Pages (/pages/):
pairs.vue: On mount, fetch data from the /exchange/pairs backend endpoint. Display the pairs in a list and allow favoriting, which triggers API calls to the /user/favorites endpoint.
trade/new.vue: Create a form for starting a new trade. The symbol dropdown should be populated by fetching from the /user/favorites endpoint.
index.vue: This will be the main dashboard. On mount, it will call the useWebSocket.connect() method. It will then pass the reactive data from useSystemState down to the various display components.
Phase 6: Testing & Validation
Goal: Implement the full testing suite to ensure correctness and reliability.
Backend Unit Tests (/backend/tests/unit/):
Set up pytest and pytest-asyncio.
Write tests for the trading logic in trading_logic.py. Use Hypothesis to generate a wide variety of SystemState inputs to test the phase handlers under many conditions. Mock the ExchangeManager and database calls.
Frontend Unit Tests (/frontend/tests/unit/):
Set up vitest.
Write tests for your composables. For example, test that useWebSocket correctly updates useSystemState when a mock message is received.
Write component tests to ensure they render the correct information based on sample props.
Contract Tests (Pact):
Consumer (Frontend): In /frontend/tests/contract/, write a Pact test for an API interaction, like fetching favorite pairs. This test will run against a mock server and generate a pact.json file.
Provider (Backend): In /backend/tests/contract/, write a Pact verification test. This test will start a real instance of your FastAPI app, replay the requests from the pact.json file against it, and assert that the responses match the contract. Integrate this into your CI/CD pipeline.