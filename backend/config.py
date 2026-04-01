from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    uploads_dir: Path = Path(__file__).resolve().parent.parent / "uploads"
    exports_dir: Path = Path(__file__).resolve().parent.parent / "exports"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:3000"

    # LLM
    default_model: str = "gpt-4o"
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # LLM Provider: "direct" (use API keys) or "copilot_proxy" (use vscode-lm-proxy)
    llm_provider: str = "direct"
    copilot_proxy_url: str = "http://localhost:4000/v1"
    copilot_proxy_model: str = ""  # Override model name sent to proxy (empty = use default)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

# Ensure runtime directories exist
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir.mkdir(parents=True, exist_ok=True)

# Propagate API keys to environment so LiteLLM can find them
import os

if settings.openai_api_key:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
if settings.anthropic_api_key:
    os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)

# Propagate LLM provider settings so llm_client.py can read them
os.environ.setdefault("LLM_PROVIDER", settings.llm_provider)
if settings.copilot_proxy_url:
    os.environ.setdefault("COPILOT_PROXY_URL", settings.copilot_proxy_url)
if settings.copilot_proxy_model:
    os.environ.setdefault("COPILOT_PROXY_MODEL", settings.copilot_proxy_model)
