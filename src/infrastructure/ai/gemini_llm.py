from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from src.core.config import get_settings
from src.domain.interfaces.llm import BaseLLMClient

T = TypeVar("T", bound=BaseModel)
settings = get_settings()


class GeminiLLMClient(BaseLLMClient):
    """Production Large Language Model client adapter using the Google GenAI SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.ACTIVE_LLM_MODEL
        self.client = genai.Client(api_key=self.api_key)

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Generates raw text completion from Gemini."""
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction,
            max_output_tokens=max_tokens,
        )
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        return response.text or ""

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> T:
        """Generates strictly typed structured output adhering to a Pydantic schema."""
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        return response_schema.model_validate_json(response.text or "{}")

    async def stream_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Streams token chunks asynchronously for real-time streaming UI responses."""
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction,
        )
        response_stream = await self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text
