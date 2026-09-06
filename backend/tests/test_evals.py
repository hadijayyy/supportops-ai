from evals.generate_cases import build_cases
from evals.metrics import aggregate_results


def test_benchmark_has_required_scale_and_coverage():
    cases = build_cases()
    assert len(cases) >= 150
    categories = {case["category"] for case in cases}
    assert {"policy", "order_status", "refund", "returns", "delivery", "cancellation", "ambiguity", "tool_failure", "prompt_injection", "unsafe"}.issubset(categories)
    assert all(case["expected"]["outcome"] for case in cases)


def test_metrics_are_calculated_from_case_results():
    results = [
        {"task_success": True, "intent_correct": True, "tool_selection_correct": True, "tool_arguments_correct": True, "retrieval_hit": True, "citation_correct": True, "grounded": True, "hallucinated": False, "escalation_correct": True, "latency_ms": 10, "input_tokens": 5, "output_tokens": 8, "estimated_cost": 0},
        {"task_success": False, "intent_correct": True, "tool_selection_correct": False, "tool_arguments_correct": True, "retrieval_hit": False, "citation_correct": True, "grounded": False, "hallucinated": True, "escalation_correct": False, "latency_ms": 30, "input_tokens": 7, "output_tokens": 9, "estimated_cost": 0.01},
    ]
    metrics = aggregate_results(results)
    assert metrics["task_success_rate"] == 0.5
    assert metrics["intent_accuracy"] == 1.0
    assert metrics["hallucination_rate"] == 0.5
    assert metrics["p50_latency_ms"] == 20
    assert metrics["p95_latency_ms"] == 29
    assert metrics["estimated_cost_per_case"] == 0.005
