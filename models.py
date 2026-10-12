"""
Database models for Digital Wallet & Payment Platform.
Supports PostgreSQL and SQLite via SQLAlchemy.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "userId": self.user_id,
            "name": self.name,
            "email": self.email,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Wallet(Base):
    __tablename__ = "wallets"

    wallet_id = Column(String(50), primary_key=True)
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False, index=True)
    balance = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="INR")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("balance >= 0", name="check_positive_balance"),
    )

    user = relationship("User", back_populates="wallets")

    def to_dict(self):
        return {
            "walletId": self.wallet_id,
            "userId": self.user_id,
            "balance": round(float(self.balance), 2),
            "currency": self.currency,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String(64), primary_key=True)
    sender_wallet_id = Column(String(50), nullable=True, index=True)
    receiver_wallet_id = Column(String(50), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    type = Column(String(30), nullable=False)  # 'TRANSFER', 'ADD_MONEY'
    status = Column(String(30), nullable=False, default="SUCCESS")  # 'SUCCESS', 'FAILED', 'FLAGGED'
    idempotency_key = Column(String(128), nullable=True, index=True)
    description = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="check_positive_amount"),
        Index("idx_tx_wallets", "sender_wallet_id", "receiver_wallet_id"),
    )

    def to_dict(self):
        return {
            "transactionId": self.transaction_id,
            "senderWalletId": self.sender_wallet_id,
            "receiverWalletId": self.receiver_wallet_id,
            "amount": round(float(self.amount), 2),
            "type": self.type,
            "status": self.status,
            "description": self.description,
            "idempotencyKey": self.idempotency_key,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(String(64), primary_key=True)
    wallet_id = Column(String(50), ForeignKey("wallets.wallet_id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50), nullable=False, default="UPI")  # 'UPI', 'NETBANKING', 'CARD'
    status = Column(String(30), nullable=False, default="SUCCESS")
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("amount > 0", name="check_payment_positive_amount"),
    )

    def to_dict(self):
        return {
            "paymentId": self.payment_id,
            "walletId": self.wallet_id,
            "amount": round(float(self.amount), 2),
            "paymentMethod": self.payment_method,
            "status": self.status,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
