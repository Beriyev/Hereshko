from fastapi import APIRouter, UploadFile, Form, HTTPException
from app.schemas.ingestion import IngestResponse, WebsiteIngestResponse
from pathlib import Path
from app.services.ingestion.registry import get_ingester, extension_to_source_type_mapping
from app.services.ingestion.website_extractor import extract_scraped_website, extract_website
from app.core.exceptions import IngestionError
import tempfile
from app.services.ingestion.video_extractor import extract_youtube
import asyncio
from app.services.ingestion.indexing import index_document

router = APIRouter()

@router.post("/ingest/upload", response_model=IngestResponse)
async def upload_file(file: UploadFile, notebook_id: str = Form(...))-> IngestResponse:
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Filename is missing")
    original_filename = Path(file.filename.replace("\\", "/")).name
    path = Path(original_filename)
    extn = path.suffix.lower()

    source_type = extension_to_source_type_mapping.get(extn)
    if source_type is None:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension: {extn}")

    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=extn) as temp_file:
        temp_file.write(content)
        temp_file_path = Path(temp_file.name)
    try:
        ingester = get_ingester(source_type)
        document = ingester(temp_file_path, notebook_id)
        document.title = original_filename
        document.source_identifier = original_filename
        document.raw_metadata["original_filename"] = original_filename
        document = await asyncio.to_thread(index_document,document=document)
    except IngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        temp_file_path.unlink(missing_ok=True)

    return IngestResponse(document_id = document.document_id, status = "success")

@router.post("/ingest/website",response_model=WebsiteIngestResponse)
async def upload_website(url: str = Form(...), notebook_id: str = Form(...)) -> WebsiteIngestResponse:
    try:
        documents = await extract_website(url=url,notebook_id=notebook_id)
        document_ids = []
        for document in documents:
                document = await asyncio.to_thread(index_document,document=document)
                document_ids.append(document.document_id)
    except IngestionError as e:
        raise HTTPException(status_code=400,detail=str(e))

    return WebsiteIngestResponse(
        document_ids=document_ids,
        status="success"
    )


@router.post("/ingest/scrape", response_model=WebsiteIngestResponse)
async def scrape_website(url: str = Form(...), notebook_id: str = Form(...)) -> WebsiteIngestResponse:
    try:
        documents = await extract_scraped_website(url=url, notebook_id=notebook_id)
        document_ids = []
        for document in documents:
            document = await asyncio.to_thread(index_document, document=document)
            document_ids.append(document.document_id)
    except IngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return WebsiteIngestResponse(
        document_ids=document_ids,
        status="success",
    )

@router.post("/ingest/youtube",response_model=IngestResponse)
async def ingest_youtube(url: str = Form(...), notebook_id: str = Form(...)) -> IngestResponse:
    try:
        document = await asyncio.to_thread(
            extract_youtube,
            url=url,
            notebook_id=notebook_id,
        )
        document = await asyncio.to_thread(index_document,document=document)
    except IngestionError as e:
        raise HTTPException(status_code=400,detail=str(e))

    return IngestResponse(document_id=document.document_id,status="success")

    

    
