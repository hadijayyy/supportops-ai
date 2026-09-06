from __future__ import annotations

from statistics import mean
from typing import Any


def _rate(results: list[dict[str, Any]], key: str) -> float:
    values = [bool(row[key]) for row in results if row.get(key) is not None]
    return round(sum(values) / len(values), 4) if values else 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = percentile * (len(ordered) - 1)
    low, high = int(position), min(int(position) + 1, len(ordered) - 1)
    fraction = position - low
    return round(ordered[low] + (ordered[high] - ordered[low]) * fraction, 2)


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(row["latency_ms"]) for row in results]
    return {
        "cases_executed": len(results),
        "task_success_rate": _rate(results, "task_success"),
        "intent_accuracy": _rate(results, "intent_correct"),
        "tool_selection_accuracy": _rate(results, "tool_selection_correct"),
        "tool_argument_accuracy": _rate(results, "tool_arguments_correct"),
        "retrieval_recall_at_3": _rate(results, "retrieval_hit"),
        "citation_accuracy": _rate(results, "citation_correct"),
        "groundedness": _rate(results, "grounded"),
        "hallucination_rate": _rate(results, "hallucinated"),
        "escalation_accuracy": _rate(results, "escalation_correct"),
        "p50_latency_ms": _percentile(latencies, 0.5),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "average_input_tokens": round(mean(row["input_tokens"] for row in results), 2),
        "average_output_tokens": round(mean(row["output_tokens"] for row in results), 2),
        "estimated_cost_per_case": round(mean(row["estimated_cost"] for row in results), 8),
    }
