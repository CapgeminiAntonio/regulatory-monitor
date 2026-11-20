import os
import tempfile
from pathlib import Path

# Point the app at a throwaway database and offline fixtures before any app import.
_tmp = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["DEMO_MODE"] = "true"
os.environ["ENABLE_SCHEDULER"] = "false"
# Tests must not depend on (or send) whatever key/provider is in the developer's .env.
os.environ["LLM_PROVIDER"] = "anthropic"
os.environ["GATEWAY_API_KEY"] = "test-key"
os.environ["ANTHROPIC_MODEL"] = "claude-opus-5-5"
os.environ["GATEWAY_MODEL"] = "anthropic.claude-opus-5-5"
os.environ.pop("GATEWAY_BASE_URL", None)
