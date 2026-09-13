from app.services.rag.weaviate_service import WeaviateService

service: WeaviateService | None = None

def get_weaviate_service() -> WeaviateService:
    global service 
    if service is None:
        service = WeaviateService()
    return service

def close_weaviate_service() -> None:
    global service
    if service is not None:
        service.close()
        service = None


