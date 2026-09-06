from supportops.db import Database
from supportops.seed import seed_database
from supportops.tools import ToolRegistry


def registry(tmp_path):
    db = Database(tmp_path / "test.db")
    seed_database(db)
    return ToolRegistry(db)


def test_eligible_damaged_refund_executes_once(tmp_path):
    tools = registry(tmp_path)
    eligibility = tools.execute("check_refund_eligibility", {"order_id": "ORD-20551", "reason": "damaged"})
    assert eligibility.ok and eligibility.data["eligible"] is True

    first = tools.execute("issue_refund", {"order_id": "ORD-20551", "amount": 84.0, "reason": "damaged", "idempotency_key": "case-1"})
    second = tools.execute("issue_refund", {"order_id": "ORD-20551", "amount": 84.0, "reason": "damaged", "idempotency_key": "case-1"})
    assert first.ok and first.data["status"] == "processed"
    assert second.ok and second.data["refund_id"] == first.data["refund_id"]


def test_threshold_and_fraud_require_human(tmp_path):
    tools = registry(tmp_path)
    high = tools.execute("check_refund_eligibility", {"order_id": "ORD-60000", "reason": "damaged"})
    fraud = tools.execute("check_refund_eligibility", {"order_id": "ORD-50993", "reason": "damaged"})
    assert high.data["authorization"] == "human_required"
    assert "threshold" in high.data["risk_flags"]
    assert fraud.data["authorization"] == "human_required"
    assert "fraud_flag" in fraud.data["risk_flags"]


def test_duplicate_unknown_and_invalid_tools_fail_safely(tmp_path):
    tools = registry(tmp_path)
    existing = tools.execute("check_refund_eligibility", {"order_id": "ORD-40992", "reason": "return"})
    missing = tools.execute("get_order", {"order_id": "ORD-NOPE"})
    invalid = tools.execute("issue_refund", {"order_id": "ORD-20551", "amount": -10, "reason": "damaged", "idempotency_key": "bad"})
    unknown = tools.execute("delete_everything", {})
    assert existing.data["eligible"] is False and "already_refunded" in existing.data["risk_flags"]
    assert missing.ok is False and missing.error_code == "not_found"
    assert invalid.ok is False and invalid.error_code == "invalid_arguments"
    assert unknown.ok is False and unknown.error_code == "unknown_tool"
