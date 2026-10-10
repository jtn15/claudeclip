"""Local speech-to-text with faster-whisper, producing word-level timestamps."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable

from clipengine.config import ClipEngineError

MIN_WORDS = 15
CACHE_VERSION = 1


def probe_duration(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return float(out)
    except (subprocess.CalledProcessError, ValueError) as e:
        raise ClipEngineError(f"Could not read video (is it a valid, non-corrupt file?): {path}") from e


def fingerprint(path: Path, model: str) -> dict:
    st = path.stat()
    return {"version": CACHE_VERSION, "name": path.name, "size": st.st_size, "model": model}


def load_cached(cache_path: Path, source: Path, model: str) -> dict | None:
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    fp = data.get("fingerprint") or {}
    if fp == fingerprint(source, model) and data.get("words"):
        return data
    return None


def transcribe(
    video: Path,
    cache_path: Path,
    model_size: str = "small",
    device: str = "auto",
    compute_type: str = "auto",
    on_progress: Callable[[float], None] | None = None,
    force: bool = False,
) -> tuple[dict, bool]:
    """Return (transcript, from_cache). Transcript = {language, duration, text, segments, words}."""
    if not force:
        cached = load_cached(cache_path, video, model_size)
        if cached:
            return cached, True

    duration = probe_duration(video)

    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ClipEngineError("faster-whisper is not installed. Run: pip install -r requirements.txt") from e

    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        seg_iter, info = model.transcribe(
            str(video), word_timestamps=True, vad_filter=True, beam_size=5,
        )
        segments, words = [], []
        for seg in seg_iter:
            seg_words = [
                {"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
                for w in (seg.words or []) if w.word.strip()
            ]
            segments.append({
                "start": round(seg.start, 3), "end": round(seg.end, 3),
                "text": seg.text.strip(), "words": seg_words,
            })
            words.extend(seg_words)
            if on_progress and duration:
                on_progress(min(1.0, seg.end / duration))
    except ClipEngineError:
        raise
    except Exception as e:
        raise ClipEngineError(
            f"Transcription failed ({type(e).__name__}: {e}). If this is the first run, "
            f"the '{model_size}' Whisper model needs to download; check your internet connection."
        ) from e

    if len(words) < MIN_WORDS:
        raise NoSpeechError(
            f"No usable speech detected in {video.name} ({len(words)} words found). "
            "Skipping: clipengine needs a video with spoken audio."
        )

    transcript = {
        "fingerprint": fingerprint(video, model_size),
        "source_file": video.name,
        "language": info.language,
        "duration": round(duration, 3),
        "text": " ".join(s["text"] for s in segments),
        "segments": segments,
        "words": words,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8")
    if on_progress:
        on_progress(1.0)
    return transcript, False


class NoSpeechError(ClipEngineError):
    pass
