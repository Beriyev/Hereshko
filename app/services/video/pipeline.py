from typing import Any
from app.config import settings
from pathlib import Path
import shutil
import tempfile
import yt_dlp
from yt_dlp.utils import DownloadError
from ffmpy import FFmpeg, FFExecutableNotFoundError, FFRuntimeError
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

CHUNK_SECONDS = 30 * 60

def chunk_audio(audio_path: Path, chunk_seconds: int = CHUNK_SECONDS) -> list[Path]:
    chunk_dir = Path(tempfile.mkdtemp(prefix="hereshko_chunks_",dir=audio_path.parent))
    try:
        FFmpeg(
            global_options=["-hide_banner","-loglevel","error"],
            inputs={str(audio_path):None},
            outputs={
                str(chunk_dir / "chunk_%03d.mp3") : [
                    "-f", "segment",
                    "-segment_time", str(chunk_seconds),
                    "-c", "copy", "-reset_timestamps", "1"
                ]
            }
        ).run()
    except FFExecutableNotFoundError as e:
        shutil.rmtree(chunk_dir, ignore_errors=True)
        raise IngestionError("ffmpeg executable not found; install ffmpeg and add it to PATH") from e
    except FFRuntimeError as e:
        shutil.rmtree(chunk_dir, ignore_errors=True)
        raise IngestionError(f"ffmpeg failed to split audio: {e}") from e

    chunks = sorted(chunk_dir.glob("chunk_*.mp3"))
    if not chunks:
        shutil.rmtree(chunk_dir, ignore_errors=True)
        raise IngestionError("ffmpeg produced no audio chunks")
    return chunks

def get_transcript(audio_path: Path) -> dict:
    if not audio_path.exists():
        raise FileNotFoundError("Audio not found.")

    audio_chunks = chunk_audio(audio_path)
    chunk_dir = audio_chunks[0].parent

    try:
        offset = 0.0
        duration = 0.0
        texts = []
        segments = []
        language = None
        task = None

        for chunk in audio_chunks:
            with open(chunk,"rb") as f:
                response = groq_client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json",
                    file=f,
                    timestamp_granularities=["segment"]
                )
            data = response.model_dump()

            for segment in data["segments"]:
                text = segment["text"].strip()
                if text:
                    texts.append(text)
                    segments.append({
                        "text" : text,
                        "start" : segment["start"] + offset,
                        "end" : segment["end"] + offset
                    })

            if language is None:
                language = data.get("language")
            if task is None:
                task = data.get("task")

            chunk_duration = data.get("duration") or 0.0
            offset += chunk_duration
            duration += chunk_duration

        if not segments:
            raise IngestionError("Groq returned no segments.")

        return {
            "text" : "\n".join(texts),
            "language" : language,
            "duration" : duration,
            "task" : task,
            "segments" : segments
        }
    finally:
        shutil.rmtree(path=chunk_dir,ignore_errors=True)


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



