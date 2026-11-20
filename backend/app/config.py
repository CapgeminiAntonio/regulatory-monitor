from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ROOT / "backend" / ".env"), extra="ignore")

    # Which LLM backend to call:
    #   "anthropic" = Anthropic API directly (ANTHROPIC_API_KEY)
    #   "gateway"   = Capgemini AI Passport Gateway, OpenAI-compatible Responses API (GATEWAY_API_KEY)
    llm_provider: str = "anthropic"

    anthropic_model: str = "claude-opus-5-5"
    # Read from .env or the environment; if empty, the SDK falls back to its own credential chain.
    anthropic_api_key: str | None = None

    gateway_base_url: str = "https://openai.generative.engine.capgemini.com/v1"  # US; EU: openai.generative-eu...
    gateway_api_key: str | None = None
    gateway_model: str = "anthropic.claude-opus-5-5"
    gateway_timeout_s: float = 300.0
    client_name: str = "Northwind Wealth & Asset Management (fictional)"
    database_url: str = f"sqlite:///{(ROOT / 'backend' / 'regmon.db').as_posix()}"
    policies_dir: Path = ROOT / "data" / "policies"
    fixtures_dir: Path = ROOT / "data" / "fixtures"
    # DEMO_MODE=true: ingest from cached fixtures instead of live feeds (offline-safe demo).
    demo_mode: bool = False
    # Automatic scan: once a week at this day/hour (server local time), only while the backend is running.
    enable_scheduler: bool = True
    scan_day_of_week: str = "mon"
    scan_hour: int = 7
    max_items_per_source: int = 10
    # Only consider feed items newer than this many days.
    lookback_days: int = 150
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
