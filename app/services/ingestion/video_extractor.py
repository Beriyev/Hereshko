import tempfile, shutil, uuid
from datetime import datetime, timezone
from pathlib import Path
from app.core.normalization import Document, SourceType
from app.core.exceptions import IngestionError
from app.services.video.pipeline import download_yt_audio, get_transcript, get_metadata

def extract_youtube(url: str, notebook_id: str) -> Document:
    temp_dir = Path(tempfile.mkdtemp(prefix="hereshko_youtube_"))
    try:
        audio_path = download_yt_audio(video_url=url,output_dir=temp_dir)
        metadata = get_metadata(video_url=url)
        transcript = get_transcript(input_dir=audio_path)

        texts = []
        boundaries = []
        offset = 0

        for segment in transcript["segments"]:
            text = segment["text"].strip()
            text_size = len(text) if text else 0
            if text:
                boundaries.append(
                    {
                        "start" : offset,
                        "end" : offset+text_size,
                        "timestamp_seconds" : segment["start"]
                    }
                )
                offset+=text_size+1
                texts.append(text)
        content = "\n".join(texts) + "\n" if texts else "" 

        return Document(
            document_id=str(uuid.uuid4()),
            notebook_id=notebook_id,
            content=content,
            source_identifier=url,
            source_type=SourceType.YOUTUBE,
            title = metadata.get("title") or url,
            ingested_at=datetime.now(timezone.utc),
            raw_metadata={
                "url": url,
                "title": metadata.get("title"),
                "channel": metadata.get("channel"),
                "uploader": metadata.get("uploader"),
                "duration": metadata.get("duration"),
                "description": metadata.get("description"),
                "view_count": metadata.get("view_count"),
                "language": transcript.get("language"),
                "audio_duration": transcript.get("duration"),
                "boundaries": boundaries,
            }
        )
    finally:
        shutil.rmtree(path=temp_dir,ignore_errors=True)
