from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    tool: str
    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    message: str | None = None


class RefundDecision(BaseModel):
    eligible: bool
    authorization: Literal["auto_approved", "human_required", "denied"]
    refundable_amount: float
    reasons: list[str]
    risk_flags: list[str]


class PolicyEvidence(BaseModel):
    document_id: str
    title: str
    version: str
    category: str
    effective_date: str
    excerpt: str
    score: float


class TraceEvent(BaseModel):
    step: str
    status: Literal["completed", "failed", "escalated", "blocked"]
    label: str
    detail: str | None = None
    tool: str | None = None
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
