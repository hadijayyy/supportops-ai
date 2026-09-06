from __future__ import annotations

from datetime import datetime, timezone

from .config import settings
from .db import Database
from .models import RefundDecision


def _days_since(value: str | None, reference: datetime | None = None) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    reference = reference or datetime.now(timezone.utc)
    if parsed > reference:
        return None
    return max(0, (reference - parsed).days)


def evaluate_refund(db: Database, order_id: str, reason: str) -> RefundDecision:
    order = db.one(
        "SELECT o.*, c.verified, c.fraud_flag FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.id=?",
        (order_id,),
    )
    if not order:
        return RefundDecision(eligible=False, authorization="denied", refundable_amount=0, reasons=["order_not_found"], risk_flags=["unresolved_order"])

    risks: list[str] = []
    reasons: list[str] = []
    prior = db.one("SELECT id FROM refunds WHERE order_id=? AND status='processed'", (order_id,))
    shipment = db.one("SELECT * FROM shipments WHERE order_id=?", (order_id,))
    payment = db.one("SELECT amount, status FROM payments WHERE order_id=?", (order_id,))

    if not order["verified"]:
        risks.append("customer_unverified")
    if order["fraud_flag"]:
        risks.append("fraud_flag")
    if not payment or payment["status"] != "captured":
        risks.append("payment_not_captured")
    elif float(payment["amount"]) + 0.01 < float(order["total"]):
        risks.append("payment_amount_mismatch")
    if prior:
        risks.append("already_refunded")
    if order["total"] > settings.auto_refund_threshold:
        risks.append("threshold")

    normalized = reason.lower().strip()
    days = _days_since(order["delivered_at"])
    policy_eligible = False
    if normalized in {"damaged", "damage", "defective"}:
        policy_eligible = order["status"] in {"delivered", "refunded"} and days is not None and days <= 30
        reasons.append("damage_within_30_days" if policy_eligible else "damage_window_or_status_failed")
    elif normalized in {"lost", "lost_package", "delivery_lost"}:
        policy_eligible = bool(shipment and shipment["status"] == "lost")
        reasons.append("carrier_confirmed_lost" if policy_eligible else "loss_not_confirmed")
    elif normalized in {"return", "unwanted"}:
        policy_eligible = order["status"] in {"delivered", "refunded"} and days is not None and days <= 30
        reasons.append("return_within_30_days" if policy_eligible else "return_window_or_status_failed")
    else:
        reasons.append("unsupported_refund_reason")

    blocked = any(flag in risks for flag in ["customer_unverified", "already_refunded", "payment_not_captured", "payment_amount_mismatch"])
    eligible = policy_eligible and not blocked
    if not eligible:
        authorization = "denied"
    elif any(flag in risks for flag in ["fraud_flag", "threshold"]):
        authorization = "human_required"
    else:
        authorization = "auto_approved"
    return RefundDecision(eligible=eligible, authorization=authorization, refundable_amount=float(order["total"]) if eligible else 0, reasons=reasons, risk_flags=risks)


def can_cancel(order_status: str) -> tuple[bool, str]:
    if order_status == "processing":
        return True, "order_not_fulfilled"
    if order_status in {"shipped", "delivered"}:
        return False, "fulfillment_started"
    return False, f"order_{order_status}"
