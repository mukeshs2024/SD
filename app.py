"""
Complete Digital Wallet & Payment Platform — Flask Application.
Combines Round 2 (Low-Level Design) & Round 3 (High-Level System Design).
"""

import os
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response, make_response
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from database import init_db, SessionLocal
from models import User, Wallet, Transaction, Payment
from services import cache_service, event_broker, fraud_service, notification_service
from receipt_generator import generate_receipt_pdf_bytes

app = Flask(__name__)

# Initialize database schema and initial seed data
init_db(seed_sample_data=True)


# ============================================================================
# TASK 2: ROOT ENDPOINT & WEB UI (PART C)
# ============================================================================
@app.route("/", methods=["GET"])
def root_endpoint():
    """
    Root endpoint returning system metadata and available API endpoints.
    Ensures root endpoint does not return 404.
    """
    return jsonify({
        "status": "online",
        "service": "Digital Wallet & Payment Platform API",
        "version": "2.0.0",
        "architecture": "Modular Microservices (LLD & HLD Practical Demonstration)",
        "webInterface": "/ui",
        "availableEndpoints": {
            "root": {
                "method": "GET",
                "uri": "/",
                "description": "System status and endpoint catalog"
            },
            "webUI": {
                "method": "GET",
                "uri": "/ui",
                "description": "Interactive web dashboard for testing wallet operations"
            },
            "getWalletBalance": {
                "method": "GET",
                "uri": "/api/wallets/<wallet_id>/balance",
                "description": "Retrieve wallet balance with Redis cache-aside"
            },
            "addMoney": {
                "method": "POST",
                "uri": "/api/wallets/<wallet_id>/add-money",
                "description": "Add funds to wallet via payment gateway simulation"
            },
            "transferMoney": {
                "method": "POST",
                "uri": "/api/transfers",
                "description": "ACID atomic P2P money transfer between wallets"
            },
            "getTransactionHistory": {
                "method": "GET",
                "uri": "/api/wallets/<wallet_id>/transactions",
                "description": "Retrieve full transaction history for a wallet"
            },
            "downloadTransactionReceipt": {
                "method": "GET",
                "uri": "/api/transactions/<transaction_id>/download",
                "description": "Download an official PDF transaction receipt"
            },
            "listWallets": {
                "method": "GET",
                "uri": "/api/wallets",
                "description": "List all active wallets in the system"
            },
            "systemHealth": {
                "method": "GET",
                "uri": "/api/system/health",
                "description": "Database, cache, and messaging bus diagnostic metrics"
            }
        }
    }), 200


@app.route("/ui", methods=["GET"])
def ui_dashboard():
    """Serves the interactive web interface."""
    return render_template("index.html")


@app.route("/api/wallets", methods=["GET"])
def list_wallets():
    """Helper endpoint to list all wallets."""
    session = SessionLocal()
    try:
        wallets = session.query(Wallet).all()
        return jsonify({
            "count": len(wallets),
            "wallets": [w.to_dict() for w in wallets]
        }), 200
    finally:
        session.close()


# ============================================================================
# TASK 1 & TASK 4: WALLET BALANCE (CACHE-ASIDE PATTERN)
# ============================================================================
@app.route("/api/wallets/<wallet_id>/balance", methods=["GET"])
def get_wallet_balance(wallet_id: str):
    """
    Get wallet balance.
    Checks Redis cache first. On miss, queries DB and populates cache.
    Status codes: 200 OK, 404 Not Found.
    """
    # 1. Check Cache Layer
    cached_bal = cache_service.get_wallet_balance(wallet_id)
    if cached_bal is not None:
        # Retrieve wallet metadata
        session = SessionLocal()
        try:
            wallet = session.query(Wallet).filter_by(wallet_id=wallet_id).first()
            user_id = wallet.user_id if wallet else "Unknown"
            currency = wallet.currency if wallet else "INR"
        finally:
            session.close()

        return jsonify({
            "walletId": wallet_id,
            "userId": user_id,
            "balance": round(cached_bal, 2),
            "currency": currency,
            "source": "cache"
        }), 200

    # 2. Cache Miss: Authoritative Database Read
    session = SessionLocal()
    try:
        wallet = session.query(Wallet).filter_by(wallet_id=wallet_id).first()
        if not wallet:
            return jsonify({
                "success": False,
                "error": f"Wallet '{wallet_id}' not found.",
                "code": "WALLET_NOT_FOUND"
            }), 404

        balance = round(float(wallet.balance), 2)
        # Populate cache
        cache_service.set_wallet_balance(wallet_id, balance)

        return jsonify({
            "walletId": wallet.wallet_id,
            "userId": wallet.user_id,
            "balance": balance,
            "currency": wallet.currency,
            "source": "database"
        }), 200
    finally:
        session.close()


