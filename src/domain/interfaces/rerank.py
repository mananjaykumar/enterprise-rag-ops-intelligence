from abc import ABC, abstractmethod
from typing import Any


class BaseRerankClient(ABC):
    """Abstract interface for cross-encoder reranking operations."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        passages: list[dict[str, Any]],
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        """Reranks candidate passages against the query.

        Args:
            query: The user search or question string.
            passages: List of dicts, each containing at least 'id' and 'text'/'content'.
            top_n: Maximum number of highest-scoring passages to return.

        Returns:
            List of passages sorted in descending order of relevance score,
            each containing a 'score' float field.
        """
        pass
