from typing import Dict, Callable
from .openai_client import OpenAIClient
from .anthropic_client import AnthropicClient
from .LLMClient import LLMClient

class LLMProvider:
    def __init__(self, logger: Callable[[Dict[str, str]], None]):
        self.supported_models: Dict[str, str] = {
            "gpt-4o": "openai",
            "gpt-4o-mini": "openai",
            "o1-preview": "openai",
            "o1-mini": "openai",
            "gpt-4o-2024-08-06": "openai",
            "claude-3-5-sonnet-20240620": "anthropic"
        }
        self.logger = logger

    def get_client(self, model_name: str) -> LLMClient:
        provider = self.supported_models.get(model_name)
        if not provider:
            raise ValueError(f"Unsupported model: {model_name}")

        if provider == "openai":
            return OpenAIClient(self.logger)
        elif provider == "anthropic":
            return AnthropicClient(self.logger)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
