#!/usr/bin/env python3
"""
Migration script to add unit_size column to trading_plans table.
"""
import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

from app.core.config import settings
import asyncpg

async def add_unit_size_column():
    """Add unit_size column to trading_plans table."""
    
    # Extract connection details from DATABASE_URL
    db_url = settings.DATABASE_URL
    # Remove the 'postgresql+asyncpg://' prefix for asyncpg
    if db_url.startswith('postgresql+asyncpg://'):
        db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    print(f"Connecting to database...")
    
    try:
        conn = await asyncpg.connect(db_url)
        
        # Check if column already exists
        check_query = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'trading_plans' AND column_name = 'unit_size';
        """
        
        result = await conn.fetch(check_query)
        
        if result:
            print("Column 'unit_size' already exists in trading_plans table")
        else:
            # Add the column
            alter_query = """
            ALTER TABLE trading_plans 
            ADD COLUMN unit_size NUMERIC(20, 8) DEFAULT 1.0 NOT NULL;
            """
            
            await conn.execute(alter_query)
            print("Successfully added 'unit_size' column to trading_plans table")
            
        await conn.close()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(add_unit_size_column())
