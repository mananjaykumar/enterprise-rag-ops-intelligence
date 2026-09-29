from abc import ABC, abstractmethod


class BaseEmbeddingClient(ABC):
    """Abstract interface for text embedding models."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the active embedding model (e.g., 'gemini-embedding-001')."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the vector space (e.g., 768)."""
        pass

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Generate an embedding vector for a retrieval query."""
        pass

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of document chunks."""
        pass
