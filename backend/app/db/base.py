# backend/app/db/base.py

from sqlalchemy.orm import declarative_base

# Create a Base class for all SQLAlchemy models to inherit from.
# This is kept in its own file to prevent circular import errors.
Base = declarative_base()
