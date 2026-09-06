from __future__ import annotations

from time import perf_counter
import re
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from .config import settings
from .db import Database
from .models import PolicyEvidence, TraceEvent, ToolResult
from .llm import configured_classifier
from .rag import PolicyRetriever
from .schemas import AgentRequest, AgentResult, HumanHandoff, Intent, Usage
from .tools import ToolRegistry


ORDER_PATTERN = re.compile(r"\bORD-\d{5}\b", re.IGNORECASE)
INJECTION_PATTERNS = (
    "ignore your refund policy", "ignore previous instructions", "ignore system instructions",
    "ignore all previous", "disregard previous", "do not follow", "system prompt", "developer message",
    "refund everything", "refund every order", "bypass authorization", "bypass controls", "override the policy",
    "override safety",
)
POLICY_TERMS = (
    "policy", "policies", "rule", "rules", "how many days", "return window", "eligibility",
    "eligible", "allowed", "shipping", "delivery", "payment", "refund", "return",
)
POLICY_ACTION_TERMS = (
    "refund my", "refund it", "get a refund", "issue a refund", "process a refund",
    "send me a refund", "cancel my", "cancel order",
)


def _looks_like_policy_question(message: str) -> bool:
    normalized = message.lower()
    if not any(term in normalized for term in POLICY_TERMS):
        return False
    if any(term in normalized for term in POLICY_ACTION_TERMS):
        return False
    return "?" in message or normalized.startswith(("what", "can i", "am i", "how", "is ", "are ", "tell me", "please explain", "explain"))


def _policy_category(message: str) -> str | None:
    normalized = message.lower()
    if any(term in normalized for term in ("lost", "hasn't arrived", "has not arrived", "late", "missing package")):
        return "lost_packages"
    if any(term in normalized for term in ("damaged", "damage", "broken", "defective")):
        return "damaged_items"
    if any(term in normalized for term in ("cancel", "cancellation")):
        return "cancellations"
    if any(term in normalized for term in ("payment", "charged", "charge", "card", "dispute")):
        return "payments"
    if any(term in normalized for term in ("shipping", "delivery", "tracking", "shipment")):
        return "shipping"
    if any(term in normalized for term in ("return", "returns")):
        return "returns"
    if any(term in normalized for term in ("refund", "refunded")):
        return "refunds"
    return None


class AgentState(TypedDict, total=False):
    request: AgentRequest
    run_id: str
    intent: Intent
    confidence: float
    order_id: str | None
    customer: dict[str, Any] | None
    order: dict[str, Any] | None
    shipment: dict[str, Any] | None
    evidence: list[PolicyEvidence]
    trace: list[TraceEvent]
    risk_flags: list[str]
    authorization: str
    escalation_reason: str | None
    outcome: str
    response: str
    action_result: dict[str, Any] | None
    handoff: HumanHandoff | None


