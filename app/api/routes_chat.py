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

@router.post("/chat/l1",response_model=ChatResponse)
async def chat_l1(
    request: ChatRequest,
    weaviate_service: WeaviateService = Depends(get_weaviate_service)
):
    if request.session_id:
        history = conversation_store.get_recent(session_id=request.session_id,n=8)
    else:
        history = None

    response = await answer_l1(request=request,weaviate_service=weaviate_service,history=history)

    if request.session_id:
        conversation_store.get_or_create(session_id=request.session_id,notebook_id=request.notebook_id)
        conversation_store.add_turn(session_id=request.session_id,user_msg=request.query,assistant_msg=response.answer)

    return response

@router.post("/chat/l2", response_class=StreamingResponse)
async def chat_l2(
    request: ChatRequest,
    weaviate_service: WeaviateService = Depends(get_weaviate_service)
):
    if request.session_id:
        history = conversation_store.get_recent(session_id=request.session_id,n=8)
    else:
        history = None

    async def stream():
        queue = asyncio.Queue()

        async def run_l2():
            try:
                response = await l2_orchestrator(
                    request=request,
                    weaviate_service=weaviate_service,
                    history=history,
                    on_progress=queue.put
                )
                if request.session_id:
                    conversation_store.get_or_create(session_id=request.session_id,notebook_id=request.notebook_id)
                    conversation_store.add_turn(session_id=request.session_id,user_msg=request.query,assistant_msg=response.answer)
                await queue.put({
                    "type" : "done",
                    **response.model_dump()
                })
            except Exception as e:
                await queue.put({
                    "type" : "error",
                    "message" : str(getattr(e,"detail",e))
                })
        task = asyncio.create_task(run_l2())
        try:
            while True:
                event = await queue.get()
                yield json.dumps(event) + "\n"

                if event["type"] in {"done","error"}:
                    break
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task,return_exceptions=True)

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache"}
    )
    

    
