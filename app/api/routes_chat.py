from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import asyncio
import json
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag.l1 import answer_l1
from app.services.rag.l2 import l2_orchestrator
from app.clients.weaviate_client import get_weaviate_service
from app.core.chat import ChatMessage, ChatRole
from app.services.rag.weaviate_service import WeaviateService
from app.storage.database import get_history, save_history

router = APIRouter()

@router.post("/chat/l1",response_model=ChatResponse)
async def chat_l1(
    request: ChatRequest,
    weaviate_service: WeaviateService = Depends(get_weaviate_service)
):
    history = (
        await asyncio.to_thread(get_history, request.notebook_id, request.session_id)
        if request.session_id
        else None
    )

    response = await answer_l1(
        request=request,
        weaviate_service=weaviate_service,
        history=history,
    )

    if request.session_id:
        await asyncio.to_thread(
            save_history,
            request.notebook_id,
            request.session_id,
            ChatMessage(role=ChatRole.USER, content=request.query),
        )
        await asyncio.to_thread(
            save_history,
            request.notebook_id,
            request.session_id,
            ChatMessage(role=ChatRole.ASSISTANT, content=response.answer),
        )

    return response

@router.post("/chat/l2", response_class=StreamingResponse)
async def chat_l2(
    request: ChatRequest,
    weaviate_service: WeaviateService = Depends(get_weaviate_service)
):
    history = (
        await asyncio.to_thread(get_history, request.notebook_id, request.session_id)
        if request.session_id
        else None
    )

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
                    await asyncio.to_thread(
                        save_history,
                        request.notebook_id,
                        request.session_id,
                        ChatMessage(role=ChatRole.USER, content=request.query),
                    )
                    await asyncio.to_thread(
                        save_history,
                        request.notebook_id,
                        request.session_id,
                        ChatMessage(role=ChatRole.ASSISTANT, content=response.answer),
                    )

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
    

    
