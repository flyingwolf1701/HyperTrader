"""SQLAlchemy ORM model for trading plans."""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from app.db.session import Base

class Plan(Base):
    """Trading plan configuration."""
    
    __tablename__ = "plans"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, nullable=False)
    allocation_percent = Column(Float, nullable=False)
    leverage = Column(Integer, default=1)
    fibonacci_levels = Column(JSON, default=[0.23, 0.38, 0.50, 0.618])
    stop_loss_percent = Column(Float, default=2.0)
    max_positions = Column(Integer, default=3)
    auto_execute = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    # System state
    entry_price = Column(Float, nullable=True)
    current_unit = Column(Integer, default=0)
    peak_unit = Column(Integer, nullable=True)
    valley_unit = Column(Integer, nullable=True)
    
    # Allocations
    long_invested = Column(Float, default=0.0)
    long_cash = Column(Float, default=0.0)
    hedge_long = Column(Float, default=0.0)
    hedge_short = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
