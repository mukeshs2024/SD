"""
Automated Test Suite for Round 2: Low-Level Design (LLD).
Tests all REST endpoints, HTTP status codes, edge cases, validations, and PDF downloads.
"""

import pytest
import json
from app import app
from database import init_db, SessionLocal
from models import Wallet, User, Transaction, Payment


@pytest.fixture(autouse=True)
def setup_test_db():
    """Reset database and re-seed clean test fixtures before each test."""
    init_db(seed_sample_data=True)
    session = SessionLocal()
    session.query(Transaction).delete()
    session.query(Payment).delete()
    # Reset wallet balances to known clean state
    w101 = session.query(Wallet).filter_by(wallet_id="W101").first()
    w102 = session.query(Wallet).filter_by(wallet_id="W102").first()
    w103 = session.query(Wallet).filter_by(wallet_id="W103").first()
    if w101:
        w101.balance = 5000.0
    if w102:
        w102.balance = 2000.0
    if w103:
        w103.balance = 500.0
    session.commit()
    session.close()
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestRound2APIs:

    def test_01_root_endpoint(self, client):
        """Test Root endpoint GET / returns 200 OK and available endpoints list."""
        res = client.get("/")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "online"
        assert "availableEndpoints" in data
        assert "getWalletBalance" in data["availableEndpoints"]

    def test_02_get_wallet_balance_success(self, client):
        """Test GET /api/wallets/<wallet_id>/balance returns 200 OK and correct balance."""
        res = client.get("/api/wallets/W101/balance")
        assert res.status_code == 200
        data = res.get_json()
        assert data["walletId"] == "W101"
        assert data["balance"] == 5000.0
        assert data["currency"] == "INR"

    def test_03_get_wallet_balance_not_found(self, client):
        """Test GET /api/wallets/<wallet_id>/balance returns 404 for non-existent wallet."""
        res = client.get("/api/wallets/W9999/balance")
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_04_add_money_success(self, client):
        """Test POST /api/wallets/<wallet_id>/add-money returns 201 Created and updates balance."""
        res = client.post("/api/wallets/W101/add-money", json={"amount": 1000.0, "paymentMethod": "UPI"})
        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["amountAdded"] == 1000.0
        assert data["newBalance"] == 6000.0
        assert data["transactionId"].startswith("TXN-")

    def test_05_add_money_invalid_amount(self, client):
        """Test POST /api/wallets/<wallet_id>/add-money returns 400 for negative or zero amounts."""
        # Zero amount
        res1 = client.post("/api/wallets/W101/add-money", json={"amount": 0})
        assert res1.status_code == 400
        assert "greater than zero" in res1.get_json()["error"]

        # Negative amount
        res2 = client.post("/api/wallets/W101/add-money", json={"amount": -50})
        assert res2.status_code == 400

        # Non-numeric
        res3 = client.post("/api/wallets/W101/add-money", json={"amount": "not-a-number"})
        assert res3.status_code == 400

    def test_06_add_money_missing_wallet(self, client):
        """Test POST /api/wallets/<wallet_id>/add-money returns 404 for invalid wallet."""
        res = client.post("/api/wallets/W_GHOST/add-money", json={"amount": 500})
        assert res.status_code == 404

    def test_07_transfer_money_success(self, client):
        """Test POST /api/transfers successfully transfers funds and returns 201 Created."""
        payload = {
            "fromWalletId": "W101",
            "toWalletId": "W102",
            "amount": 500.0
        }
        res = client.post("/api/transfers", json=payload)
        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["fromWalletId"] == "W101"
        assert data["toWalletId"] == "W102"
        assert data["amount"] == 500.0
        assert data["status"] == "SUCCESS"
        assert "transactionId" in data

        # Verify updated balances
        bal1 = client.get("/api/wallets/W101/balance").get_json()["balance"]
        bal2 = client.get("/api/wallets/W102/balance").get_json()["balance"]
        assert bal1 == 4500.0
        assert bal2 == 2500.0

    def test_08_transfer_money_insufficient_balance(self, client):
        """Test POST /api/transfers returns 422 Unprocessable Content when sender lacks funds."""
        payload = {
            "fromWalletId": "W103",  # W103 balance is 500.0
            "toWalletId": "W101",
            "amount": 99999.0
        }
        res = client.post("/api/transfers", json=payload)
        assert res.status_code == 422
        data = res.get_json()
        assert data["success"] is False
        assert "insufficient" in data["error"].lower()

    def test_09_transfer_money_same_wallet(self, client):
        """Test POST /api/transfers returns 400 Bad Request when sender == receiver."""
        payload = {
            "fromWalletId": "W101",
            "toWalletId": "W101",
            "amount": 100.0
        }
        res = client.post("/api/transfers", json=payload)
        assert res.status_code == 400
        data = res.get_json()
        assert "same" in data["error"].lower()

    def test_10_transfer_money_missing_wallet(self, client):
        """Test POST /api/transfers returns 404 Not Found when wallet does not exist."""
        # Non-existent sender
        res1 = client.post("/api/transfers", json={"fromWalletId": "W_UNKNOWN", "toWalletId": "W102", "amount": 100})
        assert res1.status_code == 404

        # Non-existent receiver
        res2 = client.post("/api/transfers", json={"fromWalletId": "W101", "toWalletId": "W_UNKNOWN", "amount": 100})
        assert res2.status_code == 404

    def test_11_transfer_money_negative_amount(self, client):
        """Test POST /api/transfers returns 400 Bad Request for negative amount."""
        res = client.post("/api/transfers", json={"fromWalletId": "W101", "toWalletId": "W102", "amount": -100})
        assert res.status_code == 400

    def test_12_transaction_history(self, client):
        """Test GET /api/wallets/<wallet_id>/transactions returns 200 OK and list of records."""
        # Perform a transfer first
        client.post("/api/transfers", json={"fromWalletId": "W101", "toWalletId": "W102", "amount": 300})

        res = client.get("/api/wallets/W101/transactions")
        assert res.status_code == 200
        data = res.get_json()
        assert data["walletId"] == "W101"
        assert data["count"] >= 1
        assert len(data["transactions"]) >= 1
        assert data["transactions"][0]["amount"] == 300.0

    def test_13_download_receipt_pdf(self, client):
        """Test GET /api/transactions/<txn_id>/download returns valid PDF document."""
        # Create transfer to get transaction ID
        transfer_res = client.post("/api/transfers", json={"fromWalletId": "W101", "toWalletId": "W102", "amount": 250})
        txn_id = transfer_res.get_json()["transactionId"]

        # Download receipt
        res = client.get(f"/api/transactions/{txn_id}/download")
        assert res.status_code == 200
        assert res.headers["Content-Type"] == "application/pdf"
        assert res.data.startswith(b"%PDF-")
        assert len(res.data) > 1000

    def test_14_download_receipt_invalid_id(self, client):
        """Test GET /api/transactions/<invalid_id>/download returns 404 Not Found."""
        res = client.get("/api/transactions/TXN-NONEXISTENT/download")
        assert res.status_code == 404
        assert res.get_json()["success"] is False

    def test_15_method_not_allowed_handling(self, client):
        """Test opening POST endpoint with GET returns 405 Method Not Allowed with explanation."""
        res = client.get("/api/transfers")
        assert res.status_code == 405
        data = res.get_json()
        assert data["code"] == "METHOD_NOT_ALLOWED"
        assert "browser" in data["error"].lower()
