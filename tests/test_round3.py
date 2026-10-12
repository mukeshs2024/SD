"""
Automated Test Suite for Round 3: High-Level System Design (HLD).
Tests database persistence, idempotency, atomicity, caching, events, and fraud checks.
"""

import pytest
import time
from app import app
from database import init_db, SessionLocal
from models import Wallet, Transaction, User, Payment
from services import cache_service, event_broker, fraud_service, notification_service


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db(seed_sample_data=True)
    session = SessionLocal()
    # Clean transactions and payments to ensure isolated test runs
    session.query(Transaction).delete()
    session.query(Payment).delete()
    w101 = session.query(Wallet).filter_by(wallet_id="W101").first()
    w102 = session.query(Wallet).filter_by(wallet_id="W102").first()
    if w101:
        w101.balance = 10000.0
    if w102:
        w102.balance = 5000.0
    session.commit()
    session.close()
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestRound3SystemDesign:

    def test_01_idempotency_prevents_duplicate_transfers(self, client):
        """Test Idempotency mechanism prevents duplicate execution with 409 Conflict."""
        import uuid
        idemp_key = f"IDEMP-TEST-KEY-{uuid.uuid4().hex[:8]}"
        payload = {
            "fromWalletId": "W101",
            "toWalletId": "W102",
            "amount": 1000.0,
            "idempotencyKey": idemp_key
        }

        # First request succeeds with 201 Created
        res1 = client.post("/api/transfers", json=payload)
        assert res1.status_code == 201
        txn_id = res1.get_json()["transactionId"]

        # Duplicate replay with same idempotency key fails with 409 Conflict
        res2 = client.post("/api/transfers", json=payload)
        assert res2.status_code == 409
        data2 = res2.get_json()
        assert data2["code"] == "DUPLICATE_REQUEST"
        assert data2["existingTransaction"]["transactionId"] == txn_id

        # Verify balance only debited once (10000 - 1000 = 9000)
        bal_res = client.get("/api/wallets/W101/balance")
        assert bal_res.get_json()["balance"] == 9000.0

    def test_02_database_persistence_and_relationship(self, client):
        """Test relational database integrity across Users, Wallets, and Transactions."""
        session = SessionLocal()
        try:
            user = session.query(User).filter_by(user_id="U101").first()
            assert user is not None
            assert len(user.wallets) >= 1
            wallet = user.wallets[0]
            assert wallet.wallet_id == "W101"
            assert wallet.currency == "INR"
        finally:
            session.close()

    def test_03_cache_aside_and_invalidation(self, client):
        """Test Cache-Aside pattern: population on read, invalidation on transfer."""
        wallet_id = "W101"

        # 1. Warm cache via balance read
        res1 = client.get(f"/api/wallets/{wallet_id}/balance")
        assert res1.status_code == 200

        # Verify cached
        cached = cache_service.get_wallet_balance(wallet_id)
        assert cached is not None

        # 2. Transfer funds - should invalidate cache
        client.post("/api/transfers", json={"fromWalletId": "W101", "toWalletId": "W102", "amount": 500})

        # Cache entry should have been invalidated
        assert cache_service.get_wallet_balance(wallet_id) is None

        # 3. Next read re-populates cache with updated balance
        res2 = client.get(f"/api/wallets/{wallet_id}/balance")
        assert res2.status_code == 200
        assert res2.get_json()["balance"] == 9500.0
        assert cache_service.get_wallet_balance(wallet_id) == 9500.0

    def test_04_fraud_detection_single_transfer_limit(self, client):
        """Test Fraud Detection rejects transfers exceeding maximum single limit (₹100,000)."""
        payload = {
            "fromWalletId": "W101",
            "toWalletId": "W102",
            "amount": 250000.0  # Exceeds 100,000 cap
        }
        res = client.post("/api/transfers", json=payload)
        assert res.status_code == 400
        data = res.get_json()
        assert data["code"] == "FRAUD_CHECK_FAILED"
        assert "exceeds limit" in data["error"].lower()

    def test_05_asynchronous_event_and_notification_dispatch(self, client):
        """Test that transfer triggers decoupled asynchronous event and notification dispatch."""
        initial_notifs_count = len(notification_service.sent_notifications)

        res = client.post("/api/transfers", json={"fromWalletId": "W101", "toWalletId": "W102", "amount": 750})
        assert res.status_code == 201

        # Give async thread a brief moment to process
        time.sleep(0.1)

        assert len(notification_service.sent_notifications) > initial_notifs_count
        latest_notif = notification_service.sent_notifications[-1]
        assert latest_notif["type"] == "TRANSFER_NOTIFICATION"
        assert "W101" in latest_notif["message"]
        assert "750" in latest_notif["message"]

    def test_06_atomic_rollback_guarantee(self, client):
        """Verify ACID Atomicity: transfer failure leaves balances unchanged."""
        session = SessionLocal()
        w1_before = session.query(Wallet).filter_by(wallet_id="W101").first().balance
        w2_before = session.query(Wallet).filter_by(wallet_id="W102").first().balance
        session.close()

        # Trigger failed transfer (insufficient balance, within fraud limit of 100,000)
        res = client.post("/api/transfers", json={"fromWalletId": "W101", "toWalletId": "W102", "amount": 80000.0})
        assert res.status_code == 422

        session = SessionLocal()
        w1_after = session.query(Wallet).filter_by(wallet_id="W101").first().balance
        w2_after = session.query(Wallet).filter_by(wallet_id="W102").first().balance
        session.close()

        assert w1_before == w1_after
        assert w2_before == w2_after

    def test_07_system_health_diagnostics(self, client):
        """Test /api/system/health diagnostic monitoring endpoint."""
        res = client.get("/api/system/health")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert "cache" in data
        assert "messageBroker" in data
