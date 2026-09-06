from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any

from .config import settings
from .db import Database
from .schemas import AgentResult


logger = logging.getLogger("supportops.runs")


def persist_run(db: Database, result: AgentResult) -> None:
    retrieved = [item.document_id for item in result.evidence]
    tools = [event.tool for event in result.trace if event.tool]
    errors = [event.tool for event in result.trace if event.tool and event.status == "failed"]
    trace = [event.model_dump(exclude_none=True) for event in result.trace]
    db.execute(
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            result.run_id, result.conversation_id, settings.model_name, result.intent,
            json.dumps(retrieved), json.dumps(tools), json.dumps(errors), result.outcome,
            int(result.escalation), result.latency_ms, result.usage.input_tokens,
            result.usage.output_tokens, result.usage.estimated_cost, json.dumps(trace),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    logger.info(json.dumps({"run_id": result.run_id, "intent": result.intent, "outcome": result.outcome, "escalation": result.escalation, "latency_ms": result.latency_ms, "tools_called": tools}))


def read_run(db: Database, run_id: str) -> dict[str, Any] | None:
    row = db.one("SELECT * FROM runs WHERE run_id=?", (run_id,))
    if not row:
        return None
    for key in ["retrieved_documents", "tools_called", "tool_errors", "trace_json"]:
        row[key] = json.loads(row[key])
    row["escalation"] = bool(row["escalation"])
    return row
