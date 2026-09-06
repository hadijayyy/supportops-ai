from fastapi.testclient import TestClient

from supportops.api import create_app
from supportops.db import Database


def client(tmp_path):
    return TestClient(create_app(Database(tmp_path / "api.db")))


def test_health_and_demo_customers(tmp_path):
    api = client(tmp_path)
    health = api.get("/health")
    demos = api.get("/api/customers/demo")
    assert health.status_code == 200 and health.json()["status"] == "healthy"
    assert demos.status_code == 200 and len(demos.json()) >= 5


def test_agent_run_is_persisted_and_trace_is_sanitized(tmp_path):
    api = client(tmp_path)
    response = api.post("/api/agent/run", json={"customer_id": "CUS-0001", "message": "Where is order ORD-10428?"})
    assert response.status_code == 200
    result = response.json()
    stored = api.get(f"/api/runs/{result['run_id']}")
    assert stored.status_code == 200
    assert stored.json()["outcome"] == "resolved"
    assert "customer1@example.test" not in stored.text


def test_architecture_contract(tmp_path):
    api = client(tmp_path)
    response = api.get("/api/architecture")
    assert response.status_code == 200
    body = response.json()
    assert body["orchestrator"] == "LangGraph"
    assert {"policy_retrieval", "operational_tools", "business_rules", "human_escalation"}.issubset(body["capabilities"])
