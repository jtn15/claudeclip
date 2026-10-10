"""Input handling: local files or a single URL (downloaded with yt-dlp)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from clipengine.config import VIDEO_EXTENSIONS, ClipEngineError

_URL_RE = re.compile(r"^https?://", re.I)


def is_url(value: str) -> bool:
    return bool(_URL_RE.match(value.strip()))


def _ydl_opts(**extra):
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
    opts.update(extra)
    return opts


def fetch_title(url: str) -> str:
    """Look up the video title without downloading (used to name the output folder)."""
    import yt_dlp
    from yt_dlp.utils import DownloadError

    try:
        with yt_dlp.YoutubeDL(_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as e:
        raise ClipEngineError(f"Could not read that URL: {_clean_yt_error(e)}") from e
    except Exception as e:  # network errors, unsupported extractors, etc.
        raise ClipEngineError(f"Could not read that URL: {e}") from e
    if not info:
        raise ClipEngineError("Could not read that URL: no video information returned.")
    return str(info.get("title") or info.get("id") or "video")


def download(url: str, dest_dir: Path, on_progress: Callable[[float], None] | None = None) -> Path:
    """Download one video to dest_dir and return the file path. Reuses an existing download."""
    import yt_dlp
    from yt_dlp.utils import DownloadError

    dest_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(dest_dir.glob("source.*"))
    existing = [p for p in existing if p.suffix.lower() in VIDEO_EXTENSIONS]
    if existing:
        return existing[0]

    def hook(d):
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                on_progress(min(1.0, d.get("downloaded_bytes", 0) / total))

    opts = _ydl_opts(
        outtmpl=str(dest_dir / "source.%(ext)s"),
        format="bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        merge_output_format="mp4",
        progress_hooks=[hook],
        retries=3,
    )
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except DownloadError as e:
        raise ClipEngineError(f"Download failed: {_clean_yt_error(e)}") from e
    except Exception as e:
        raise ClipEngineError(f"Download failed: {e}") from e

    files = [p for p in dest_dir.glob("source.*") if p.suffix.lower() in VIDEO_EXTENSIONS]
    if not files:
        raise ClipEngineError("Download finished but no video file was produced.")
    return files[0]


def _clean_yt_error(e: Exception) -> str:
    return re.sub(r"^ERROR:\s*", "", str(e)).strip().splitlines()[0] if str(e).strip() else "unknown error"


def resolve_local(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.exists():
        raise ClipEngineError(f"File not found: {p}")
    if not p.is_file():
        raise ClipEngineError(f"Not a file: {p}")
    if p.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ClipEngineError(
            f"Unsupported file type '{p.suffix}'. Supported: {', '.join(sorted(VIDEO_EXTENSIONS))}"
        )
    return p


def list_videos(folder: str) -> list[Path]:
    """Videos directly inside a folder (non-recursive, sorted by name)."""
    p = Path(folder).expanduser()
    if not p.is_dir():
        raise ClipEngineError(f"Not a folder: {p}")
    videos = sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS)
    if not videos:
        raise ClipEngineError(f"No video files found in {p}")
    return videos
