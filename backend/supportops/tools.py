from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from .db import Database
from .models import ToolResult
from .rules import can_cancel, evaluate_refund


class CustomerInput(BaseModel):
    customer_id: str | None = None
    email: str | None = None


class CustomerOrdersInput(BaseModel):
    customer_id: str


class OrderInput(BaseModel):
    order_id: str


class EligibilityInput(OrderInput):
    reason: str


class RefundInput(OrderInput):
    amount: float = Field(gt=0)
    reason: str
    idempotency_key: str = Field(min_length=3, max_length=120)


class TicketInput(BaseModel):
    customer_id: str | None = None
    order_id: str | None = None
    reason: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    actions_attempted: list[str] = Field(default_factory=list)
    recommended_next_step: str
    priority: str = "normal"


class ToolRegistry:
    def __init__(self, db: Database):
        self.db = db
        self._tools: dict[str, tuple[type[BaseModel], Callable[[BaseModel], ToolResult]]] = {
            "get_customer": (CustomerInput, self._get_customer),
            "get_customer_orders": (CustomerOrdersInput, self._get_customer_orders),
            "get_order": (OrderInput, self._get_order),
            "get_shipment": (OrderInput, self._get_shipment),
            "check_refund_eligibility": (EligibilityInput, self._check_refund_eligibility),
            "calculate_refund": (OrderInput, self._calculate_refund),
            "issue_refund": (RefundInput, self._issue_refund),
            "cancel_order": (OrderInput, self._cancel_order),
            "create_support_ticket": (TicketInput, lambda value: self._create_ticket(value, "create_support_ticket")),
            "escalate_to_human": (TicketInput, lambda value: self._create_ticket(value, "escalate_to_human")),
        }

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        entry = self._tools.get(name)
        if not entry:
            return ToolResult(tool=name, ok=False, error_code="unknown_tool", message="Tool is not registered")
        schema, handler = entry
        try:
            parsed = schema.model_validate(arguments)
            return handler(parsed)
        except ValidationError as exc:
            return ToolResult(tool=name, ok=False, error_code="invalid_arguments", message=exc.errors()[0]["msg"])
        except Exception:
            return ToolResult(tool=name, ok=False, error_code="tool_failure", message="The operation could not be completed safely")

    def _get_customer(self, value: CustomerInput) -> ToolResult:
        if not value.customer_id and not value.email:
            return ToolResult(tool="get_customer", ok=False, error_code="invalid_arguments", message="customer_id or email is required")
        field, needle = ("id", value.customer_id) if value.customer_id else ("email", value.email)
        customer = self.db.one(f"SELECT id, name, email, verified, fraud_flag, tier FROM customers WHERE {field}=?", (needle,))
        if not customer:
            return ToolResult(tool="get_customer", ok=False, error_code="not_found", message="Customer not found")
        customer["verified"] = bool(customer["verified"])
        customer["fraud_flag"] = bool(customer["fraud_flag"])
        return ToolResult(tool="get_customer", ok=True, data=customer)

    def _get_customer_orders(self, value: CustomerOrdersInput) -> ToolResult:
        rows = self.db.all("SELECT id, status, total, created_at, delivered_at FROM orders WHERE customer_id=? ORDER BY created_at DESC LIMIT 20", (value.customer_id,))
        return ToolResult(tool="get_customer_orders", ok=True, data={"orders": rows, "count": len(rows)})

    def _get_order(self, value: OrderInput) -> ToolResult:
        order = self.db.one("SELECT * FROM orders WHERE id=?", (value.order_id,))
        if not order:
            return ToolResult(tool="get_order", ok=False, error_code="not_found", message="Order not found")
        return ToolResult(tool="get_order", ok=True, data=order)

    def _get_shipment(self, value: OrderInput) -> ToolResult:
        shipment = self.db.one("SELECT * FROM shipments WHERE order_id=?", (value.order_id,))
        if not shipment:
            return ToolResult(tool="get_shipment", ok=False, error_code="not_found", message="Shipment not found")
        return ToolResult(tool="get_shipment", ok=True, data=shipment)

    def _check_refund_eligibility(self, value: EligibilityInput) -> ToolResult:
        decision = evaluate_refund(self.db, value.order_id, value.reason)
        return ToolResult(tool="check_refund_eligibility", ok=True, data=decision.model_dump())

    def _calculate_refund(self, value: OrderInput) -> ToolResult:
        order = self.db.one("SELECT total FROM orders WHERE id=?", (value.order_id,))
        if not order:
            return ToolResult(tool="calculate_refund", ok=False, error_code="not_found", message="Order not found")
        return ToolResult(tool="calculate_refund", ok=True, data={"amount": round(float(order["total"]), 2), "currency": "USD", "method": "original_payment"})

    def _issue_refund(self, value: RefundInput) -> ToolResult:
        with self.db.transaction() as connection:
            existing_key = connection.execute("SELECT * FROM refunds WHERE idempotency_key=?", (value.idempotency_key,)).fetchone()
            if existing_key:
                return ToolResult(tool="issue_refund", ok=True, data={"refund_id": existing_key["id"], "status": existing_key["status"], "amount": existing_key["amount"], "idempotent_replay": True})
            decision = evaluate_refund(self.db, value.order_id, value.reason)
            if decision.authorization != "auto_approved":
                return ToolResult(tool="issue_refund", ok=False, error_code="authorization_required", message="Deterministic authorization gate rejected automatic refund", data=decision.model_dump())
            if round(value.amount, 2) != round(decision.refundable_amount, 2):
                return ToolResult(tool="issue_refund", ok=False, error_code="amount_mismatch", message="Refund amount does not match calculated amount")
            prior = connection.execute("SELECT id FROM refunds WHERE order_id=? AND status='processed'", (value.order_id,)).fetchone()
            if prior:
                return ToolResult(tool="issue_refund", ok=False, error_code="duplicate_refund", message="Order already refunded")
            refund_id = f"REF-{uuid4().hex[:10].upper()}"
            now = datetime.now(timezone.utc).isoformat()
            connection.execute("INSERT INTO refunds VALUES (?, ?, ?, ?, ?, ?, ?)", (refund_id, value.order_id, value.amount, value.reason, "processed", value.idempotency_key, now))
            connection.execute("UPDATE orders SET status='refunded' WHERE id=?", (value.order_id,))
            return ToolResult(tool="issue_refund", ok=True, data={"refund_id": refund_id, "status": "processed", "amount": value.amount, "currency": "USD", "idempotent_replay": False})

    def _cancel_order(self, value: OrderInput) -> ToolResult:
        order = self.db.one("SELECT status FROM orders WHERE id=?", (value.order_id,))
        if not order:
            return ToolResult(tool="cancel_order", ok=False, error_code="not_found", message="Order not found")
        allowed, reason = can_cancel(order["status"])
        if not allowed:
            return ToolResult(tool="cancel_order", ok=False, error_code="authorization_required", message=reason)
        self.db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (value.order_id,))
        return ToolResult(tool="cancel_order", ok=True, data={"order_id": value.order_id, "status": "cancelled"})

    def _create_ticket(self, value: TicketInput, tool_name: str) -> ToolResult:
        ticket_id = f"CASE-{uuid4().hex[:8].upper()}"
        self.db.execute(
            "INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticket_id, value.customer_id, value.order_id, "open", value.priority, value.reason, json.dumps(value.evidence), json.dumps(value.actions_attempted), value.recommended_next_step, datetime.now(timezone.utc).isoformat()),
        )
        return ToolResult(tool=tool_name, ok=True, data={"case_id": ticket_id, "status": "open", "priority": value.priority, "recommended_next_step": value.recommended_next_step})
