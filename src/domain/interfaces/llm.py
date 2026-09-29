from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseLLMClient(ABC):
    """Abstract interface for Large Language Model providers."""

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate unstructured text completion."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> T:
        """Generate strictly typed structured output adhering to a Pydantic schema."""
        pass

    @abstractmethod
    async def stream_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream token chunks asynchronously for real-time UI responses."""
        pass
