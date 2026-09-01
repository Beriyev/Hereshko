from typing import Any
from app.config import settings
import tempfile
from pathlib import Path
import shutil
import yt_dlp
from yt_dlp.utils import DownloadError
from app.core.exceptions import IngestionError
from app.clients.groq_client import groq_client

def download_yt_audio(video_url: str, output_dir: Path) -> Path:
    ydl_opts = {
        'format' : 'bestaudio/best',
        'outtmpl': str(output_dir / "audio.%(ext)s"),
        'postprocessors' : [{
            'key' : 'FFmpegExtractAudio',
            'preferredcodec' : 'mp3',
            'preferredquality' : '192'
        }],
        'postprocessor_args' : ['-ar','16000','-ac','1']
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
            ydl.download([video_url])
    except DownloadError as e:
        raise IngestionError(f"Failed to download YouTube audio: {e}") from e

    audio_files = sorted(output_dir.glob("audio.*"))
    if not audio_files:
        raise IngestionError("yt-dlp reported success but no audio file was produced")
    return audio_files[0]

def get_transcript(input_dir: Path) -> dict:
    if not input_dir.exists():
        raise FileNotFoundError("Audio not found.")
    
    with open(input_dir,"rb") as f:
        response = groq_client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            response_format="verbose_json",
            file=f,
            language="en",
            timestamp_granularities=["segment"]
        )

    texts: list[dict[str,Any]] = []
    data = response.model_dump()

    for segment in data["segments"]:
        texts.append({
            "text" : segment["text"],
            "start" : segment["start"],
            "end" : segment["end"]
        })
    if not texts:
        raise IngestionError("Groq returned no transcript segments")
    
    return {
        "text" : data.get("text",""),
        "language" : data.get("language"),
        "duration" : data.get("duration"),
        "task" : data.get("task"),
        "segments" : texts
    }

def get_metadata(video_url: str) -> dict:
    ydl_opts ={"quiet":True, "no_warnings":True, "skip_download":True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: #type: ignore[arg-type]
            info = ydl.extract_info(url=video_url,download=False)
    except DownloadError as e:
        raise IngestionError(e) from e
    
    return {
        "title": info.get("title"),
        "channel": info.get("channel"),
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "description": info.get("description"),
        "view_count": info.get("view_count"),
    }



