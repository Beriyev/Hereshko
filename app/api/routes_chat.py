from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import asyncio
import json
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag.l1 import answer_l1
from app.services.rag.l2 import l2_orchestrator
from app.clients.weaviate_client import get_weaviate_service
from app.services.rag.memory import ConversationStore
from app.services.rag.weaviate_service import WeaviateService

router = APIRouter()

conversation_store = ConversationStore()

@router.post("/chat",response_model=ChatResponse)
async def chat(request: ChatRequest, weaviate_service: WeaviateService = Depends(get_weaviate_service)) -> ChatResponse:

    if request.session_id:
        history = conversation_store.get_recent(session_id=request.session_id,n=16)
    else:
        history = None

    if request.mode == "l2":
        generated_answer = await l2_orchestrator(request, weaviate_service, history=history)
    else:
        generated_answer = await answer_l1(request, weaviate_service, history=history)

    if request.session_id:
        conversation_store.get_or_create(session_id=request.session_id,notebook_id=request.notebook_id)

    if request.session_id:
        conversation_store.add_turn(session_id=request.session_id,user_msg=request.query,assistant_msg=generated_answer.answer)

    return generated_answer


@router.post("/chat/l2")
async def chat_l2(
    request: ChatRequest,
    weaviate_service: WeaviateService = Depends(get_weaviate_service),
) -> StreamingResponse:
    history = conversation_store.get_recent(request.session_id, 16) if request.session_id else None

    async def events():
        queue = asyncio.Queue()

        async def run():
            try:
                response = await l2_orchestrator(
                    request, weaviate_service, history=history, on_progress=queue.put
                )
                if request.session_id:
                    conversation_store.get_or_create(request.session_id, request.notebook_id)
                    conversation_store.add_turn(request.session_id, request.query, response.answer)
                await queue.put({"type": "done", **response.model_dump()})
            except Exception as error:
                await queue.put({"type": "error", "message": str(getattr(error, "detail", error))})

        task = asyncio.create_task(run())
        try:
            while True:
                event = await queue.get()
                yield json.dumps(event) + "\n"
                if event["type"] in {"done", "error"}:
                    break
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(
        events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache"}
    )

