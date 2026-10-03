from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes_ingestion import router as ingestion_router
from app.api.routes_chat import router as chat_router
from app.clients.weaviate_client import close_weaviate_service
from app.storage.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield 
    close_weaviate_service()

app = FastAPI(title="Hereshko", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion_router)
app.include_router(chat_router)
