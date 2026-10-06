import tempfile
import uuid
import sys
from datetime import datetime, timezone
from pathlib import Path
import paddle
import shutil
import subprocess
from app.core.exceptions import IngestionError
from paddleocr import PaddleOCR
from app.core.normalization import Document, SourceType

_ocr = None

def get_ocr():
    global _ocr

    if _ocr is None:
        if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count()>0:
            device = "gpu:0"
        else:
            device = "cpu"

        paddle.device.set_device(device)

        _ocr = PaddleOCR(
            lang="en",
            device=device,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )

    return _ocr

def convert_pptx_to_pdf(file_path: Path, output_pdf: Path) -> None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")

    if soffice is None and sys.platform == "win32":
        windows_paths = (
            Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
            Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        )
        soffice_path = next(
            (path for path in windows_paths if path.exists()),
            None,
        )
        soffice = str(soffice_path) if soffice_path else None

    if soffice is None:
        raise IngestionError("LibreOffice was not found. Install LibreOffice and add it to PATH.")
    output_pdf.parent.mkdir(parents=True,exist_ok=True)

    try:
        subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_pdf.parent),
                str(file_path)
            ],
            check=True,
            text=True,
            capture_output=True,
            timeout=120
        )
    except subprocess.TimeoutExpired as error:
        raise IngestionError("LibreOffice timed out while converting the PPTX.") from error
    except subprocess.CalledProcessError as error:
        raise IngestionError(f"LibreOffice failed to convert the PPTX: {error.stderr}") from error
    output_file = output_pdf.parent / f"{file_path.stem}.pdf"
    if not output_file.exists():
        raise IngestionError(
            "LibreOffice completed but did not create the PDF."
        )
    if output_file!=output_pdf:
        output_file.replace(output_pdf)

def extract_pptx(file_path: Path, notebook_id: str) -> Document:
    try:
        with tempfile.TemporaryDirectory(
            prefix="hereshko_pptx_"
        ) as temp_dir:
            pdf_path = Path(temp_dir) / f"{file_path.stem}.pdf"

            convert_pptx_to_pdf(file_path=file_path,output_pdf=pdf_path)

            ocr = get_ocr()
            ocr_results = ocr.predict(str(pdf_path))

            slide_texts = []
            boundaries = []
            offset = 0
            slide_count = 0
            start = 0
            end = 0

            for slide_number, slide_text in enumerate(ocr_results,start=1):
                slide_count+=1
                text = []
                for texts in slide_text["rec_texts"]:
                    if texts and texts.strip():
                        text.append(texts)

                text = "\n".join(text)

                if not text:
                    continue

                start = offset
                end = start+len(text)

                slide_texts.append(text)

                boundaries.append(
                    {
                        "slide_number" : slide_number,
                        "start" : start,
                        "end" : end
                    }
                )

                offset = end+1

        content = "\n".join(slide_texts)

        if not content.strip():
            raise IngestionError(
                "PaddleOCR found no text in the rendered PPTX"
            )

        return Document(
            document_id=str(uuid.uuid4()),
            notebook_id=notebook_id,
            content=content,
            source_type=SourceType.PPTX,
            source_identifier=file_path.name,
            title=file_path.stem,
            ingested_at=datetime.now(timezone.utc),
            raw_metadata={
                "original_filename": file_path.name,
                "file_size_bytes": file_path.stat().st_size,
                "slides_count": slide_count,
                "renderer": "libreoffice",
                "ocr_engine": "paddleocr",
                "boundaries": boundaries,
            },
        )

    except IngestionError:
        raise

    except Exception as e:
        raise IngestionError(
            f"Error: {e}" 
        ) from e