# ============================================================================
# TASK 1 & TASK 4: ADD MONEY
# ============================================================================
@app.route("/api/wallets/<wallet_id>/add-money", methods=["POST"])
def add_money(wallet_id: str):
    """
    Add money to a wallet.
    Validates input, records payment, updates balance atomically, invalidates cache,
    and publishes an asynchronous notification event.
    Status codes: 201 Created, 400 Bad Request, 404 Not Found.
    """
    payload = request.get_json(silent=True) or {}
    raw_amount = payload.get("amount")
    payment_method = payload.get("paymentMethod", "UPI")

    if raw_amount is None:
        return jsonify({
            "success": False,
            "error": "Field 'amount' is required.",
            "code": "MISSING_AMOUNT"
        }), 400

    try:
        amount = float(raw_amount)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Amount must be a valid numeric value.",
            "code": "INVALID_AMOUNT_TYPE"
        }), 400

    if amount <= 0:
        return jsonify({
            "success": False,
            "error": "Amount to add must be strictly greater than zero.",
            "code": "INVALID_AMOUNT"
        }), 400

    session = SessionLocal()
    try:
        wallet = session.query(Wallet).filter_by(wallet_id=wallet_id).first()
        if not wallet:
            return jsonify({
                "success": False,
                "error": f"Wallet '{wallet_id}' not found.",
                "code": "WALLET_NOT_FOUND"
            }), 404

        # Atomic Balance Update
        wallet.balance = round(float(wallet.balance) + amount, 2)
        wallet.updated_at = datetime.utcnow()

        # Create Payment Record
        payment_id = f"PAY-{uuid.uuid4().hex[:10].upper()}"
        payment = Payment(
            payment_id=payment_id,
            wallet_id=wallet_id,
            amount=amount,
            payment_method=payment_method,
            status="SUCCESS",
            timestamp=datetime.utcnow()
        )
        session.add(payment)

        # Create Transaction Record
        txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        txn = Transaction(
            transaction_id=txn_id,
            sender_wallet_id=None,
            receiver_wallet_id=wallet_id,
            amount=amount,
            type="ADD_MONEY",
            status="SUCCESS",
            description=f"Loaded funds via {payment_method}",
            timestamp=datetime.utcnow()
        )
        session.add(txn)

        session.commit()

        # Cache Invalidation
        cache_service.invalidate_wallet(wallet_id)

        # Asynchronous Event Notification
        event_broker.publish("ADD_MONEY_COMPLETED", {
            "transactionId": txn_id,
            "walletId": wallet_id,
            "amount": amount,
            "newBalance": wallet.balance,
            "paymentMethod": payment_method
        })

        return jsonify({
            "success": True,
            "message": f"Successfully added INR {amount:,.2f} to wallet {wallet_id}.",
            "transactionId": txn_id,
            "paymentId": payment_id,
            "walletId": wallet_id,
            "amountAdded": amount,
            "newBalance": wallet.balance,
            "currency": wallet.currency,
            "status": "SUCCESS"
        }), 201

    except Exception as e:
        session.rollback()
        return jsonify({
            "success": False,
            "error": f"Transaction failed due to internal error: {str(e)}",
            "code": "INTERNAL_SERVER_ERROR"
        }), 500
    finally:
        session.close()


