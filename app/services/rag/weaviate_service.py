import weaviate
from weaviate.classes.init import Auth, AdditionalConfig, Timeout 
from weaviate.classes.data import DataObject
from weaviate.classes.query import Rerank, Filter
from app.config import settings
from app.core.chunking import Chunk
from typing import cast
from app.core.normalization import Document, SourceType

class WeaviateService:
    def __init__(self) -> None:
        auth = Auth.api_key(api_key=settings.weaviate_api_key)
        self.client = weaviate.connect_to_weaviate_cloud(
            cluster_url=settings.weaviate_url,
            auth_credentials=auth,
            additional_config=AdditionalConfig(
                timeout=Timeout(init=120,insert=120,query=30)
            ),
            headers={
                "X-JinaAI-Api-Key" : (
                    settings.jina_ai_api_key
                )
            }
        )

    def close(self) -> None:
        self.client.close()

    def create_collection(self) -> None:
        if self.client.collections.exists("Chunks"):
            print("Chunks collection already exists.")
            return

        self.client.collections.create(
            name = "Chunks",
            vector_config = weaviate.classes.config.Configure.Vectors.self_provided(),
            reranker_config = weaviate.classes.config.Configure.Reranker.jinaai(
                model="jina-reranker-v2-base-multilingual"
            ),
            properties=[
                weaviate.classes.config.Property(
                    name = "chunk_id",
                    data_type = weaviate.classes.config.DataType.TEXT
                ),
                weaviate.classes.config.Property(
                    name = "document_id",
                    data_type = weaviate.classes.config.DataType.TEXT
                ),
                weaviate.classes.config.Property(
                    name = "notebook_id",
                    data_type = weaviate.classes.config.DataType.TEXT
                ),
                weaviate.classes.config.Property(
                    name = "content",
                    data_type = weaviate.classes.config.DataType.TEXT
                ),
                weaviate.classes.config.Property(
                    name = "position_type",
                    data_type = weaviate.classes.config.DataType.TEXT
                ),
                weaviate.classes.config.Property(
                    name = "page_number",
                    data_type = weaviate.classes.config.DataType.INT
                ),
                weaviate.classes.config.Property(
                    name = "paragraph_index",
                    data_type = weaviate.classes.config.DataType.INT
                ),
                weaviate.classes.config.Property(
                    name = "slide_number",
                    data_type = weaviate.classes.config.DataType.INT
                ),   
                weaviate.classes.config.Property(
                    name = "timestamp_seconds",
                    data_type = weaviate.classes.config.DataType.NUMBER
                ),     
                weaviate.classes.config.Property(
                    name = "source_name",
                    data_type = weaviate.classes.config.DataType.TEXT
                ),  
                weaviate.classes.config.Property(
                    name = "metadata",
                    data_type = weaviate.classes.config.DataType.OBJECT
                )
            ]
        )
        print("Collection created successfully.")

    def insert_chunks(self, document: Document, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        collection = self.client.collections.get("Chunks")

        if len(chunks) != len(embeddings):
            raise ValueError("Chunk and Embedding Arrays must be of the same length.")

        data_sets = []

        for chunk,embedding in zip(chunks,embeddings):
            data_sets.append(
                DataObject(
                    properties={
                        "chunk_id" : chunk.chunk_id,
                        "document_id" : chunk.document_id,
                        "notebook_id" : chunk.notebook_id,
                        "content" : chunk.content,
                        "position_type" : str(chunk.position_type),
                        "page_number" : chunk.page_number,
                        "paragraph_index" : chunk.paragraph_index,
                        "slide_number" : chunk.slide_number,
                        "timestamp_seconds" : chunk.timestamp_seconds,
                        "source_name" : chunk.source_name,
                        "metadata" : chunk.metadata
                    },
                    vector=embedding
                )
            )

        response = collection.data.insert_many(data_sets)

        if response.has_errors:
            print(f"Error in the insertion of Data: {response.errors}")

        return len(response.uuids)

    def retrieve_chunks(self, query: str, embedding: list[float], limit: int, notebook_id: str) -> list[Chunk]:
        collection = self.client.collections.get("Chunks")

        response = collection.query.hybrid(
            query=query,
            alpha=0.75,
            limit=limit,
            vector=embedding,
            rerank=Rerank(
                prop="content",
                query=query
            ),
            filters=Filter.by_property("notebook_id").equal(notebook_id)
        )

        results = []

        for obj in response.objects:
            chunk = Chunk(
                chunk_id=cast(str,obj.properties.get("chunk_id")),
                document_id=cast(str,obj.properties.get("document_id")),
                notebook_id=cast(str,obj.properties.get("notebook_id")),
                content=cast(str,obj.properties.get("content")),
                position_type=cast(SourceType,obj.properties.get("position_type")),
                page_number=cast(int,obj.properties.get("page_number")),
                paragraph_index=cast(int,obj.properties.get("paragraph_index")),
                slide_number=cast(int,obj.properties.get("slide_number")),
                timestamp_seconds=cast(float,obj.properties.get("timestamp_seconds")),
                metadata=cast(dict,obj.properties.get("metadata") or {}),
                source_name=cast(str,obj.properties.get("source_name"))
            )
            results.append(chunk)

        return results

        