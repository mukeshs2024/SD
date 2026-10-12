# Digital Wallet & Payment Platform — Complete Assignment Solution
## Round 2: Low-Level Design (LLD) & Round 3: High-Level System Design (HLD)

---

### 🌟 Project Summary
This repository contains the complete production-grade implementation of the **Digital Wallet & Payment Platform** developed for the college practical challenge. It demonstrates **ACID atomic peer-to-peer transfers**, **RESTful API engineering**, **idempotency protection**, **cache-aside with Redis**, **event-driven decoupled notifications**, **fraud risk policies**, **PDF receipt streaming**, and **interactive web UI monitoring**.

---

## 📁 Repository File Structure

```text
C:\SD\
├── app.py                     # Main Flask web application & REST API controllers
├── database.py                # Database connection, engine, and seed data initialization
├── models.py                  # SQLAlchemy ORM models (Users, Wallets, Transactions, Payments)
├── services.py                # Logical Microservices (Cache, Event Broker, Fraud, Notification)
├── receipt_generator.py       # FPDF-based official transaction receipt PDF generator
├── test_runner.py             # Master test suite runner executing pytest
├── requirements.txt           # Python dependency specifications
├── .env.example               # Environment configuration template
├── README.md                  # Complete setup, documentation, and execution guide
├── ASSIGNMENT_REPORT.md       # Comprehensive academic practical assignment report
├── ASSIGNMENT_REPORT.pdf      # Final college submission PDF report
├── static/
│   └── architecture_diagram.svg # High-Level Architecture Diagram (vector SVG)
├── templates/
│   └── index.html             # Visual Web UI for interactive wallet operations
└── tests/
    ├── test_round2.py         # Automated test suite for Round 2 LLD (15 tests)
    └── test_round3.py         # Automated test suite for Round 3 HLD (7 tests)
```

---

## 🚀 Quick Start Guide (Windows PowerShell)

### Step 1: Open Windows PowerShell and Navigate to Project
```powershell
cd C:\SD
```

### Step 2: Install Required Dependencies
```powershell
python -m pip install -r requirements.txt
```

### Step 3: Run the Complete Automated Test Suite
To verify that all 22 tests pass across Round 2 and Round 3:
```powershell
python test_runner.py
```
*Expected Result:* `22 passed in ~2.06s (100% SUCCESS)`

### Step 4: Start the Flask Application
```powershell
python app.py
```
*The server will start at `http://127.0.0.1:5000`.*

---

## 🌐 Interactive Web Dashboard (Part C)
Open your web browser and navigate to:
👉 **`http://127.0.0.1:5000/ui`**

Features available in the Web UI:
- **Live Wallet Selector:** Toggle between pre-seeded wallets (`W101`, `W102`, `W103`).
- **Real-Time Balance Check:** Queries cache/database with source indicator.
- **Add Money:** Simulate instant funds loading with payment method selection (UPI, Card, NetBanking).
- **Instant P2P Transfer:** Execute atomic transfers with idempotency key input.
- **Transaction History:** Real-time audit feed of incoming and outgoing transfers.
- **1-Click PDF Receipt Download:** Download official receipts generated directly on the server.

---

## ⚠️ Important Note: Browser GET vs POST (405 Method Not Allowed)
If you enter a POST URL such as `http://127.0.0.1:5000/api/transfers` directly into your browser's address bar, the browser sends an **HTTP GET request**. 
Since `/api/transfers` strictly requires **HTTP POST** with a JSON payload, the server will intentionally return:
```json
{
  "code": "METHOD_NOT_ALLOWED",
  "error": "Method Not Allowed: This endpoint requires a different HTTP method (e.g., POST)...",
  "success": false
}
```
**To test POST endpoints:** Use the provided interactive Web UI (`/ui`), the automated test suite (`python test_runner.py`), or PowerShell `Invoke-RestMethod` commands shown below.

---

## 📡 REST API Specifications & Testing Examples

### 1. Root Status & Endpoint Catalog
- **Method:** `GET`
- **URI:** `http://127.0.0.1:5000/`
- **PowerShell Test:**
  ```powershell
  Invoke-RestMethod -Uri "http://127.0.0.1:5000/" -Method GET | ConvertTo-Json
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "online",
    "service": "Digital Wallet & Payment Platform API",
    "version": "2.0.0",
    "availableEndpoints": { ... }
  }
  ```

---

### 2. Get Wallet Balance
- **Method:** `GET`
- **URI:** `http://127.0.0.1:5000/api/wallets/W101/balance`
- **PowerShell Test:**
  ```powershell
  Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/wallets/W101/balance" -Method GET | ConvertTo-Json
  ```
- **Response (200 OK):**
  ```json
  {
    "walletId": "W101",
    "userId": "U101",
    "balance": 5000.0,
    "currency": "INR",
    "source": "database"
  }
  ```

---

