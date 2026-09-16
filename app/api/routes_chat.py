from fastapi import APIRouter, HTTPException, Depends
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag.embeddings import embed_queries
from app.clients.weaviate_client import get_weaviate_service
from app.services.rag.memory import ConversationStore
from app.services.rag.weaviate_service import WeaviateService
from app.services.rag.llm import generate_answer
from app.core.exceptions import ChatError, RetrievalError, HereshkoError
import asyncio
from app.services.rag.web_agent import gather_web_sources

router = APIRouter()

conversation_store = ConversationStore()

@router.post("/chat",response_model=ChatResponse)
async def chat(request: ChatRequest, weaviate_service: WeaviateService = Depends(get_weaviate_service)) -> ChatResponse:

    try:
        embeddings = embed_queries(request.query)
    except HereshkoError as e:
        raise HTTPException(status_code=500,detail=f"Embedding failed: {e}")

    try:
        retrieved_chunks = weaviate_service.retrieve_chunks(
            query=request.query,
            embedding=embeddings,
            limit=8,
            notebook_id=request.notebook_id
        )
    except RetrievalError as e:
        raise HTTPException(status_code=500,detail=f"Retrieval failed: {e}")

    if request.session_id:
        history = conversation_store.get_recent(session_id=request.session_id,n=8)
    else:
        history = None

    try:
        web_chunks = await gather_web_sources(query=request.query,context_chunks=retrieved_chunks,notebook_id=request.notebook_id)
    except Exception:
        web_chunks = []
    all_chunks = retrieved_chunks+web_chunks

    try:
        generated_answer = await asyncio.to_thread(generate_answer,chat_request=request,retrieved_chunks=all_chunks,history=history)
    except ChatError as e:
        raise HTTPException(status_code=500,detail=f"Chat failed: {e}")

    if request.session_id:
        conversation_store.get_or_create(session_id=request.session_id,notebook_id=request.notebook_id)

    if request.session_id:
        conversation_store.add_turn(session_id=request.session_id,user_msg=request.query,assistant_msg=generated_answer.answer)

    return generated_answer

