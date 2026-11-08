import asyncio

from fastapi import APIRouter, HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import ValidationError

from app.core.exceptions import HereshkoError
from app.schemas.graphweaver import MindMap, MindMapRequest
from app.services.graphweaver.generator import generate_mindmap
from app.storage.database import get_notebook, list_sources

router = APIRouter()

@router.post("/notebooks/{notebook_id}/mindmap",response_model=MindMap)
async def create_mindmap(notebook_id: str, request: MindMapRequest) -> dict:
    notebook = get_notebook(notebook_id=notebook_id)

    if not notebook:
        raise HTTPException(404,"Notebook not found.")
    
    sources = list_sources(notebook_id=notebook_id)

    found = False

    for source in sources:
        if source.get("document_id") == request.document_id:
            found = True
            break

    if found == False:
        raise HTTPException(404,"Document not found in the notebook.")

    try:
        return await asyncio.to_thread(
            generate_mindmap,
            document_id=request.document_id
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=409,
            detail="This source has no saved extracted content. Upload the file again, or add the website/video again, then select the new source to generate its map.",
        ) from error
    except APIStatusError as error:
        messages = {
            400: "OpenRouter rejected the request. Check the configured model and document size.",
            401: "OpenRouter authentication failed. Check OPENROUTER_API_KEY on the backend.",
            402: "OpenRouter has insufficient credits. Check the account balance.",
            403: "OpenRouter access was denied. Check the API key and model access.",
            404: "The configured OpenRouter model is unavailable. Check OPENROUTER_STUDY_MODEL.",
            429: "OpenRouter's rate limit or quota was reached. Try again later.",
            503: "OpenRouter is temporarily unavailable. Try again in a moment.",
            504: "OpenRouter timed out. Please try again.",
        }
        raise HTTPException(
            status_code=error.status_code if error.status_code in (429, 503, 504) else 502,
            detail=messages.get(error.status_code, "OpenRouter could not generate the map. Please try again."),
        ) from error
    except APITimeoutError as error:
        raise HTTPException(status_code=504, detail="OpenRouter timed out. Please try again.") from error
    except APIConnectionError as error:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to OpenRouter. Check the backend's internet connection and try again.",
        ) from error
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail="The saved document or generated map has an invalid format. Re-upload the source or regenerate the map.",
        ) from error
    except HereshkoError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error
