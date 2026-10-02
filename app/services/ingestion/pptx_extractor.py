import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
import paddle

import pythoncom
import win32com.client
from paddleocr import PaddleOCR

from app.core.exceptions import IngestionError
from app.core.normalization import Document, SourceType

_ocr = None

def get_ocr():
    global _ocr

    if _ocr is None:
        if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count()>0:
            paddle.device.set_device("gpu:0")
        else:
            paddle.device.set_device("cpu")

        _ocr = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False
        )

    return _ocr

def convert_pptx_to_pdf(file_path: Path, output_pdf: Path) -> None:
    powerpoint = None
    presentation = None

    pythoncom.CoInitialize()

    try:
        powerpoint = win32com.client.DispatchEx("PowerPoint.Application")
        powerpoint.Visible = True
        powerpoint.DisplayAlerts = 1

        presentation = powerpoint.Presentations.Open(
            str(file_path),
            ReadOnly = True,
            WithWindow = False,
        )
        # 32 means PDF in PowerPoint's PpSaveAsFileType enum.
        presentation.SaveAs(
            str(output_pdf),
            32,
        )
    except Exception as e:
        raise IngestionError(
            f"Error: {e}"
        ) from e
    finally:
        if presentation is not None:
            try:
                presentation.close()
            except Exception:
                pass

        if powerpoint is not None:
            try:
                powerpoint.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()

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
                "renderer": "microsoft-powerpoint",
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
