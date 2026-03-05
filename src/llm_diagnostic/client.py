"""
Flexible LLM Client
Supports multiple LLM providers with unified interface
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List
import os

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers"""

    OPENAI = "openai"
    GROQ = "groq"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    HUGGINGFACE = "huggingface"
    TOGETHER = "together"


class BaseLLMClient(ABC):
    """Base class for LLM clients"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LLM client

        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.timeout = config.get("timeout", 30)
        self.retry_times = config.get("retry_times", 3)
        self.retry_delay = config.get("retry_delay", 1)
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 2000)
        logger.info(f"[LLM Client] Initialized with timeout={self.timeout}s, retry_times={self.retry_times}, temperature={self.temperature}")

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate response from LLM

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            Generated text response
        """
        pass

    async def generate_with_retry(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate with retry mechanism"""
        last_error = None
        for attempt in range(self.retry_times):
            try:
                return await self.generate(prompt, system_prompt)
            except Exception as e:
                last_error = e
                logger.warning(f"LLM call failed (attempt {attempt + 1}/{self.retry_times}): {e}")
                if attempt < self.retry_times - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise last_error
        raise last_error


class OpenAIClient(BaseLLMClient):
    """OpenAI API client (also supports OpenAI-compatible endpoints via base_url, e.g. cursor-api)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            import openai

            api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
            base_url = config.get("base_url")
            if base_url:
                self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url.rstrip("/") + "/v1")
            else:
                self.client = openai.AsyncOpenAI(api_key=api_key)
            self.model = config.get("model", "gpt-4")
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
        )

        return response.choices[0].message.content


class GroqClient(BaseLLMClient):
    """Groq API client (free, fast)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            from groq import AsyncGroq

            # Resolve environment variable references in api_key
            api_key = config.get("api_key", "")
            if api_key and api_key.startswith("${") and api_key.endswith("}"):
                env_var_name = api_key[2:-1]
                api_key = os.getenv(env_var_name, "")
            
            self.client = AsyncGroq(api_key=api_key or os.getenv("GROQ_API_KEY"))
            self.model = config.get("model", "llama-3.1-8b-instant")
        except ImportError:
            raise ImportError("groq package not installed. Install with: pip install groq")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        return response.choices[0].message.content


class OllamaClient(BaseLLMClient):
    """Ollama local LLM client"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            import aiohttp

            self.session = aiohttp.ClientSession()
            self.base_url = config.get("ollama_url", "http://localhost:11434")
            self.model = config.get("ollama_model", "llama2")
        except ImportError:
            raise ImportError("aiohttp package not installed. Install with: pip install aiohttp")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        import aiohttp

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        async with self.session.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            },
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        ) as response:
            result = await response.json()
            return result.get("response", "")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API client"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            import anthropic

            self.client = anthropic.AsyncAnthropic(api_key=config.get("api_key") or os.getenv("ANTHROPIC_API_KEY"))
            self.model = config.get("model", "claude-3-opus-20240229")
        except ImportError:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = [{"role": "user", "content": prompt}]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=messages,
            timeout=self.timeout,
        )

        return response.content[0].text


class GoogleClient(BaseLLMClient):
    """Google Gemini API client"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            import google.generativeai as genai

            api_key = config.get("api_key") or os.getenv("GOOGLE_API_KEY")
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(config.get("model", "gemini-pro"))
        except ImportError:
            raise ImportError("google-generativeai package not installed. Install with: pip install google-generativeai")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        response = await self.model.generate_content_async(full_prompt)
        return response.text


class LLMClient:
    """
    Flexible LLM client factory
    Supports multiple providers with unified interface
    """

    _client_classes = {
        LLMProvider.OPENAI: OpenAIClient,
        LLMProvider.GROQ: GroqClient,
        LLMProvider.OLLAMA: OllamaClient,
        LLMProvider.ANTHROPIC: AnthropicClient,
        LLMProvider.GOOGLE: GoogleClient,
    }

    def __init__(self, provider: str, config: Dict[str, Any]):
        """
        Initialize LLM client

        Args:
            provider: Provider name (openai, groq, ollama, etc.)
            config: Provider-specific configuration
        """
        self.provider = LLMProvider(provider.lower())
        self.config = config

        if self.provider not in self._client_classes:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        client_class = self._client_classes[self.provider]
        self._client = client_class(config)

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate response from LLM

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            Generated text response
        """
        return await self._client.generate_with_retry(prompt, system_prompt)

    @classmethod
    def register_provider(cls, provider: str, client_class: type):
        """
        Register custom LLM provider

        Args:
            provider: Provider name
            client_class: Client class (must inherit from BaseLLMClient)
        """
        cls._client_classes[LLMProvider(provider.lower())] = client_class
        logger.info(f"Registered custom LLM provider: {provider}")

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "LLMClient":
        """
        Create LLM client from configuration

        Args:
            config: LLM configuration dict (from app.yaml)

        Returns:
            LLMClient instance
        """
        provider = config.get("provider", "groq")
        return cls(provider, config)

