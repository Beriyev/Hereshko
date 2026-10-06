from app.core.normalization import Document, SourceType
from typing import Callable
from pathlib import Path
from app.services.ingestion.pdf_extractor import extract_pdf
from app.services.ingestion.txt_extractor import extract_txt
from app.services.ingestion.docx_extractor import extract_docx
from app.core.exceptions import IngestionError, UnsupportedSourceError


def extract_pptx_lazy(file_path: Path, notebook_id: str):
    try:
        from app.services.ingestion.pptx_extractor import extract_pptx
    except ModuleNotFoundError as error:
        if error.name in {"paddle", "paddleocr"}:
            raise IngestionError(
                "PPTX ingestion requires LibreOffice and PaddleOCR dependencies."
            ) from error
        raise

    return extract_pptx(file_path, notebook_id)

file_ingester_mapping: dict[SourceType, Callable[[Path,str], Document]] = {
    SourceType.TXT: extract_txt,
    SourceType.PDF: extract_pdf,
    SourceType.DOCX: extract_docx,
    SourceType.PPTX: extract_pptx_lazy
}

extension_to_source_type_mapping: dict[str, SourceType] = {
    ".txt": SourceType.TXT,
    ".pdf": SourceType.PDF,
    ".docx": SourceType.DOCX,
    ".pptx": SourceType.PPTX
}

def get_ingester(source_type: SourceType) -> Callable[[Path, str], Document]:
    ingester = file_ingester_mapping.get(source_type)
    if ingester is None:
        raise UnsupportedSourceError(f"No ingester found for source type: {source_type}")
    return ingester
