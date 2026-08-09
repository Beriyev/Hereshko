from fastapi import FastAPI
from app.api.routes_ingestion import router as ingestion_router

app = FastAPI(title="Hereshko")

app.include_router(ingestion_router)