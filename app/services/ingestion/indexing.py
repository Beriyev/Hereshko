from app.clients.weaviate_client import get_weaviate_service
from app.core.exceptions import IngestionError
from app.core.normalization import Document
from app.services.rag.chunker import chunker
from app.services.rag.embeddings import embed_texts
from app.storage.database import save_source

def index_document(document: Document) -> Document:
    try:
        chunks = chunker(document=document)

        if not chunks:
            raise IngestionError("No chunks could be created from the document.")

        embedding_texts = [
            f"""
            Source Title: {document.title}
            Source Type: {document.source_type}

            Content: {chunk.content}
            """
            for chunk in chunks
        ]

        embeddings = embed_texts(embedding_texts)

        get_weaviate_service().insert_chunks(
            document=document,
            chunks=chunks,
            embeddings=embeddings
        )

        save_source(document=document)
        return document
    except IngestionError:
        raise
    except Exception as e:
        raise IngestionError(
            f"Failed to index document: {e}"
        ) from e