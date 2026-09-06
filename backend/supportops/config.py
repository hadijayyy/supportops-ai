from dataclasses import dataclass
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = Path("/tmp/supportops.db") if os.getenv("VERCEL") else ROOT / "data" / "supportops.db"


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path(os.getenv("SUPPORTOPS_DB_PATH", DEFAULT_DATABASE_PATH))
    auto_refund_threshold: float = float(os.getenv("AUTO_REFUND_THRESHOLD", "250"))
    max_tool_retries: int = int(os.getenv("MAX_TOOL_RETRIES", "2"))
    retrieval_k: int = int(os.getenv("RETRIEVAL_K", "3"))
    model_name: str = os.getenv("MODEL_NAME", "supportops-deterministic-v1")
    input_token_cost_per_million: float = float(os.getenv("INPUT_TOKEN_COST_PER_MILLION", "0"))
    output_token_cost_per_million: float = float(os.getenv("OUTPUT_TOKEN_COST_PER_MILLION", "0"))
    allowed_origins: tuple[str, ...] = tuple(value.strip() for value in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if value.strip())


settings = Settings()
