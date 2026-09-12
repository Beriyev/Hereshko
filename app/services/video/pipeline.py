from typing import Any
from app.config import settings
from pathlib import Path
import shutil
import yt_dlp
from yt_dlp.utils import DownloadError
from app.core.exceptions import IngestionError
from app.clients.groq_client import groq_client


def _default_deno_path() -> str:
    for candidate in (
        Path.home() / ".deno" / "bin" / "deno.exe",
        Path.home() / ".deno" / "bin" / "deno",
    ):
        if candidate.exists():
            return str(candidate)
    which = shutil.which("deno")
    return which or ""


def download_yt_audio(video_url: str, output_dir: Path) -> Path:
    ydl_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "audio.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "64",
        }],
        "postprocessor_args": ["-ar", "16000", "-ac", "1"],
    }
    if settings.yt_player_client:
        clients = [c.strip() for c in settings.yt_player_client.split(",") if c.strip()]
        ydl_opts["extractor_args"] = {"youtube": [f"player_client={c}" for c in clients]}
    if settings.yt_js_runtime:
        runtime = settings.yt_js_runtime
        if runtime == "deno":
            deno_path = settings.yt_deno_path or _default_deno_path()
            ydl_opts["js_runtimes"] = {"deno": {"path": deno_path}} if deno_path else {"deno": {}}
        else:
            ydl_opts["js_runtimes"] = {runtime: {}}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
            ydl.download([video_url])
    except DownloadError as e:
        raise IngestionError(f"Failed to download YouTube audio: {e}") from e

    audio_files = sorted(output_dir.glob("audio.*"))
    if not audio_files:
        raise IngestionError("yt-dlp reported success but no audio file was produced")
    return audio_files[0]

GROQ_UPLOAD_LIMIT_BYTES = 25 * 1024 * 1024

def get_transcript(input_dir: Path) -> dict:
    if not input_dir.exists():
        raise FileNotFoundError("Audio not found.")

    size = input_dir.stat().st_size
    if size > GROQ_UPLOAD_LIMIT_BYTES:
        raise IngestionError(
            f"Video audio is too large to transcribe ({size / (1024 * 1024):.1f} MB exceeds "
            f"Groq's {GROQ_UPLOAD_LIMIT_BYTES // (1024 * 1024)} MB upload limit)"
        )
    
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
    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }
    if settings.yt_player_client:
        clients = [c.strip() for c in settings.yt_player_client.split(",") if c.strip()]
        ydl_opts["extractor_args"] = {"youtube": [f"player_client={c}" for c in clients]}
    if settings.yt_js_runtime:
        runtime = settings.yt_js_runtime
        if runtime == "deno":
            deno_path = settings.yt_deno_path or _default_deno_path()
            ydl_opts["js_runtimes"] = {"deno": {"path": deno_path}} if deno_path else {"deno": {}}
        else:
            ydl_opts["js_runtimes"] = {runtime: {}}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: #type: ignore[arg-type]
            info = ydl.extract_info(url=video_url,download=False)
            if info is None:
                raise IngestionError(f"No extractable info returned for: {video_url}")
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