# ============================================================================
# TASK 1, 3, 4, 5: TRANSFER MONEY (P2P ATOMIC TRANSACTION WITH IDEMPOTENCY)
# ============================================================================
@app.route("/api/transfers", methods=["POST"])
def transfer_money():
    """
    Transfer money between two wallets.
    Sequence:
      1. Validate request payload & headers
      2. Check idempotency mechanism to prevent duplicate processing
      3. Validate sender != receiver
      4. Validate positive amount
      5. Fraud detection policy check
      6. Query & validate existence of sender and receiver wallets
      7. Validate sufficient sender balance (422 Unprocessable Content)
      8. Atomic DB Transaction: Debit sender, credit receiver, record transaction
      9. Invalidate caches for both wallets
      10. Publish event to message bus (decoupled notifications)
      11. Return response (201 Created)
    """
    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "error": "Request body must be a valid JSON object.",
            "code": "INVALID_JSON"
        }), 400

    from_wallet_id = payload.get("fromWalletId")
    to_wallet_id = payload.get("toWalletId")
    raw_amount = payload.get("amount")
    idempotency_key = request.headers.get("Idempotency-Key") or payload.get("idempotencyKey")

    # Step 1: Input presence validation
    if not from_wallet_id or not to_wallet_id:
        return jsonify({
            "success": False,
            "error": "Both 'fromWalletId' and 'toWalletId' are required.",
            "code": "MISSING_WALLET_IDS"
        }), 400

    if raw_amount is None:
        return jsonify({
            "success": False,
            "error": "Field 'amount' is required.",
            "code": "MISSING_AMOUNT"
        }), 400

    # Step 2: Positive amount validation
    try:
        amount = float(raw_amount)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Transfer amount must be a numeric value.",
            "code": "INVALID_AMOUNT_TYPE"
        }), 400

    if amount <= 0:
        return jsonify({
            "success": False,
            "error": "Transfer amount must be strictly greater than zero.",
            "code": "INVALID_AMOUNT"
        }), 400

    # Step 3: Sender != Receiver validation
    if from_wallet_id.strip() == to_wallet_id.strip():
        return jsonify({
            "success": False,
            "error": "Sender and receiver wallet cannot be the same.",
            "code": "SAME_WALLET_TRANSFER"
        }), 400

    # Step 4: Fraud Detection Evaluation
    is_safe, fraud_reason = fraud_service.evaluate_transfer(from_wallet_id, to_wallet_id, amount)
    if not is_safe:
        return jsonify({
            "success": False,
            "error": fraud_reason,
            "code": "FRAUD_CHECK_FAILED"
        }), 400

    session = SessionLocal()
    try:
        # Step 5: Idempotency Verification
        if idempotency_key:
            existing_txn = session.query(Transaction).filter_by(idempotency_key=idempotency_key).first()
            if existing_txn:
                return jsonify({
                    "success": False,
                    "error": "Duplicate transfer request detected with identical idempotency key.",
                    "code": "DUPLICATE_REQUEST",
                    "existingTransaction": existing_txn.to_dict()
                }), 409

        # Step 6: Validate Wallet Existence
        sender_wallet = session.query(Wallet).filter_by(wallet_id=from_wallet_id).first()
        if not sender_wallet:
            return jsonify({
                "success": False,
                "error": f"Sender wallet '{from_wallet_id}' not found.",
                "code": "SENDER_WALLET_NOT_FOUND"
            }), 404

        receiver_wallet = session.query(Wallet).filter_by(wallet_id=to_wallet_id).first()
        if not receiver_wallet:
            return jsonify({
                "success": False,
                "error": f"Receiver wallet '{to_wallet_id}' not found.",
                "code": "RECEIVER_WALLET_NOT_FOUND"
            }), 404

        # Step 7: Validate Sufficient Sender Balance
        if float(sender_wallet.balance) < amount:
            return jsonify({
                "success": False,
                "error": "Insufficient balance to complete transfer.",
                "code": "INSUFFICIENT_FUNDS",
                "availableBalance": round(float(sender_wallet.balance), 2),
                "requestedAmount": amount
            }), 422

        # Step 8: Atomic Transaction Execution (Debit Sender, Credit Receiver)
        sender_wallet.balance = round(float(sender_wallet.balance) - amount, 2)
        sender_wallet.updated_at = datetime.utcnow()

        receiver_wallet.balance = round(float(receiver_wallet.balance) + amount, 2)
        receiver_wallet.updated_at = datetime.utcnow()

        txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.utcnow()

        txn_record = Transaction(
            transaction_id=txn_id,
            sender_wallet_id=from_wallet_id,
            receiver_wallet_id=to_wallet_id,
            amount=amount,
            type="TRANSFER",
            status="SUCCESS",
            idempotency_key=idempotency_key,
            description="P2P Instant Transfer",
            timestamp=now
        )
        session.add(txn_record)

        # Atomic commit
        session.commit()

        # Step 9: Invalidate affected caches
        cache_service.invalidate_wallet(from_wallet_id)
        cache_service.invalidate_wallet(to_wallet_id)

        # Step 10: Asynchronous Notification & Event Publishing
        event_broker.publish("TRANSFER_COMPLETED", {
            "transactionId": txn_id,
            "senderWalletId": from_wallet_id,
            "receiverWalletId": to_wallet_id,
            "amount": amount,
            "timestamp": now.isoformat()
        })

        # Step 11: Return Response
        return jsonify({
            "success": True,
            "message": "Transfer completed successfully.",
            "transactionId": txn_id,
            "fromWalletId": from_wallet_id,
            "toWalletId": to_wallet_id,
            "amount": amount,
            "status": "SUCCESS",
            "senderRemainingBalance": sender_wallet.balance,
            "timestamp": now.isoformat()
        }), 201

    except Exception as e:
        session.rollback()
        return jsonify({
            "success": False,
            "error": f"Failed to execute transfer: {str(e)}",
            "code": "INTERNAL_SERVER_ERROR"
        }), 500
    finally:
        session.close()


