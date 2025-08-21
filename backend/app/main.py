# backend/app/main.py

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
# ... (other imports)
from app.services.market_data import market_data_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On App Startup
    print("Application starting up...")
    await init_db()
    
    # Start the background task to listen for market data
    market_data_manager.start()
    
    yield
    
    # On App Shutdown
    print("Application shutting down...")
    await market_data_manager.stop()

app = FastAPI(lifespan=lifespan)

# ... (rest of your main.py)