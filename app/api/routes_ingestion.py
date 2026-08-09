from fastapi import APIRouter, UploadFile, Form, HTTPException
from app.schemas.ingestion import IngestResponse
from pathlib import Path
from app.services.ingestion.registry import file_ingester_mapping, get_ingester, extension_to_source_type_mapping
from app.core.exceptions import IngestionError, UnsupportedSourceError
import tempfile

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

    

    
