from sqlalchemy import Column, Integer, String, DateTime, DECIMAL, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.session import Base


class TradeHistory(Base):
    """
    SQLAlchemy ORM model for tracking all trades/orders.
    Records every order placed by the trading system.
    """
    __tablename__ = "trade_history"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Link to trading plan
    trading_plan_id = Column(Integer, ForeignKey("trading_plans.id"), nullable=True, index=True)
    
    # Order details
    symbol = Column(String(20), nullable=False, index=True)
    order_id = Column(String(100), nullable=True, index=True)  # Exchange order ID
    order_type = Column(String(10), nullable=False)  # market, limit
    side = Column(String(10), nullable=False)  # buy, sell
    amount = Column(DECIMAL(precision=20, scale=8), nullable=False)
    price = Column(DECIMAL(precision=20, scale=8), nullable=True)
    average_price = Column(DECIMAL(precision=20, scale=8), nullable=True)
    cost = Column(DECIMAL(precision=20, scale=8), nullable=True)
    
    # Status and flags
    success = Column(Boolean, nullable=False, default=False)
    reduce_only = Column(Boolean, nullable=False, default=False)
    error_message = Column(String(500), nullable=True)
    
    # Trading context
    current_unit = Column(Integer, nullable=True)
    current_phase = Column(String(20), nullable=True)
    units_from_peak = Column(Integer, nullable=True)
    units_from_valley = Column(Integer, nullable=True)
    
    # Raw exchange response
    exchange_response = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<TradeHistory(id={self.id}, symbol='{self.symbol}', side='{self.side}', amount={self.amount}, success={self.success})>"