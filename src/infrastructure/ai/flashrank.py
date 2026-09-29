import asyncio
from typing import Any

from flashrank import Ranker, RerankRequest

from src.domain.interfaces.rerank import BaseRerankClient


class FlashRankClient(BaseRerankClient):
    """Lightweight, local ONNX cross-encoder reranker.

    Runs on CPU with zero GPU requirements, <15ms latency, and no external API dependencies.
    """

    def __init__(self, model_name: str = "ms-marco-TinyBERT-L-2-v2") -> None:
        self.model_name = model_name
        self.ranker = Ranker(model_name=model_name)

    async def rerank(
        self,
        query: str,
        passages: list[dict[str, Any]],
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        if not passages:
            return []

        # Standardize passages to have 'id' and 'text' expected by FlashRank
        formatted_passages: list[dict[str, Any]] = []
        for p in passages:
            text_val = p.get("text") or p.get("content") or ""
            formatted_passages.append(
                {
                    **p,
                    "id": str(p.get("id", "")),
                    "text": text_val,
                }
            )

        req = RerankRequest(query=query, passages=formatted_passages)

        # Offload synchronous ONNX model inference to a thread pool executor
        loop = asyncio.get_running_loop()
        reranked = await loop.run_in_executor(None, self.ranker.rerank, req)

        # Ensure scores are native Python floats and slice top_n
        results: list[dict[str, Any]] = []
        for item in reranked[:top_n]:
            item_dict = dict(item)
            item_dict["score"] = float(item_dict.get("score", 0.0))
            results.append(item_dict)

        return results
