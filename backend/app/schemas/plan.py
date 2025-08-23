from sqlalchemy import Column, Integer, String, DateTime, Text, DECIMAL
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from datetime import datetime

from app.db.session import Base


class TradingPlan(Base):
    """
    SQLAlchemy ORM model for trading plans.
    Stores the SystemState object as JSONB for flexible schema.
    """
    __tablename__ = "trading_plans"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Basic identifying information
    symbol = Column(String(20), nullable=False, index=True)
    
    # Store the entire SystemState as JSONB for flexibility
    # This allows us to store the complex state object without defining every field
    system_state = Column(JSONB, nullable=False)
    
    # Additional metadata for querying and management
    initial_margin = Column(DECIMAL(precision=20, scale=8), nullable=False)
    leverage = Column(Integer, nullable=False, default=1)
    unit_size = Column(DECIMAL(precision=20, scale=8), nullable=False)  # User-defined price movement per unit
    current_phase = Column(String(20), nullable=False, default="advance", index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Status tracking
    is_active = Column(String(10), nullable=False, default="active")  # active, paused, completed
    
    # Optional notes
    notes = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<TradingPlan(id={self.id}, symbol='{self.symbol}', phase='{self.current_phase}')>"