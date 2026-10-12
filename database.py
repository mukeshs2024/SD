"""
Database connection, session management, and seed data initialization.
Supports PostgreSQL (production) with automatic fallback to SQLite (local development).
"""

import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base, User, Wallet, Transaction, Payment

logger = logging.getLogger("Database")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///digital_wallet.db")

# SQLite connection args for multi-threading support
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def init_db(seed_sample_data: bool = True):
    """Create tables and seed sample wallets if database is empty."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    try:
        # Check if users already exist
        if seed_sample_data and session.query(User).count() == 0:
            logger.info("Seeding initial users and wallets...")
            users = [
                User(user_id="U101", name="Alice Sharma", email="alice.sharma@example.com"),
                User(user_id="U102", name="Bob Verma", email="bob.verma@example.com"),
                User(user_id="U103", name="Charlie Patel", email="charlie.patel@example.com"),
            ]
            session.add_all(users)
            session.flush()

            wallets = [
                Wallet(wallet_id="W101", user_id="U101", balance=5000.0, currency="INR"),
                Wallet(wallet_id="W102", user_id="U102", balance=2000.0, currency="INR"),
                Wallet(wallet_id="W103", user_id="U103", balance=500.0, currency="INR"),
            ]
            session.add_all(wallets)
            session.commit()
            logger.info("Database initialized and sample data seeded successfully.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error seeding database: {e}")
    finally:
        session.close()


def get_db():
    """Generator for database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