### 3. Add Money to Wallet
- **Method:** `POST`
- **URI:** `http://127.0.0.1:5000/api/wallets/W101/add-money`
- **Payload:** `{"amount": 1000.0, "paymentMethod": "UPI"}`
- **PowerShell Test:**
  ```powershell
  $body = @{ amount = 1000.0; paymentMethod = "UPI" } | ConvertTo-Json
  Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/wallets/W101/add-money" -Method POST -Body $body -ContentType "application/json" | ConvertTo-Json
  ```
- **Response (201 Created):**
  ```json
  {
    "success": true,
    "message": "Successfully added INR 1,000.00 to wallet W101.",
    "transactionId": "TXN-7A8B9C0D1E2F",
    "walletId": "W101",
    "amountAdded": 1000.0,
    "newBalance": 6000.0,
    "status": "SUCCESS"
  }
  ```

---

### 4. Transfer Money (P2P Atomic Transfer)
- **Method:** `POST`
- **URI:** `http://127.0.0.1:5000/api/transfers`
- **Payload:** `{"fromWalletId": "W101", "toWalletId": "W102", "amount": 500.0, "idempotencyKey": "IDEMP-991"}`
- **PowerShell Test:**
  ```powershell
  $transfer = @{
      fromWalletId = "W101"
      toWalletId   = "W102"
      amount       = 500.0
      idempotencyKey = "TXN-KEY-$(Get-Random)"
  } | ConvertTo-Json

  Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/transfers" -Method POST -Body $transfer -ContentType "application/json" | ConvertTo-Json
  ```
- **Response (201 Created):**
  ```json
  {
    "success": true,
    "message": "Transfer completed successfully.",
    "transactionId": "TXN-F4D3C2B1A098",
    "fromWalletId": "W101",
    "toWalletId": "W102",
    "amount": 500.0,
    "status": "SUCCESS",
    "senderRemainingBalance": 4500.0,
    "timestamp": "2026-10-12T09:40:00.123456"
  }
  ```

---

### 5. Get Transaction History
- **Method:** `GET`
- **URI:** `http://127.0.0.1:5000/api/wallets/W101/transactions`
- **PowerShell Test:**
  ```powershell
  Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/wallets/W101/transactions" -Method GET | ConvertTo-Json
  ```
- **Response (200 OK):**
  ```json
  {
    "walletId": "W101",
    "count": 1,
    "transactions": [
      {
        "transactionId": "TXN-F4D3C2B1A098",
        "senderWalletId": "W101",
        "receiverWalletId": "W102",
        "amount": 500.0,
        "type": "TRANSFER",
        "status": "SUCCESS",
        "timestamp": "2026-10-12T09:40:00.123456"
      }
    ]
  }
  ```

---

### 6. Download PDF Transaction Receipt
- **Method:** `GET`
- **URI:** `http://127.0.0.1:5000/api/transactions/<transaction_id>/download`
- **PowerShell Download Command:**
  ```powershell
  Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/transactions/TXN-F4D3C2B1A098/download" -OutFile "C:\SD\receipt.pdf"
  ```
- **Response:** Streams an official `application/pdf` binary receipt with digital audit hash.

---

## 🛡️ HTTP Status Code Matrix

| Status Code | Standard Name | Trigger Scenario |
|---|---|---|
| **200 OK** | Successful Retrieval | Balance check, transaction history, system health, PDF receipt download |
| **201 Created** | Created | Successful money transfer or add money transaction |
| **400 Bad Request** | Bad Request | Negative/zero amount, missing wallet fields, sender == receiver, fraud policy exceeded |
| **401 Unauthorized** | Unauthorized | Unauthenticated request (when JWT authentication token missing) |
| **403 Forbidden** | Forbidden | Wallet access prohibited |
| **404 Not Found** | Not Found | Wallet ID or Transaction ID does not exist |
| **409 Conflict** | Conflict | Duplicate transfer request with identical idempotency key |
| **422 Unprocessable Content** | Insufficient Funds | Sender wallet balance is lower than the requested transfer amount |
| **405 Method Not Allowed** | Method Not Allowed | Browser GET on POST endpoint |
| **500 Internal Server Error** | Server Error | Uncaught database or transaction crash (triggers automatic rollback) |

---

## 🏗️ System Design Highlights (Round 3 HLD)

1. **ACID Two-Phase Transfer Guarantee:**
   Both sender debit and receiver credit execute in a single atomic database transaction. If any condition fails, `session.rollback()` is immediately executed, leaving balances unchanged.
2. **Cache-Aside Architecture:**
   Reads query Redis first. On cache miss, data is retrieved from PostgreSQL/SQLite and cached with a 60-second TTL. On balance updates, the cache is immediately invalidated. Authoritative balance validation always executes on the database layer.
3. **Decoupled Asynchronous Event Messaging:**
   Notifications (push, email, SMS) and fraud analysis execute asynchronously via the event broker. A failure in notification dispatch never cancels or fails a committed financial transaction.
4. **Idempotency Defense:**
   Transfers require or accept an `Idempotency-Key`. Replayed identical requests return `409 Conflict` along with the original transaction record.
5. **Horizontal Scalability:**
   Stateless Flask microservices can scale horizontally behind NGINX or AWS ALB. Database connection pooling (PgBouncer) and read replicas ensure high transaction throughput.
