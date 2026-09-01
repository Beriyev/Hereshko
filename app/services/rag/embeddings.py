from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import settings

embeddings_model = GoogleGenerativeAIEmbeddings(model=settings.gemini_embed_model, api_key=settings.gemini_api_key)

def embed_texts(text: list[str]) -> list[list[float]]:
    return embeddings_model.embed_documents(text)