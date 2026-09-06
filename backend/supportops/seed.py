from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random

from .db import Database


POLICIES = [
    ("POL-RET-031", "Returns Policy", "3.1", "returns", "2026-01-15", "NovaCart accepts unused items within 30 calendar days of delivery. Original payment is refunded after eligibility validation. Final-sale items are excluded. Identity and order must be verified."),
    ("POL-REF-042", "Refund Authorization Policy", "4.2", "refunds", "2026-03-01", "Refunds require a verified customer, an existing paid order, policy eligibility, no prior refund, and no fraud flag. Agents may automatically refund up to $250. Amounts above $250 require human approval."),
    ("POL-SHP-024", "Shipping and Delivery Policy", "2.4", "shipping", "2026-02-10", "Customers receive tracking and an estimated delivery date. A delayed package remains in transit until the carrier confirms loss or it is at least 5 calendar days beyond the promised delivery date with no carrier scan for 72 hours."),
    ("POL-LST-020", "Lost Package Resolution", "2.0", "lost_packages", "2026-04-05", "A package is considered lost when the carrier marks it lost, or when delivery is at least 5 days late and tracking has had no movement for 72 hours. Eligible lost orders may be refunded or replaced, subject to refund authorization controls."),
    ("POL-DMG-027", "Damaged Item Policy", "2.7", "damaged_items", "2026-02-20", "Damage reported within 30 days of delivery qualifies for refund review. The order must be verified and must not already have been refunded. High-value or fraud-flagged cases require human review."),
    ("POL-CAN-018", "Cancellation Policy", "1.8", "cancellations", "2026-01-05", "Orders may be cancelled automatically before fulfillment begins. Packed or shipped orders require support review; delivered orders cannot be cancelled."),
    ("POL-PAY-023", "Payment Dispute Policy", "2.3", "payments", "2026-03-12", "Payment disputes require verification against the captured payment record. Chargeback threats, mismatched identities, and suspected fraud must be escalated without issuing a refund."),
]


DEMO_ORDERS = [
    ("ORD-10428", "CUS-0001", "shipped", 80.00, 5.00, 4.00, 89.00, "2026-08-31T10:00:00Z", None, "in_transit", "2026-09-08", "Package departed regional hub"),
    ("ORD-20551", "CUS-0002", "delivered", 75.00, 5.00, 4.00, 84.00, "2026-08-20T10:00:00Z", "2026-09-01T14:00:00Z", "delivered", "2026-09-01", "Delivered at front door"),
    ("ORD-60000", "CUS-0003", "delivered", 560.00, 10.00, 30.00, 600.00, "2026-08-10T10:00:00Z", "2026-08-20T14:00:00Z", "delivered", "2026-08-20", "Delivered with signature"),
    ("ORD-30991", "CUS-0004", "shipped", 120.00, 4.00, 5.00, 129.00, "2026-08-15T10:00:00Z", None, "lost", "2026-08-31", "Carrier investigation confirms package lost"),
    ("ORD-40992", "CUS-0005", "refunded", 90.00, 5.00, 5.00, 100.00, "2026-08-01T10:00:00Z", "2026-08-10T14:00:00Z", "delivered", "2026-08-10", "Delivered at front door"),
    ("ORD-50993", "CUS-0006", "delivered", 140.00, 5.00, 5.00, 150.00, "2026-08-22T10:00:00Z", "2026-08-28T14:00:00Z", "delivered", "2026-08-28", "Delivered at front door"),
    ("ORD-61001", "CUS-0007", "processing", 40.00, 3.00, 2.00, 45.00, "2026-09-05T10:00:00Z", None, "label_created", "2026-09-12", "Shipping label created"),
]


def seed_database(db: Database) -> None:
    if db.scalar("SELECT COUNT(*) FROM customers"):
        return
    rng = random.Random(20260906)
    now = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
    with db.transaction() as connection:
        for i in range(1, 801):
            fraud = 1 if i == 6 else (1 if i % 197 == 0 else 0)
            connection.execute(
                "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)",
                (f"CUS-{i:04d}", f"Nova Customer {i}", f"customer{i}@example.test", 0 if i % 173 == 0 else 1, fraud, ["standard", "plus", "premium"][i % 3]),
            )

        for policy in POLICIES:
            connection.execute("INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?)", policy)

        used_ids = {order[0] for order in DEMO_ORDERS}
        for idx, order in enumerate(DEMO_ORDERS, start=1):
            oid, cid, status, subtotal, shipping, tax, total, created, delivered, ship_status, eta, event = order
            connection.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (oid, cid, status, subtotal, shipping, tax, total, created, delivered))
            connection.execute("INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (f"SHP-D{idx:04d}", oid, ship_status, "NovaExpress", f"NXD{idx:08d}", eta, created, delivered, event))
            connection.execute("INSERT INTO payments VALUES (?, ?, ?, ?, ?)", (f"PAY-D{idx:04d}", oid, "captured", total, "card"))

        generic_needed = 3200 - len(DEMO_ORDERS)
        for i in range(1, generic_needed + 1):
            oid = f"ORD-{70000 + i:05d}"
            if oid in used_ids:
                continue
            cid = f"CUS-{((i - 1) % 800) + 1:04d}"
            age = rng.randint(1, 120)
            created_dt = now - timedelta(days=age)
            subtotal = float(rng.randint(18, 420))
            shipping = 0.0 if subtotal >= 75 else 5.0
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + shipping + tax, 2)
            status = rng.choices(["delivered", "shipped", "processing", "cancelled"], [65, 18, 12, 5])[0]
            delivered_dt = created_dt + timedelta(days=rng.randint(2, 8)) if status == "delivered" else None
            ship_status = "delivered" if status == "delivered" else ("in_transit" if status == "shipped" else "label_created")
            eta = (created_dt + timedelta(days=7)).date().isoformat()
            connection.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (oid, cid, status, subtotal, shipping, tax, total, created_dt.isoformat(), delivered_dt.isoformat() if delivered_dt else None))
            connection.execute("INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (f"SHP-{i:06d}", oid, ship_status, ["NovaExpress", "ParcelPro", "SwiftShip"][i % 3], f"NX{i:010d}", eta, created_dt.isoformat(), delivered_dt.isoformat() if delivered_dt else None, "Delivered" if status == "delivered" else "Shipment data received"))
            connection.execute("INSERT INTO payments VALUES (?, ?, ?, ?, ?)", (f"PAY-{i:06d}", oid, "voided" if status == "cancelled" else "captured", total, ["card", "wallet", "bank_transfer"][i % 3]))

        connection.execute("INSERT INTO refunds VALUES (?, ?, ?, ?, ?, ?, ?)", ("REF-EXISTING", "ORD-40992", 100.0, "return", "processed", "existing-refund", "2026-08-15T10:00:00Z"))
