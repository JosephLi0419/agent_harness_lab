"""LLM provider factory for Azure OpenAI and Ollama."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

# Load .env from the project root on import.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

Provider = Literal["azure", "ollama"]

DEFAULT_MODELS: dict[Provider, str] = {
    "ollama": "qwen3.6:35b-a3b-q8_0",
}

CONFIG_PATH = Path.home() / ".agent-harness-lab" / "config.toml"


def load_config() -> dict:
    """Load config from ~/.agent-harness-lab/config.toml."""
    if not CONFIG_PATH.exists():
        return {}
    return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def get_default_provider() -> Provider:
    """Return the default provider from config, then env, then Ollama."""
    config = load_config()
    configured = config.get("llm", {}).get("provider")
    if configured:
        if configured not in ("azure", "ollama"):
            raise ValueError(
                f"Unknown provider in config: {configured!r}. Choose from: azure, ollama"
            )
        return configured

    if os.getenv("AZURE_OPENAI_API_KEY"):
        return "azure"
    return "ollama"


def create_llm(provider: Provider | None = None) -> BaseChatModel:
    """Create a chat model for Azure OpenAI or Ollama."""
    if provider is None:
        provider = get_default_provider()

    config = load_config()
    model_override = config.get("llm", {}).get("model") or None

    if provider == "azure":
        from langchain_openai import AzureChatOpenAI

        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        api_key = os.environ["AZURE_OPENAI_API_KEY"]
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        deployment = model_override or os.environ["AZURE_OPENAI_DEPLOYMENT"]

        return AzureChatOpenAI(
            azure_endpoint=endpoint,
            azure_deployment=deployment,
            api_version=api_version,
            api_key=api_key,
            streaming=True,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        model = model_override or os.getenv("OLLAMA_MODEL") or DEFAULT_MODELS["ollama"]
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        return ChatOllama(
            model=model,
            base_url=base_url,
        )

    raise ValueError(f"Unknown provider: {provider!r}. Choose from: azure, ollama")


def ensure_config_exists(provider: Provider | None = None) -> None:
    """Create default config file if it does not exist."""
    if CONFIG_PATH.exists():
        return

    if provider is None:
        provider = "azure" if os.getenv("AZURE_OPENAI_API_KEY") else "ollama"

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = f'[llm]\nprovider = "{provider}"\nmodel = ""\n'
    CONFIG_PATH.write_text(content, encoding="utf-8")
