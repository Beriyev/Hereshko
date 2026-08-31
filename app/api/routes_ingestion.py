from fastapi import APIRouter, UploadFile, Form, HTTPException
from app.schemas.ingestion import IngestResponse, WebsiteIngestResponse
from pathlib import Path
from app.services.ingestion.registry import file_ingester_mapping, get_ingester, extension_to_source_type_mapping
from app.services.ingestion.website_extractor import extract_website
from app.core.exceptions import IngestionError, UnsupportedSourceError
import tempfile
from app.services.ingestion.video_extractor import extract_youtube

router = APIRouter()

@router.post("/ingest/upload", response_model=IngestResponse)
async def upload_file(file: UploadFile, notebook_id: str = Form(...))-> IngestResponse:
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Filename is missing")
    path = Path(file.filename)
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
    except IngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        temp_file_path.unlink(missing_ok=True)

    return IngestResponse(document_id = document.document_id, status = "success")

@router.post("/ingest/website",response_model=WebsiteIngestResponse)
async def upload_website(url: str = Form(...), notebook_id: str = Form(...)) -> WebsiteIngestResponse:
    try:
        documents = await extract_website(url=url,notebook_id=notebook_id)
    except IngestionError as e:
        raise HTTPException(status_code=400,detail=str(e))
    
    document_ids = []

    for document in documents:
        document_ids.append(document.document_id)

    return WebsiteIngestResponse(
        document_ids=document_ids,
        status="success"
    )

@router.post("/ingest/youtube",response_model=IngestResponse)
def ingest_youtube(url: str = Form(...), notebook_id: str = Form(...)) -> IngestResponse:
    try:
        document = extract_youtube(url=url, notebook_id=notebook_id)
    except IngestionError as e:
        raise HTTPException(status_code=400,detail=str(e))

    return IngestResponse(document_id=document.document_id,status="success")

    

    
