from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes_ingestion import router as ingestion_router
from app.api.routes_chat import router as chat_router
from app.clients.weaviate_client import close_weaviate_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield 
    close_weaviate_service()

app = FastAPI(title="Hereshko", lifespan=lifespan)

app.include_router(ingestion_router)
app.include_router(chat_router)
