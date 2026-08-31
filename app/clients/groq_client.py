from groq import Groq
from app.config import settings

groq_client = Groq(api_key=settings.groq_api_key)