# ============================================================================
# TASK 1: TRANSACTION HISTORY
# ============================================================================
@app.route("/api/wallets/<wallet_id>/transactions", methods=["GET"])
def get_transaction_history(wallet_id: str):
    """
    Retrieve full transaction history for a specific wallet (sent & received).
    Status codes: 200 OK, 404 Not Found.
    """
    session = SessionLocal()
    try:
        wallet = session.query(Wallet).filter_by(wallet_id=wallet_id).first()
        if not wallet:
            return jsonify({
                "success": False,
                "error": f"Wallet '{wallet_id}' not found.",
                "code": "WALLET_NOT_FOUND"
            }), 404

        txns = session.query(Transaction).filter(
            or_(
                Transaction.sender_wallet_id == wallet_id,
                Transaction.receiver_wallet_id == wallet_id
            )
        ).order_by(desc(Transaction.timestamp)).all()

        return jsonify({
            "walletId": wallet_id,
            "count": len(txns),
            "transactions": [t.to_dict() for t in txns]
        }), 200
    finally:
        session.close()


# ============================================================================
# TASK 1 & TASK 6: DOWNLOAD TRANSACTION RECEIPT (PDF)
# ============================================================================
@app.route("/api/transactions/<transaction_id>/download", methods=["GET"])
def download_transaction_receipt(transaction_id: str):
    """
    Generate and stream an official PDF transaction receipt.
    Status codes: 200 OK (application/pdf), 404 Not Found (JSON).
    """
    session = SessionLocal()
    try:
        txn = session.query(Transaction).filter_by(transaction_id=transaction_id).first()
        if not txn:
            return jsonify({
                "success": False,
                "error": f"Transaction '{transaction_id}' not found.",
                "code": "TRANSACTION_NOT_FOUND"
            }), 404

        pdf_bytes = generate_receipt_pdf_bytes(txn.to_dict())

        response = make_response(pdf_bytes)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="receipt_{transaction_id}.pdf"'
        return response
    finally:
        session.close()


# ============================================================================
# SYSTEM HEALTH & ARCHITECTURE DIAGNOSTICS
# ============================================================================
@app.route("/api/system/health", methods=["GET"])
def system_health():
    """System health check showing DB, Cache, and Message Bus status."""
    return jsonify({
        "status": "healthy",
        "database": {
            "type": "SQLite (Development) / PostgreSQL (Production Compatible)",
            "connected": True
        },
        "cache": {
            "service": "Redis",
            "active": cache_service.is_redis_active,
            "mode": "Redis" if cache_service.is_redis_active else "In-Memory Fallback"
        },
        "messageBroker": {
            "eventsPublishedCount": len(event_broker.published_events),
            "notificationsDispatchedCount": len(notification_service.sent_notifications),
            "mode": "Asynchronous Decoupled Event Bus"
        },
        "fraudDetection": {
            "maxTransferLimit": fraud_service.max_single_transfer,
            "flaggedTransfersCount": len(fraud_service.flagged_records)
        }
    }), 200


# ============================================================================
# TASK 4: STANDARDIZED HTTP ERROR HANDLERS
# ============================================================================
@app.errorhandler(400)
def handle_bad_request(e):
    return jsonify({
        "success": False,
        "error": "Bad Request: The submitted payload was invalid or missing required parameters.",
        "code": "BAD_REQUEST"
    }), 400


@app.errorhandler(404)
def handle_not_found(e):
    return jsonify({
        "success": False,
        "error": "Resource Not Found: The requested URL, wallet, or transaction does not exist.",
        "code": "NOT_FOUND"
    }), 404


@app.errorhandler(405)
def handle_method_not_allowed(e):
    return jsonify({
        "success": False,
        "error": "Method Not Allowed: This endpoint requires a different HTTP method (e.g., POST). "
                 "Opening a POST endpoint directly in a web browser sends a GET request, resulting in this error. "
                 "Please use the Web UI (/ui) or an API tool like curl or Postman with POST.",
        "code": "METHOD_NOT_ALLOWED"
    }), 405


@app.errorhandler(500)
def handle_internal_error(e):
    return jsonify({
        "success": False,
        "error": "Internal Server Error: An unexpected failure occurred on the server.",
        "code": "INTERNAL_SERVER_ERROR"
    }), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() in ("true", "1")
    print(f"Starting Digital Wallet & Payment Platform on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
