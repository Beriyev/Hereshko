from app.core.normalization import Document, SourceType
from typing import Callable
from pathlib import Path
from app.services.ingestion.pdf_extractor import extract_pdf
from app.services.ingestion.txt_extractor import extract_txt
from app.core.exceptions import UnsupportedSourceError

file_ingester_mapping: dict[SourceType, Callable[[Path,str], Document]] = {
    SourceType.TXT: extract_txt,
    SourceType.PDF: extract_pdf
}

extension_to_source_type_mapping: dict[str, SourceType] = {
    ".txt": SourceType.TXT,
    ".pdf": SourceType.PDF
}

def get_ingester(file_extension: SourceType) -> Callable[[Path, str], Document]:
    ingester = file_ingester_mapping.get(file_extension)
    if ingester is None:
        raise UnsupportedSourceError(f"No ingester found for file extension: {file_extension}")
    return ingester