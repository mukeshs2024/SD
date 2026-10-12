"""
Transaction receipt PDF generator using FPDF.
Produces a professional, high-clarity receipt document.
"""

from datetime import datetime
from fpdf import FPDF


class ReceiptPDF(FPDF):
    def header(self):
        # Primary Brand Bar
        self.set_fill_color(30, 41, 59)  # Slate dark #1E293B
        self.rect(0, 0, 210, 26, "F")

        # Title
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, "DIGITAL WALLET & PAYMENT PLATFORM", align="C", ln=True)

        self.set_font("Helvetica", "", 9)
        self.set_text_color(203, 213, 225)
        self.cell(0, 4, "Official Transaction Receipt & Audit Summary", align="C", ln=True)
        self.ln(8)

    def footer(self):
        self.set_y(-25)
        self.set_draw_color(226, 232, 240)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(2)

        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 116, 139)
        self.cell(0, 4, "This is a system-generated electronic receipt. No physical signature required.", align="C", ln=True)
        self.cell(0, 4, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Digital Wallet Core Engine v2.0", align="C", ln=True)


def generate_receipt_pdf_bytes(txn_data: dict) -> bytes:
    """
    Generate PDF receipt for a transaction and return raw bytes.
    txn_data keys expected:
      - transactionId
      - type ('TRANSFER', 'ADD_MONEY')
      - amount
      - status
      - senderWalletId
      - receiverWalletId
      - timestamp
      - description (optional)
    """
    pdf = ReceiptPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 41, 59)

    # Status Pill / Banner
    status = txn_data.get("status", "SUCCESS").upper()
    if status == "SUCCESS":
        pdf.set_fill_color(220, 252, 231)  # Emerald light
        pdf.set_text_color(22, 101, 52)     # Emerald dark
        status_label = "TRANSACTION SUCCESSFUL"
    else:
        pdf.set_fill_color(254, 226, 226)  # Red light
        pdf.set_text_color(153, 27, 27)    # Red dark
        status_label = f"TRANSACTION {status}"

    pdf.set_xy(15, 32)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(180, 10, f"  STATUS: {status_label}", border=1, ln=True, fill=True)
    pdf.ln(4)

    # Receipt Info Card
    pdf.set_draw_color(203, 213, 225)
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(15, 46, 180, 24, "FD")

    pdf.set_xy(20, 49)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(85, 5, "TRANSACTION REFERENCE ID", ln=False)
    pdf.cell(85, 5, "DATE & TIME (UTC)", ln=True)

    pdf.set_xy(20, 56)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(85, 6, str(txn_data.get("transactionId", "N/A")), ln=False)
    pdf.cell(85, 6, str(txn_data.get("timestamp", datetime.utcnow().isoformat()))[:19], ln=True)

    pdf.ln(12)

    # Financial Summary Table Header
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, "Transaction Breakdown", ln=True)
    pdf.ln(2)

    pdf.set_fill_color(241, 245, 249)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(110, 8, "Description / Field", border="TB", fill=True)
    pdf.cell(70, 8, "Details", border="TB", align="R", ln=True, fill=True)

    rows = [
        ("Transaction Type", txn_data.get("type", "TRANSFER")),
        ("Sender Wallet ID", txn_data.get("senderWalletId") or "EXTERNAL PAYMENT GATEWAY / SYSTEM"),
        ("Receiver Wallet ID", txn_data.get("receiverWalletId", "N/A")),
        ("Payment Note", txn_data.get("description") or "Instant Wallet Transfer"),
        ("Base Amount", f"INR {float(txn_data.get('amount', 0.0)):,.2f}"),
        ("Platform Processing Fee", "INR 0.00 (Free Tier)"),
        ("Applicable GST / Taxes", "INR 0.00"),
    ]

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 41, 59)
    for label, val in rows:
        pdf.cell(110, 7, f" {label}", border="B")
        pdf.cell(70, 7, f"{val} ", border="B", align="R", ln=True)

    # Net Amount Highlight
    pdf.ln(3)
    pdf.set_fill_color(238, 242, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 27, 75)
    pdf.cell(110, 10, " Total Settled Amount", border=1, fill=True)
    pdf.cell(70, 10, f"INR {float(txn_data.get('amount', 0.0)):,.2f} ", border=1, align="R", fill=True, ln=True)

    pdf.ln(8)

    # Security & Verification Box
    pdf.set_fill_color(250, 250, 250)
    pdf.set_draw_color(226, 232, 240)
    pdf.rect(15, pdf.get_y(), 180, 28, "FD")

    pdf.set_xy(20, pdf.get_y() + 4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(51, 65, 85)
    pdf.cell(0, 5, "SECURITY VERIFICATION & AUDIT SIGNATURE", ln=True)

    pdf.set_xy(20, pdf.get_y() + 1)
    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(100, 116, 139)
    import hashlib
    raw_hash_seed = f"{txn_data.get('transactionId')}-{txn_data.get('amount')}-{txn_data.get('timestamp')}"
    sha = hashlib.sha256(raw_hash_seed.encode("utf-8")).hexdigest()
    pdf.cell(0, 4, f"Hash: SHA256:{sha}", ln=True)
    pdf.set_x(20)
    pdf.cell(0, 4, "Settlement Protocol: ACID Compliant Two-Phase Balance Lock & Journal", ln=True)

    output = pdf.output(dest="S")
    if isinstance(output, str):
        return output.encode("latin-1")
    return bytes(output)
