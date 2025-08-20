from sqlalchemy import Column, Integer, String, DateTime, Boolean, UniqueConstraint
from sqlalchemy.sql import func
from datetime import datetime

from app.db.session import Base


class UserFavorite(Base):
    """
    SQLAlchemy ORM model for user favorite trading pairs.
    Supports multi-user functionality with user_id field for future expansion.
    """
    __tablename__ = "user_favorites"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # User identification (for future multi-user support)
    user_id = Column(String(50), nullable=False, default="default_user", index=True)
    
    # Trading pair symbol
    symbol = Column(String(20), nullable=False, index=True)
    
    # Market information
    base_asset = Column(String(10), nullable=False)   # e.g., "BTC"
    quote_asset = Column(String(10), nullable=False)  # e.g., "USDT"
    
    # Exchange information
    exchange = Column(String(20), nullable=False, default="hyperliquid")
    
    # Favorite metadata
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=True)  # For custom ordering
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Notes or tags
    notes = Column(String(255), nullable=True)
    tags = Column(String(255), nullable=True)  # Comma-separated tags like "high-vol,trending"
    
    # Ensure unique combination of user_id and symbol
    __table_args__ = (
        UniqueConstraint('user_id', 'symbol', name='uq_user_symbol'),
    )
    
    def __repr__(self):
        return f"<UserFavorite(id={self.id}, user_id='{self.user_id}', symbol='{self.symbol}')>"