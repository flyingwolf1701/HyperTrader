# backend/app/schemas/favorite.py

from sqlalchemy import Column, Integer, String
from .plan import Base # Import Base from another schema file

class UserFavorite(Base):
    """
    SQLAlchemy ORM model for user's favorite trading pairs.
    """
    __tablename__ = "user_favorites"

    id = Column(Integer, primary_key=True, index=True)
    # In the future, this could be a foreign key to a users table
    user_id = Column(String, index=True, default="default_user")
    symbol = Column(String, index=True, nullable=False)