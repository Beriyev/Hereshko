import asyncio
import traceback

from fastapi import HTTPException

from app.core.chat import ChatMessage
from app.core.exceptions import ChatError, HereshkoError, RetrievalError
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag.embeddings import embed_queries
from app.services.rag.llm import generate_answer
from app.services.rag.weaviate_service import WeaviateService
from app.services.rag.web_agent import gather_web_sources
from app.storage.database import get_notebook


async def answer_l1(
    request: ChatRequest,
    weaviate_service: WeaviateService,
    history: list[ChatMessage] | None = None,
) -> ChatResponse:
    try:
        embeddings = await asyncio.to_thread(embed_queries, request.query)
    except HereshkoError as error:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {error}") from error

    notebook = get_notebook(request.notebook_id)
    source_count = notebook["source_count"] if notebook else 0
    retrieval_limit = 24 if source_count > 5 else 20

    try:
        retrieved_chunks = await asyncio.to_thread(
            weaviate_service.retrieve_chunks,
            query=request.query,
            embedding=embeddings,
            limit=10,
            candidate_limit=retrieval_limit,
            notebook_id=request.notebook_id,
        )
    except RetrievalError as error:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {error}") from error

    web_chunks = []
    if request.web_search:
        try:
            web_chunks = await gather_web_sources(
                query=request.query,
                context_chunks=retrieved_chunks,
                notebook_id=request.notebook_id,
                force_web=request.web_search,
            )
        except Exception as error:
            print(f"MCP web tools unavailable: {error}")
            traceback.print_exception(type(error), error, error.__traceback__)
            if request.web_search:
                raise HTTPException(
                    status_code=503,
                    detail=f"Web Search mode requires MCP, but MCP is unavailable: {error}",
                ) from error

    try:
        return await asyncio.to_thread(
            generate_answer,
            chat_request=request,
            retrieved_chunks=retrieved_chunks + web_chunks,
            history=history,
        )
    except ChatError as error:
        raise HTTPException(status_code=500, detail=f"Chat failed: {error}") from error
