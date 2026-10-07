import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.core.exceptions import ChatError, IngestionError
from app.schemas.notebook import (
    NotebookTitleUpdate,
    NotebookResponse,
    SourceListResponse,
    SummaryResponse,
)
from app.services.rag.llm import generate_preview_summary
from app.storage.database import delete_all_sources, delete_source, get_notebook, list_sources, update_notebook_title, notebook_summaries
from app.clients.weaviate_client import get_weaviate_service
from app.services.rag.weaviate_service import WeaviateService
from app.schemas.notebook import SourceResponse

router = APIRouter(
    prefix="/notebooks",
    tags=["notebooks"]
)

@router.get("/{notebook_id}",response_model=NotebookResponse)
def get_notebook_details(notebook_id: str) -> NotebookResponse:
    notebook = get_notebook(notebook_id=notebook_id)

    if notebook is None:
        raise HTTPException(
            status_code=404,
            detail="Notebook not found."
        )

    return NotebookResponse(
        notebook_id=notebook_id,
        title = notebook["title"],
        created_at=notebook["created_at"],
        updated_at=notebook["updated_at"],
        source_count=notebook["source_count"]
    )


@router.patch("/{notebook_id}", response_model=NotebookResponse)
def rename_notebook(notebook_id: str, payload: NotebookTitleUpdate) -> NotebookResponse:
    title = payload.title.strip()

    if not title:
        raise HTTPException(status_code=400, detail="Notebook name cannot be empty.")
    if len(title) > 120:
        raise HTTPException(status_code=400, detail="Notebook name must be 120 characters or fewer.")

    notebook = get_notebook(notebook_id=notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")

    updated = update_notebook_title(notebook_id, title)
    if updated is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")

    return NotebookResponse(
        notebook_id=notebook_id,
        title=updated["title"],
        created_at=updated["created_at"],
        updated_at=updated["updated_at"],
        source_count=updated["source_count"],
    )

@router.get("/{notebook_id}/sources",response_model=SourceListResponse)
def get_notebook_sources(notebook_id: str) -> SourceListResponse:
    notebook = get_notebook(notebook_id=notebook_id)

    if notebook is None:
        raise HTTPException(
            status_code=404,
            detail="Notebook not found."
        )

    sources = list_sources(notebook_id=notebook_id)

    sources_list: list[SourceResponse] = []

    for source in sources:
        sources_list.append(
            SourceResponse(
                document_id=source["document_id"],
                notebook_id=source["notebook_id"],
                title=source["title"],
                source_type=source["source_type"],
                source_identifier=source["source_identifier"],
                ingested_at=source["ingested_at"],
                metadata=source["metadata"]
            )
        )

    return SourceListResponse(
        sources=sources_list
    )


@router.delete("/{notebook_id}/sources/{document_id}")
def remove_notebook_source(
    notebook_id: str,
    document_id: str,
    weaviate_service: WeaviateService = Depends(get_weaviate_service),
) -> dict[str, str]:
    notebook = get_notebook(notebook_id=notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")

    source = next(
        (item for item in list_sources(notebook_id=notebook_id) if item["document_id"] == document_id),
        None,
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")

    try:
        weaviate_service.delete_document_chunks(document_id=document_id)
    except IngestionError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Source removal failed in Weaviate: {error}",
        ) from error

    delete_source(document_id=document_id, notebook_id=notebook_id)

    return {"status": "deleted", "document_id": document_id}


@router.delete("/{notebook_id}/sources")
def remove_all_notebook_sources(
    notebook_id: str,
    weaviate_service: WeaviateService = Depends(get_weaviate_service),
) -> dict[str, int | str]:
    notebook = get_notebook(notebook_id=notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")

    try:
        weaviate_service.delete_notebook_chunks(notebook_id=notebook_id)
    except IngestionError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Source removal failed in Weaviate: {error}",
        ) from error

    deleted_count = delete_all_sources(notebook_id=notebook_id)
    return {"status": "deleted", "deleted_count": deleted_count}


@router.post(
    "/{notebook_id}/summary",
    response_model=SummaryResponse,
)
async def generate_notebook_summary(notebook_id: str) -> SummaryResponse:
    notebook = get_notebook(notebook_id=notebook_id)

    if notebook is None:
        raise HTTPException(
            status_code=404,
            detail="Notebook not found.",
        )

    if notebook["source_count"] == 0:
        raise HTTPException(
            status_code=400,
            detail="Notebook has no indexed sources.",
        )

    sources = list_sources(notebook_id=notebook_id)
    source_previews = [
        {
            "title": source["title"],
            "preview_text": source["metadata"].get("preview_text", ""),
        }
        for source in sources
    ]

    try:
        summary = await asyncio.to_thread(
            generate_preview_summary,
            source_previews,
        )
    except ChatError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Summary generation failed: {error}",
        ) from error

    notebook_summaries[notebook_id] = summary.summary

    return SummaryResponse(
        title=summary.title,
        summary=summary.summary,
        source_count=notebook["source_count"],
        updated_at=notebook["updated_at"],
    )