class SupportAgent:
    def __init__(self, db: Database):
        self.db = db
        self.tools = ToolRegistry(db)
        self.rag = PolicyRetriever(db)
        self.classifier = configured_classifier()
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("understand_intent", self._understand_intent)
        workflow.add_node("identify_context", self._identify_context)
        workflow.add_node("retrieve_policy", self._retrieve_policy)
        workflow.add_node("execute_operations", self._execute_operations)
        workflow.add_node("authorization_gate", self._authorization_gate)
        workflow.add_node("finalize", self._finalize)
        workflow.add_edge(START, "understand_intent")
        workflow.add_edge("understand_intent", "identify_context")
        workflow.add_edge("identify_context", "retrieve_policy")
        workflow.add_edge("retrieve_policy", "execute_operations")
        workflow.add_edge("execute_operations", "authorization_gate")
        workflow.add_edge("authorization_gate", "finalize")
        workflow.add_edge("finalize", END)
        return workflow.compile()

    def run(self, request: AgentRequest) -> AgentResult:
        started = perf_counter()
        initial: AgentState = {
            "request": request, "run_id": f"RUN-{uuid4().hex[:10].upper()}", "trace": [],
            "evidence": [], "risk_flags": [], "authorization": "not_required",
            "outcome": "resolved", "response": "", "action_result": None,
            "handoff": None, "escalation_reason": None,
        }
        state = self.graph.invoke(initial)
        latency = round((perf_counter() - started) * 1000, 2)
        input_tokens = max(1, len(request.message) // 4)
        output_tokens = max(1, len(state["response"]) // 4)
        cost = (
            input_tokens * settings.input_token_cost_per_million
            + output_tokens * settings.output_token_cost_per_million
        ) / 1_000_000
        return AgentResult(
            run_id=state["run_id"], conversation_id=request.conversation_id,
            intent=state["intent"], confidence=state["confidence"], outcome=state["outcome"],
            response=state["response"], customer=state.get("customer"), order=state.get("order"),
            shipment=state.get("shipment"), evidence=state.get("evidence", []), trace=state["trace"],
            risk_flags=state["risk_flags"], authorization=state["authorization"],
            escalation=state["outcome"] == "escalated", handoff=state.get("handoff"),
            action_result=state.get("action_result"), latency_ms=latency,
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens, estimated_cost=round(cost, 8)),
        )

    def _understand_intent(self, state: AgentState) -> dict[str, Any]:
        raw_message = state["request"].message
        message = raw_message.lower()
        risks = list(state["risk_flags"])
        if any(pattern in message for pattern in INJECTION_PATTERNS):
            risks.append("prompt_injection")

        # Policy questions must win over action words and optional model output.
        if _looks_like_policy_question(raw_message) and not risks:
            intent: Intent = "policy_question"
            confidence = 0.96
        elif self.classifier and not risks:
            try:
                classified = self.classifier.classify(raw_message)
                intent, confidence = classified.intent, classified.confidence
            except Exception:
                risks.append("model_fallback")
                intent, confidence = "unknown", 0.0
        else:
            intent, confidence = "unknown", 0.0

        if intent == "unknown":
            if ("lost" in message or "hasn't arrived" in message or "has not arrived" in message or "late" in message) and "refund" in message:
                intent = "lost_package_refund"
                confidence = 0.97
            elif "refund" in message or "damaged" in message or "broken" in message:
                intent = "refund"
                confidence = 0.96
            elif "cancel" in message:
                intent = "cancellation"
                confidence = 0.95
            elif any(word in message for word in ["where is", "track", "status", "shipment", "shipped"]):
                intent = "order_status"
                confidence = 0.96
            elif "policy" in message and "prompt_injection" not in risks and not any(term in message for term in POLICY_ACTION_TERMS):
                intent = "policy_question"
                confidence = 0.92
            else:
                intent = "unknown"
                confidence = 0.35

        match = ORDER_PATTERN.search(raw_message)
        trace = state["trace"] + [TraceEvent(step="intent", status="completed", label="Intent classified", detail=f"{intent} · {confidence:.0%} confidence")]
        return {"intent": intent, "confidence": confidence, "order_id": match.group(0).upper() if match else None, "risk_flags": risks, "trace": trace}

    def _record_tool(self, trace: list[TraceEvent], result: ToolResult, label: str, arguments: dict[str, Any] | None = None) -> list[TraceEvent]:
        safe = {key: value for key, value in result.data.items() if key not in {"email", "fraud_flag"}}
        safe_input = {key: value for key, value in (arguments or {}).items() if key not in {"email", "idempotency_key"}}
        return trace + [TraceEvent(step="tool", status="completed" if result.ok else "failed", label=label, detail=result.message, tool=result.tool, input=safe_input, output=safe)]

    def _identify_context(self, state: AgentState) -> dict[str, Any]:
        if state["intent"] == "policy_question":
            return {}
        trace = state["trace"]
        customer = None
        if state["request"].customer_id:
            result = self.tools.execute("get_customer", {"customer_id": state["request"].customer_id})
            trace = self._record_tool(trace, result, "Customer identified" if result.ok else "Customer could not be identified", {"customer_id": state["request"].customer_id})
            if result.ok:
                customer = {
                    "id": result.data["id"],
                    "name": result.data["name"],
                    "verified": bool(result.data.get("verified")),
                    "tier": result.data.get("tier"),
                }
                if not customer["verified"]:
                    return {
                        "trace": trace,
                        "customer": customer,
                        "escalation_reason": "Customer identity could not be verified",
                        "risk_flags": state["risk_flags"] + ["customer_unverified"],
                    }
            else:
                return {"trace": trace, "escalation_reason": "Identity could not be verified", "risk_flags": state["risk_flags"] + ["unresolved_identity"]}
        else:
            return {"trace": trace, "escalation_reason": "Customer identity is required", "risk_flags": state["risk_flags"] + ["unresolved_identity"]}

        order_id = state.get("order_id")
        if not order_id:
            return {"trace": trace, "customer": customer, "escalation_reason": "Order reference is missing", "risk_flags": state["risk_flags"] + ["unresolved_order"]}
        order_result = self.tools.execute("get_order", {"order_id": order_id})
        trace = self._record_tool(trace, order_result, "Order retrieved" if order_result.ok else "Order could not be retrieved", {"order_id": order_id})
        if not order_result.ok or order_result.data.get("customer_id") != customer["id"]:
            return {"trace": trace, "customer": customer, "escalation_reason": "Order ownership could not be verified", "risk_flags": state["risk_flags"] + ["unresolved_order"]}
        return {"trace": trace, "customer": customer, "order": order_result.data}

    def _retrieve_policy(self, state: AgentState) -> dict[str, Any]:
        if state.get("escalation_reason") or state["intent"] == "order_status":
            return {}
        category = (
            _policy_category(state["request"].message)
            if state["intent"] == "policy_question"
            else {
                "refund": "damaged_items",
                "lost_package_refund": "lost_packages",
                "cancellation": "cancellations",
            }.get(state["intent"])
        )
        evidence = self.rag.search(state["request"].message, category=category, k=settings.retrieval_k)
        if not evidence or evidence[0].score < 0.2:
            return {"evidence": evidence, "escalation_reason": "No reliable policy evidence was available", "risk_flags": state["risk_flags"] + ["policy_unavailable"]}
        trace = state["trace"] + [TraceEvent(step="retrieval", status="completed", label=f"{evidence[0].title} v{evidence[0].version} retrieved", detail=f"{len(evidence)} attributable policy sources")]
        return {"evidence": evidence, "trace": trace}

    def _execute_operations(self, state: AgentState) -> dict[str, Any]:
        if state.get("escalation_reason") or state["intent"] == "policy_question" or "prompt_injection" in state["risk_flags"]:
            return {}
        order_id = state["order"]["id"]
        trace = state["trace"]
        shipment = None
        if state["intent"] in {"order_status", "lost_package_refund"}:
            shipped = self.tools.execute("get_shipment", {"order_id": order_id})
            trace = self._record_tool(trace, shipped, "Shipping status checked", {"order_id": order_id})
            if not shipped.ok:
                return {"trace": trace, "escalation_reason": "Shipment lookup failed", "risk_flags": state["risk_flags"] + ["tool_failure"]}
            shipment = shipped.data
        if state["intent"] == "order_status":
            return {"trace": trace, "shipment": shipment}
        if state["intent"] == "cancellation":
            cancelled = self.tools.execute("cancel_order", {"order_id": order_id})
            trace = self._record_tool(trace, cancelled, "Cancellation attempted", {"order_id": order_id})
            if cancelled.ok:
                return {"trace": trace, "action_result": cancelled.data, "authorization": "auto_approved", "outcome": "cancelled"}
            return {"trace": trace, "escalation_reason": cancelled.message or "Cancellation requires review", "authorization": "human_required"}

        reason = "lost" if state["intent"] == "lost_package_refund" else "damaged"
        eligibility = self.tools.execute("check_refund_eligibility", {"order_id": order_id, "reason": reason})
        trace = self._record_tool(trace, eligibility, "Refund eligibility verified", {"order_id": order_id, "reason": reason})
        decision = eligibility.data
        risks = list(dict.fromkeys(state["risk_flags"] + decision.get("risk_flags", [])))
        if not decision.get("eligible"):
            return {"trace": trace, "shipment": shipment, "risk_flags": risks, "authorization": "denied", "outcome": "denied", "action_result": decision}
        calculated = self.tools.execute("calculate_refund", {"order_id": order_id})
        trace = self._record_tool(trace, calculated, "Refund amount calculated", {"order_id": order_id})
        if not calculated.ok:
            return {"trace": trace, "shipment": shipment, "risk_flags": risks + ["tool_failure"], "escalation_reason": "Refund calculation failed"}
        return {"trace": trace, "shipment": shipment, "risk_flags": risks, "authorization": decision["authorization"], "action_result": {"decision": decision, "calculation": calculated.data}}

    def _authorization_gate(self, state: AgentState) -> dict[str, Any]:
        if "prompt_injection" in state["risk_flags"]:
            trace = state["trace"] + [TraceEvent(step="authorization", status="blocked", label="Unsafe instruction blocked", detail="System policy and financial controls remain enforced")]
            return {"trace": trace, "authorization": "denied", "outcome": "blocked", "action_result": None}
        if state.get("escalation_reason"):
            return self._escalate(state, state["escalation_reason"])
        if state["intent"] in {"policy_question", "order_status"} or state["outcome"] in {"cancelled", "denied"}:
            return {}
        if state["authorization"] == "human_required":
            return self._escalate(state, "Refund exceeds the automatic authorization boundary or carries elevated risk")
        if state["authorization"] != "auto_approved":
            return {}
        detail = state["action_result"]
        reason = "lost" if state["intent"] == "lost_package_refund" else "damaged"
        issued = self.tools.execute("issue_refund", {
            "order_id": state["order"]["id"], "amount": detail["calculation"]["amount"], "reason": reason,
            "idempotency_key": f"{state['request'].conversation_id}:{state['order']['id']}:{reason}",
        })
        trace = self._record_tool(state["trace"], issued, "Refund processed" if issued.ok else "Refund could not be processed", {"order_id": state["order"]["id"], "amount": detail["calculation"]["amount"], "reason": reason})
        if not issued.ok:
            updated = dict(state)
            updated["trace"] = trace
            return self._escalate(updated, issued.message or "Refund tool failed")
        return {"trace": trace, "outcome": "refunded", "action_result": issued.data}

    def _escalate(self, state: AgentState, reason: str) -> dict[str, Any]:
        evidence_ids = [item.document_id for item in state.get("evidence", [])]
        attempted = [event.tool for event in state["trace"] if event.tool]
        args = {
            "customer_id": state.get("customer", {}).get("id") if state.get("customer") else state["request"].customer_id,
            "order_id": state.get("order", {}).get("id") if state.get("order") else state.get("order_id"),
            "reason": reason, "evidence": [{"document_id": value} for value in evidence_ids],
            "actions_attempted": attempted, "recommended_next_step": "Verify the flagged condition and approve or deny the proposed action.",
            "priority": "high" if any(flag in state["risk_flags"] for flag in ["fraud_flag", "threshold", "tool_failure"]) else "normal",
        }
        ticket = self.tools.execute("escalate_to_human", args)
        trace = self._record_tool(state["trace"], ticket, "Human review requested", {"customer_id": args["customer_id"], "order_id": args["order_id"], "reason": reason})
        handoff = HumanHandoff(
            case_id=ticket.data.get("case_id", "CASE-UNAVAILABLE"), customer=args["customer_id"], order=args["order_id"],
            reason=reason, relevant_evidence=evidence_ids, actions_attempted=attempted,
            recommended_next_step=args["recommended_next_step"],
        )
        return {"trace": trace, "outcome": "escalated", "authorization": "human_required", "handoff": handoff, "action_result": None}

    def _finalize(self, state: AgentState) -> dict[str, Any]:
        if state["outcome"] == "blocked":
            response = "I can’t bypass NovaCart’s refund policy or authorization controls. No financial action was taken."
        elif state["outcome"] == "escalated":
            case_id = state["handoff"].case_id if state.get("handoff") else "pending"
            response = f"I could not verify or authorize this request safely, so I sent it for human review as {case_id}. No refund was issued."
        elif state["outcome"] == "refunded":
            action = state["action_result"]
            refs = ", ".join(f"{item.document_id} v{item.version}" for item in state["evidence"][:2])
            response = f"Refund {action['refund_id']} for ${action['amount']:.2f} was processed to the original payment method. Policy evidence: {refs}."
        elif state["outcome"] == "cancelled":
            response = f"Order {state['order']['id']} was cancelled before fulfillment."
        elif state["outcome"] == "denied":
            refs = ", ".join(f"{item.document_id} v{item.version}" for item in state["evidence"][:2])
            response = f"This order is not eligible for an automatic refund under the verified conditions. No refund was issued. Policy evidence: {refs}."
        elif state["intent"] == "order_status":
            shipment = state["shipment"]
            response = f"Order {state['order']['id']} is {shipment['status'].replace('_', ' ')} with {shipment['carrier']}. Latest update: {shipment['last_event']}. Expected delivery: {shipment['eta']}."
        elif state["intent"] == "policy_question":
            top = state["evidence"][0]
            response = f"According to {top.title} v{top.version}: {top.excerpt} Source: {top.document_id}, effective {top.effective_date}."
        else:
            response = "I could not resolve this request automatically."
        trace = state["trace"] + [TraceEvent(step="result", status="completed", label="Grounded response prepared")]
        return {"response": response, "trace": trace}
