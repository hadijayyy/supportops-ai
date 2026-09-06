from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from supportops.agent import SupportAgent
from supportops.db import Database
from supportops.models import ToolResult
from supportops.schemas import AgentRequest
from supportops.seed import seed_database

from .generate_cases import build_cases
from .metrics import aggregate_results


ROOT = Path(__file__).resolve().parents[1]


def _score(case: dict[str, Any], result, valid_policies: set[str]) -> dict[str, Any]:
    expected = case["expected"]
    tools = [event.tool for event in result.trace if event.tool]
    expected_order = expected.get("order_id")
    tool_inputs = [event.input for event in result.trace if event.tool and event.input]
    arguments_correct = all(
        not payload.get("order_id") or payload["order_id"] == expected_order
        for payload in tool_inputs
    )
    evidence_ids = [item.document_id for item in result.evidence]
    expected_policy = expected.get("policy")
    retrieval_hit = expected_policy in evidence_ids if expected_policy else None
    citation_correct = (all(value in valid_policies for value in evidence_ids) and (not expected_policy or expected_policy in evidence_ids)) if evidence_ids or expected_policy else None
    response_orders = set(re.findall(r"ORD-\d{5}", result.response))
    response_policies = set(re.findall(r"POL-[A-Z]+-\d+", result.response))
    hallucinated = bool((response_orders - ({expected_order} if expected_order else set())) or (response_policies - set(evidence_ids)))
    grounded = (
        (result.outcome == "refunded" and bool(result.action_result and result.action_result.get("refund_id")))
        or (result.outcome == "escalated" and bool(result.handoff and result.handoff.case_id))
        or (result.outcome == "blocked" and "prompt_injection" in result.risk_flags)
        or (result.outcome == "cancelled" and bool(result.action_result))
        or (result.intent == "order_status" and result.shipment is not None and result.shipment["carrier"] in result.response)
        or (result.intent == "policy_question" and bool(evidence_ids) and evidence_ids[0] in result.response)
        or result.outcome == "denied"
    )
    return {
        "case_id": case["case_id"], "category": case["category"],
        "expected_outcome": expected["outcome"], "actual_outcome": result.outcome,
        "expected_intent": expected["intent"], "actual_intent": result.intent,
        "expected_tools": expected["tools"], "actual_tools": tools,
        "task_success": result.outcome == expected["outcome"],
        "intent_correct": result.intent == expected["intent"],
        "tool_selection_correct": tools == expected["tools"],
        "tool_arguments_correct": arguments_correct,
        "retrieval_hit": retrieval_hit, "citation_correct": citation_correct,
        "grounded": grounded, "hallucinated": hallucinated,
        "escalation_correct": result.escalation == expected["escalation"],
        "latency_ms": result.latency_ms, "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens, "estimated_cost": result.usage.estimated_cost,
    }


def execute_benchmark(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cases = cases or build_cases()
    with tempfile.TemporaryDirectory(prefix="supportops-eval-") as temp:
        pristine_path = Path(temp) / "pristine.db"
        pristine = Database(pristine_path)
        seed_database(pristine)
        valid_policies = {row["document_id"] for row in pristine.all("SELECT document_id FROM policies")}
        results = []
        for index, case in enumerate(cases):
            case_path = Path(temp) / f"case-{index:03d}.db"
            shutil.copy2(pristine_path, case_path)
            agent = SupportAgent(Database(case_path))
            fault_tool = case.get("fault_tool")
            if fault_tool:
                original_execute = agent.tools.execute
                def fault_injected(name, arguments, *, _original=original_execute, _fault=fault_tool):
                    if name == _fault:
                        return ToolResult(tool=name, ok=False, error_code="tool_failure", message="Injected benchmark failure")
                    return _original(name, arguments)
                agent.tools.execute = fault_injected
            result = agent.run(AgentRequest(customer_id=case["customer_id"], message=case["message"], conversation_id=f"BENCH-{case['case_id']}"))
            results.append(_score(case, result, valid_policies))
    return {
        "benchmark": "SupportOps AI V1 Synthetic Benchmark",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution_mode": "deterministic orchestration; isolated seeded database per case",
        "metrics": aggregate_results(results),
        "category_counts": {category: sum(row["category"] == category for row in results) for category in sorted({row["category"] for row in results})},
        "results": results,
    }


def main() -> None:
    cases = build_cases()
    cases_path = Path(__file__).resolve().parent / "cases.json"
    cases_path.write_text(json.dumps(cases, indent=2) + "\n")
    report = execute_benchmark(cases)
    output = ROOT / "data" / "evaluation-results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    summary = {key: value for key, value in report.items() if key != "results"}
    summary["result_count"] = len(report["results"])
    (ROOT / "data" / "evaluation-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(report["metrics"], indent=2))
    print(f"Saved {len(cases)} executed cases to {output}")


if __name__ == "__main__":
    main()
