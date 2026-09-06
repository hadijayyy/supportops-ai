from __future__ import annotations

import json
import os
from typing import Protocol

import httpx
from pydantic import BaseModel, Field

from .schemas import Intent


class IntentClassification(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0, le=1)


class IntentClassifier(Protocol):
    def classify(self, message: str) -> IntentClassification: ...


class OpenAIIntentClassifier:
    """Optional structured-output classifier; actions remain deterministic."""

    def __init__(self, api_key: str, model: str = "gpt-5-mini"):
        self.api_key = api_key
        self.model = model

    def classify(self, message: str) -> IntentClassification:
        schema = IntentClassification.model_json_schema()
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "instructions": "Classify a NovaCart support message. Never propose or authorize actions.",
                "input": message,
                "text": {"format": {"type": "json_schema", "name": "intent_classification", "strict": True, "schema": schema}},
            },
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        text = next(
            part["text"] for item in payload.get("output", []) for part in item.get("content", [])
            if part.get("type") == "output_text"
        )
        return IntentClassification.model_validate(json.loads(text))


def configured_classifier() -> IntentClassifier | None:
    api_key = os.getenv("OPENAI_API_KEY")
    return OpenAIIntentClassifier(api_key, os.getenv("OPENAI_MODEL", "gpt-5-mini")) if api_key else None
