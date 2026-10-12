"""
Modular logical services for Digital Wallet & Payment Platform.
Implements:
1. CacheService (Redis with in-memory fallback)
2. EventBrokerService (Decoupled messaging bus for events)
3. FraudDetectionService (Transaction risk scoring & limits)
4. NotificationService (Asynchronous recipient notification)
5. PaymentService (Payment gateway simulation)
6. WalletService & TransactionService
"""

import os
import json
import uuid
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from models import User, Wallet, Transaction, Payment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WalletServices")


# ==========================================
# 1. CACHE SERVICE (Redis + Fallback)
# ==========================================
class CacheService:
    """
    Manages caching for wallet balances and summaries.
    Uses Redis if available; gracefully falls back to local memory cache.
    Crucial Rule: Cache is never the authoritative financial source.
    """
    def __init__(self):
        self.redis_client = None
        self._local_cache: Dict[str, Any] = {}
        self.is_redis_active = False

        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))

        try:
            import redis
            client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                socket_timeout=0.5,
                socket_connect_timeout=0.5,
                decode_responses=True
            )
            # Ping test
            client.ping()
            self.redis_client = client
            self.is_redis_active = True
            logger.info("CacheService: Connected successfully to Redis.")
        except Exception as e:
            logger.info(f"CacheService: Redis not available ({e}). Falling back to local in-memory cache.")
            self.is_redis_active = False

    def get_wallet_balance(self, wallet_id: str) -> Optional[float]:
        key = f"wallet:balance:{wallet_id}"
        if self.is_redis_active and self.redis_client:
            try:
                val = self.redis_client.get(key)
                if val is not None:
                    return float(val)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        # Fallback
        if key in self._local_cache:
            return float(self._local_cache[key])
        return None

    def set_wallet_balance(self, wallet_id: str, balance: float, ttl_seconds: int = 60):
        key = f"wallet:balance:{wallet_id}"
        if self.is_redis_active and self.redis_client:
            try:
                self.redis_client.setex(key, ttl_seconds, str(balance))
                return
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        self._local_cache[key] = float(balance)

    def invalidate_wallet(self, wallet_id: str):
        key = f"wallet:balance:{wallet_id}"
        if self.is_redis_active and self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")
        self._local_cache.pop(key, None)


# ==========================================
# 2. EVENT BROKER & MESSAGING SERVICE
# ==========================================
class EventBrokerService:
    """
    Asynchronous event bus simulating Kafka / RabbitMQ.
    Guarantees that downstream operations like SMS/Push notifications
    or fraud auditing never cause atomic financial transactions to fail.
    """
    def __init__(self):
        self._subscribers = {}
        self.published_events = []
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler):
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

    def publish(self, event_type: str, payload: dict):
        event_record = {
            "eventId": f"EVT-{uuid.uuid4().hex[:12].upper()}",
            "eventType": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        }
        with self._lock:
            self.published_events.append(event_record)

        logger.info(f"[EVENT PUBLISHED] {event_type} -> ID: {event_record['eventId']}")

        # Asynchronously dispatch to subscribers to prevent blocking caller
        handlers = self._subscribers.get(event_type, [])
        for handler in handlers:
            threading.Thread(target=self._safe_execute, args=(handler, event_record), daemon=True).start()

    def _safe_execute(self, handler, event_record):
        try:
            handler(event_record)
        except Exception as e:
            logger.error(f"Error handling event {event_record['eventType']}: {e}")


# ==========================================
# 3. FRAUD DETECTION SERVICE
# ==========================================
class FraudDetectionService:
    """
    Logical Fraud Detection Service.
    Evaluates velocity, single transaction amount caps, and anomalous patterns.
    """
    def __init__(self):
        self.max_single_transfer = float(os.getenv("MAX_SINGLE_TRANSFER_LIMIT", "100000.0"))
        self.high_value_alert_threshold = float(os.getenv("HIGH_VALUE_ALERT_THRESHOLD", "25000.0"))
        self.flagged_records = []

    def evaluate_transfer(self, sender_wallet_id: str, receiver_wallet_id: str, amount: float) -> Tuple[bool, str]:
        """
        Returns (is_allowed: bool, reason: str)
        """
        if amount <= 0:
            return False, "Transfer amount must be strictly greater than zero."

        if amount > self.max_single_transfer:
            record = {
                "senderWalletId": sender_wallet_id,
                "receiverWalletId": receiver_wallet_id,
                "amount": amount,
                "reason": "Exceeded maximum single transfer limit of ₹100,000",
                "timestamp": datetime.utcnow().isoformat(),
            }
            self.flagged_records.append(record)
            return False, f"Transfer rejected: Amount exceeds limit of ₹{self.max_single_transfer:,.2f}"

        if amount >= self.high_value_alert_threshold:
            logger.warning(f"FRAUD ALERT: High value transfer of ₹{amount:,.2f} detected from {sender_wallet_id}")
            self.flagged_records.append({
                "senderWalletId": sender_wallet_id,
                "receiverWalletId": receiver_wallet_id,
                "amount": amount,
                "reason": "High-value transfer alert triggered",
                "timestamp": datetime.utcnow().isoformat(),
            })

        return True, "Passed fraud check"


# ==========================================
# 4. NOTIFICATION SERVICE
# ==========================================
class NotificationService:
    """
    Logical Notification Service.
    Listens to broker events and simulates sending SMS / Email / Push notifications.
    """
    def __init__(self):
        self.sent_notifications = []
        self._lock = threading.Lock()

    def handle_transfer_event(self, event_record: dict):
        payload = event_record["payload"]
        msg = (
            f"[NOTIFICATION] Transfer of INR {payload.get('amount')} "
            f"from {payload.get('senderWalletId')} to {payload.get('receiverWalletId')} "
            f"completed successfully. Ref: {payload.get('transactionId')}"
        )
        with self._lock:
            self.sent_notifications.append({
                "type": "TRANSFER_NOTIFICATION",
                "message": msg,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": payload,
            })
        logger.info(msg)

    def handle_add_money_event(self, event_record: dict):
        payload = event_record["payload"]
        msg = (
            f"[NOTIFICATION] Wallet {payload.get('walletId')} credited with "
            f"INR {payload.get('amount')}. Balance updated."
        )
        with self._lock:
            self.sent_notifications.append({
                "type": "ADD_MONEY_NOTIFICATION",
                "message": msg,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": payload,
            })
        logger.info(msg)


# Singletons for application lifecycle
cache_service = CacheService()
event_broker = EventBrokerService()
fraud_service = FraudDetectionService()
notification_service = NotificationService()

# Register event subscribers
event_broker.subscribe("TRANSFER_COMPLETED", notification_service.handle_transfer_event)
event_broker.subscribe("ADD_MONEY_COMPLETED", notification_service.handle_add_money_event)
