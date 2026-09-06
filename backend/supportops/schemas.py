from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .models import PolicyEvidence, TraceEvent


Intent = Literal["policy_question", "order_status", "refund", "lost_package_refund", "cancellation", "unknown"]


class AgentRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    customer_id: str | None = None
    conversation_id: str = Field(default_factory=lambda: f"CONV-{uuid4().hex[:10].upper()}")
    demo_mode: bool = False


class HumanHandoff(BaseModel):
    case_id: str
    customer: str | None
    order: str | None
    reason: str
    relevant_evidence: list[str]
    actions_attempted: list[str]
    recommended_next_step: str


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0


class AgentResult(BaseModel):
    run_id: str
    conversation_id: str
    intent: Intent
    confidence: float
    outcome: Literal["resolved", "refunded", "cancelled", "denied", "blocked", "escalated"]
    response: str
    customer: dict[str, Any] | None = None
    order: dict[str, Any] | None = None
    shipment: dict[str, Any] | None = None
    evidence: list[PolicyEvidence] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    authorization: str = "not_required"
    escalation: bool = False
    handoff: HumanHandoff | None = None
    action_result: dict[str, Any] | None = None
    latency_ms: float = 0
    usage: Usage = Field(default_factory=Usage)
