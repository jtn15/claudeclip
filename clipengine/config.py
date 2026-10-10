"""Configuration: environment variables, defaults, and shared helpers."""

from __future__ import annotations

import os
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mpg", ".mpeg", ".flv", ".wmv"}

OUT_W, OUT_H = 1080, 1920

FFMPEG_INSTALL_HELP = """\
ffmpeg and ffprobe are required but were not found on your PATH.

Install ffmpeg:
  macOS:           brew install ffmpeg
  Ubuntu/Debian:   sudo apt update && sudo apt install ffmpeg
  Windows:         winget install Gyan.FFmpeg   (or: choco install ffmpeg)
Then open a new terminal and re-run clipengine."""


class ClipEngineError(Exception):
    """Base class for errors that should be shown to the user without a traceback."""


@dataclass
class CaptionStyle:
    font: str = "Arial"
    font_size: int = 96
    color: str = "#FFFFFF"            # normal word color
    highlight_color: str = "#FFE600"  # currently spoken word
    outline_color: str = "#000000"
    outline: int = 7
    margin_bottom: int = 560          # px from bottom edge -> lower-middle of a 1920 frame
    max_words: int = 4
    max_chars: int | None = None      # None = derive from font size so a line fits the frame
    fonts_dir: str | None = None
    uppercase: bool = True


@dataclass
class Settings:
    anthropic_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-6"
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    output_dir: Path = field(default_factory=lambda: Path("output"))
    max_video_hours: float = 4.0


def load_settings() -> Settings:
    """Load settings from the environment (and a .env file in the working directory)."""
    load_dotenv()
    env = os.environ.get
    return Settings(
        anthropic_api_key=env("ANTHROPIC_API_KEY") or None,
        claude_model=env("CLIPENGINE_MODEL") or "claude-sonnet-4-6",
        whisper_model=env("WHISPER_MODEL") or "small",
        whisper_device=env("WHISPER_DEVICE") or "auto",
        whisper_compute_type=env("WHISPER_COMPUTE_TYPE") or "auto",
        output_dir=Path(env("CLIPENGINE_OUTPUT_DIR") or "output"),
        max_video_hours=float(env("CLIPENGINE_MAX_VIDEO_HOURS") or 4.0),
    )


def check_ffmpeg() -> None:
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        raise ClipEngineError(FFMPEG_INSTALL_HELP)


def slugify(text: str, max_len: int = 48) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    text = text[:max_len].strip("-")
    return text or "untitled"


def safe_dirname(text: str, max_len: int = 80) -> str:
    """Folder-safe name that keeps spaces and case (for client / video titles)."""
    text = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:max_len].strip(" .") or "Untitled"


def fmt_ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
