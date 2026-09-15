from groq import AsyncGroq, Groq
from app.config import settings

groq_client = Groq(api_key=settings.groq_api_key)

async_groq_client = AsyncGroq(api_key=settings.groq_api_key)