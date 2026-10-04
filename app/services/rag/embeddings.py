from typing import Any

from sentence_transformers import SentenceTransformer

from app.config import settings


_embedding_model: SentenceTransformer | None = None
_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            settings.embedding_model,
            device=settings.embedding_device,
        )

    return _embedding_model


def _encode(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    model = get_embedding_model()
    vectors: Any = model.encode(
        texts,
        batch_size=settings.embedding_batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    return _encode(texts)


def embed_queries(text: str) -> list[float]:
    return _encode([f"{_QUERY_INSTRUCTION}{text}"])[0]
