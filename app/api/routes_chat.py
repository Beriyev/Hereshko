from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag.embeddings import embed_texts
from app.services.rag.weaviate_service import WeaviateService
from app.services.rag.memory import ConversationStore
from app.services.rag.llm import generate_answer
from app.core.exceptions import ChatError, RetrievalError, HereshkoError

router = APIRouter()

weaviate_service = WeaviateService()

conversation_store = ConversationStore()

@router.post("/chat",response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:

    try:
        embeddings = embed_texts([request.query])[0]
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
        generated_answer = generate_answer(chat_request=request,retrieved_chunks=retrieved_chunks,history=history)
    except ChatError as e:
        raise HTTPException(status_code=500,detail=f"Chat failed: {e}")

    if request.session_id:
        conversation_store.add_turn(session_id=request.session_id,user_msg=request.query,assistant_msg=generated_answer.answer)

    return generated_answer

