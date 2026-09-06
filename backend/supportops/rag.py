from __future__ import annotations

from collections import Counter
import math
import re

from .db import Database
from .models import PolicyEvidence


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
SYNONYMS = {
    "late": "lost delivery shipping",
    "arrived": "delivery delivered",
    "broken": "damaged damage",
    "damage": "damaged",
    "refund": "refunds authorization",
    "return": "returns unused",
    "track": "tracking shipment shipping",
    "chargeback": "payment dispute",
}


def _tokens(text: str) -> Counter[str]:
    raw = TOKEN_PATTERN.findall(text.lower())
    expanded = list(raw)
    for token in raw:
        expanded.extend(SYNONYMS.get(token, "").split())
    return Counter(expanded)


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    numerator = sum(value * right.get(key, 0) for key, value in left.items())
    denominator = math.sqrt(sum(v * v for v in left.values())) * math.sqrt(sum(v * v for v in right.values()))
    return numerator / denominator if denominator else 0.0


class PolicyRetriever:
    """Deterministic lexical vector search with a pgvector-compatible result contract."""

    def __init__(self, db: Database):
        self.db = db

    def search(self, query: str, category: str | None = None, k: int = 3) -> list[PolicyEvidence]:
        rows = self.db.all("SELECT * FROM policies")
        query_vector = _tokens(query)
        ranked: list[tuple[float, dict]] = []
        for row in rows:
            document_vector = _tokens(f"{row['title']} {row['category']} {row['content']}")
            score = _cosine(query_vector, document_vector)
            if category and row["category"] == category:
                score += 0.45
            ranked.append((score, row))
        ranked.sort(key=lambda item: (-item[0], item[1]["document_id"]))
        return [
            PolicyEvidence(
                document_id=row["document_id"], title=row["title"], version=row["version"],
                category=row["category"], effective_date=row["effective_date"],
                excerpt=row["content"][:360], score=round(score, 4),
            )
            for score, row in ranked[: max(1, k)] if score > 0
        ]
