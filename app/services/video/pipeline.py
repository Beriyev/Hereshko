from typing import Any
from app.config import settings
from pathlib import Path
import shutil
import tempfile
import os
import sys
import yt_dlp
from yt_dlp.cookies import CookieLoadError, SUPPORTED_BROWSERS, SUPPORTED_KEYRINGS
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


def _configure_youtube_options(ydl_opts: dict[str, Any], *, use_cookies: bool = False) -> None:
    browser = settings.yt_cookies_browser.strip().lower().replace("_", "-") if use_cookies else ""
    profile = settings.yt_cookies_profile.strip() or None
    authenticated = use_cookies and bool(settings.yt_cookies_file or browser)
    if use_cookies and settings.yt_cookies_file:
        cookie_path = Path(settings.yt_cookies_file).expanduser()
        if not cookie_path.is_file():
            raise IngestionError("The configured YouTube cookies file does not exist.")
        ydl_opts["cookiefile"] = str(cookie_path)
    elif browser:
        if browser in ("opera-gx", "opera gx"):
            browser = "opera"
            if profile is None:
                if sys.platform != "win32":
                    raise IngestionError("Set YT_COOKIES_PROFILE to your Opera GX profile path.")
                roaming = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
                profile = str(roaming / "Opera Software" / "Opera GX Stable")
        if browser not in SUPPORTED_BROWSERS:
            raise IngestionError(
                f"Unsupported cookie browser '{browser}'. Use one of "
                f"{', '.join(sorted(SUPPORTED_BROWSERS))}, opera-gx, or YT_COOKIES_FILE."
            )
        keyring = settings.yt_cookies_keyring.strip().upper() or None
        if keyring is not None and keyring not in SUPPORTED_KEYRINGS:
            raise IngestionError("Unsupported YT_COOKIES_KEYRING setting.")
        container = settings.yt_cookies_container.strip() or None
        ydl_opts["cookiesfrombrowser"] = (browser, profile, keyring, container)

    # Authenticated requests need yt-dlp's cookie-compatible client defaults.
    if settings.yt_player_client and not authenticated:
        clients = [c.strip() for c in settings.yt_player_client.split(",") if c.strip()]
        ydl_opts["extractor_args"] = {"youtube": {"player_client": clients}}
    if settings.yt_js_runtime:
        runtime = settings.yt_js_runtime
        if runtime == "deno":
            deno_path = settings.yt_deno_path or _default_deno_path()
            ydl_opts["js_runtimes"] = {"deno": {"path": deno_path}} if deno_path else {"deno": {}}
        else:
            ydl_opts["js_runtimes"] = {runtime: {}}


def _extract_youtube_info(video_url: str, ydl_opts: dict[str, Any], *, download: bool) -> dict[str, Any]:
    options = dict(ydl_opts)
    _configure_youtube_options(options)
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(video_url, download=download)
    except DownloadError as error:
        # Public videos should never need access to a live browser database.
        # Retry with configured credentials only when YouTube requests authentication.
        message = str(error).lower()
        needs_auth = any(marker in message for marker in (
            "sign in", "login required", "log in", "confirm your age", "age-restricted", "private video",
        ))
        if not needs_auth or not (settings.yt_cookies_file or settings.yt_cookies_browser):
            raise IngestionError(f"YouTube extraction failed: {error}") from error

        options = dict(ydl_opts)
        _configure_youtube_options(options, use_cookies=True)
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(video_url, download=download)
        except (DownloadError, CookieLoadError) as auth_error:
            raise IngestionError(
                f"YouTube requested authentication and the configured cookie fallback failed: {auth_error}"
            ) from auth_error

    if info is None:
        raise IngestionError(f"No extractable info returned for: {video_url}")
    return dict(info)


def download_yt_audio(video_url: str, output_dir: Path) -> tuple[Path, dict[str, Any]]:
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
    info = _extract_youtube_info(video_url, ydl_opts, download=True)

    audio_path = output_dir / "audio.mp3"
    if not audio_path.exists():
        raise IngestionError("yt-dlp reported success but audio.mp3 was not produced")

    return audio_path, info

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
                try:
                    response = groq_client.audio.transcriptions.create(
                        model=settings.groq_whisper_model,
                        response_format="verbose_json",
                        file=f,
                        timestamp_granularities=["segment"],
                    )
                except Exception as e:
                    raise IngestionError(
                        f"YouTube transcription failed: {e}"
                    ) from e
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
    info = _extract_youtube_info(video_url, ydl_opts, download=False)
    
    return {
        "title": info.get("title"),
        "channel": info.get("channel"),
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "description": info.get("description"),
        "view_count": info.get("view_count"),
    }



