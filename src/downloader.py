import yt_dlp
from pathlib import Path
from typing import Optional


def get_video_info(url: str, cookiefile: Optional[str] = None) -> dict:
    opts = {"quiet": True, "no_warnings": True}
    if cookiefile:
        opts["cookiefile"] = cookiefile
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0) or 0,
            "uploader": info.get("uploader", ""),
            "thumbnail": info.get("thumbnail", ""),
            "description": (info.get("description") or "")[:500],
        }


def download_audio(url: str, output_dir: Path, cookiefile: Optional[str] = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "audio.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    if cookiefile:
        opts["cookiefile"] = cookiefile

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    audio_files = [f for f in output_dir.iterdir() if f.stem == "audio"]
    if audio_files:
        return audio_files[0]

    raise FileNotFoundError(f"Downloaded audio not found in {output_dir}")


def download_video(url: str, output_dir: Path, cookiefile: Optional[str] = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
        "outtmpl": str(output_dir / "video.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }
    if cookiefile:
        opts["cookiefile"] = cookiefile

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    for ext in ["mp4", "mkv", "webm", "avi"]:
        path = output_dir / f"video.{ext}"
        if path.exists():
            return path

    raise FileNotFoundError(f"Downloaded video not found in {output_dir}")
