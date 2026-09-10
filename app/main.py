from fastapi import FastAPI
from app.api.routes_ingestion import router as ingestion_router
from app.api.routes_chat import router as chat_router

app = FastAPI(title="Hereshko")

app.include_router(ingestion_router)
app.include_router(chat_router)
