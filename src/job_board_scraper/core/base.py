"""SQLAlchemy declarative base.

This module exists to break the circular import between database.py and models.
All SQLAlchemy models should inherit from `Base` defined here.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    pass
