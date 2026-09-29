from google import genai
from google.genai import types

from src.core.config import get_settings
from src.domain.interfaces.embedding import BaseEmbeddingClient

settings = get_settings()


class GeminiEmbeddingClient(BaseEmbeddingClient):
    """Adapter for Google Gemini text embedding models implementing BaseEmbeddingClient."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        dimension: int | None = None,
    ) -> None:
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._model_name = model_name or settings.ACTIVE_EMBEDDING_MODEL
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        self.client = genai.Client(api_key=self._api_key)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_query(self, text: str) -> list[float]:
        """Generates embedding for a user search query (768 dimensions)."""
        response = self.client.models.embed_content(
            model=self._model_name,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=self._dimension,
                task_type="RETRIEVAL_QUERY",
            ),
        )
        # Extract the vector values from the first embedding object
        return list(response.embeddings[0].values)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a batch of document chunks in chunks of 50."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        batch_size = 50  # Prevent hitting Gemini single-request payload limits

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.models.embed_content(
                model=self._model_name,
                contents=batch,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimension,
                    task_type="RETRIEVAL_DOCUMENT",
                ),
            )
            for emb in response.embeddings:
                all_embeddings.append(list(emb.values))

        return all_embeddings
