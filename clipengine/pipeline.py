"""End-to-end processing of one video: input -> transcript -> moments -> clips."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from rich.progress import Progress

from clipengine import captions, downloader, moments as moments_mod, render, transcribe
from clipengine.config import CaptionStyle, ClipEngineError, Settings, safe_dirname, slugify


@dataclass
class RunOptions:
    client: str
    clips: int = 8
    min_len: float = 20
    max_len: float = 60
    smart_crop: bool = False
    captions: bool = True
    caption_style: CaptionStyle = field(default_factory=CaptionStyle)
    refresh_transcript: bool = False
    allow_long: bool = False
    rights_confirmed: bool = False


@dataclass
class ClipResult:
    number: int
    path: Path
    moment: moments_mod.Moment
    face_found: bool | None = None  # None when smart-crop is off


@dataclass
class VideoResult:
    title: str
    out_dir: Path
    clips: list[ClipResult]
    failed: list[tuple[int, str]]
    transcript_cached: bool
    duration: float

    def top(self, n: int = 3) -> list[ClipResult]:
        return sorted(self.clips, key=lambda c: (-c.moment.virality_score, c.moment.start))[:n]


def validate_options(opts: RunOptions) -> None:
    if not 1 <= opts.clips <= 20:
        raise ClipEngineError("--clips must be between 1 and 20.")
    if opts.min_len < 5 or opts.max_len > 180 or opts.min_len >= opts.max_len:
        raise ClipEngineError("Use 5 <= --min-len < --max-len <= 180 (seconds).")


def process_video(source: str | Path, opts: RunOptions, settings: Settings, progress: Progress,
                  claude_client=None) -> VideoResult:
    validate_options(opts)
    if not opts.rights_confirmed:
        raise ClipEngineError("Rights not confirmed. Pass --confirm-rights (only for content you own or have permission to use).")

    client_dir = settings.output_dir / safe_dirname(opts.client)

    # 1. INPUT
    src_str = str(source)
    if downloader.is_url(src_str):
        t = progress.add_task("Reading URL", total=1)
        title = downloader.fetch_title(src_str)
        progress.update(t, completed=1)
        out_dir = client_dir / safe_dirname(title)
        out_dir.mkdir(parents=True, exist_ok=True)
        t = progress.add_task("Downloading video", total=1)
        video = downloader.download(src_str, out_dir / ".cache",
                                    on_progress=lambda f: progress.update(t, completed=f))
        progress.update(t, completed=1)
        source_label = src_str
    else:
        video = downloader.resolve_local(src_str)
        title = video.stem
        out_dir = client_dir / safe_dirname(title)
        out_dir.mkdir(parents=True, exist_ok=True)
        source_label = str(video)

    duration = transcribe.probe_duration(video)
    hours = duration / 3600
    if hours > settings.max_video_hours and not opts.allow_long:
        raise ClipEngineError(
            f"Video is {hours:.1f}h long (limit {settings.max_video_hours:g}h). Pass --allow-long to process it anyway "
            "(transcription will take a while)."
        )
    src_size = render.probe_video(video)

    # 2. TRANSCRIBE
    t = progress.add_task("Transcribing (Whisper)", total=1)
    transcript, cached = transcribe.transcribe(
        video, out_dir / "transcript.json", settings.whisper_model, settings.whisper_device,
        settings.whisper_compute_type, on_progress=lambda f: progress.update(t, completed=f),
        force=opts.refresh_transcript,
    )
    progress.update(t, completed=1, description="Transcript (cached)" if cached else "Transcribed (Whisper)")

    # 3. PICK MOMENTS
    t = progress.add_task("Finding best moments (Claude)", total=1)
    picked = moments_mod.pick_moments(
        transcript, settings.anthropic_api_key, settings.claude_model, opts.clips, opts.min_len, opts.max_len,
        on_progress=lambda f: progress.update(t, completed=f),
        on_retry=lambda msg: progress.console.print(f"[yellow]{msg}[/yellow]"),
        client=claude_client,
    )
    progress.update(t, completed=1)

    # 4-5. CUT + REFORMAT + CAPTIONS
    for old in out_dir.glob("clip_*.mp4"):
        old.unlink()
    t = progress.add_task("Rendering clips", total=len(picked))
    results: list[ClipResult] = []
    failed: list[tuple[int, str]] = []
    with tempfile.TemporaryDirectory(prefix="clipengine_") as tmp:
        for n, m in enumerate(picked, start=1):  # picked is chronological
            out_path = out_dir / f"clip_{n:02d}_{slugify(m.title)}.mp4"
            center, face_found = None, None
            if opts.smart_crop:
                center = render.detect_face_center(video, m.start, m.end)
                face_found = center is not None
            ass_path = None
            if opts.captions:
                candidate = Path(tmp) / f"clip_{n:02d}.ass"
                if captions.write_ass(candidate, transcript["words"], m.start, m.end, opts.caption_style):
                    ass_path = candidate
            try:
                render.render_clip(video, m.start, m.end, out_path, src_size, center, ass_path,
                                   opts.caption_style.fonts_dir)
                results.append(ClipResult(n, out_path, m, face_found))
            except ClipEngineError as e:
                failed.append((n, str(e)))
            progress.update(t, advance=1)
    if not results:
        raise ClipEngineError("Every clip failed to render:\n" + "\n".join(msg for _, msg in failed))

    # 6. OUTPUT FILES
    write_outputs(out_dir, title, source_label, opts, settings, transcript, results)
    return VideoResult(title, out_dir, results, failed, cached, duration)


def write_outputs(out_dir: Path, title: str, source_label: str, opts: RunOptions, settings: Settings,
                  transcript: dict, results: list[ClipResult]) -> None:
    clips_json = []
    for r in results:
        d = r.moment.to_dict()
        d.update({"clip_number": r.number, "file": r.path.name})
        if r.face_found is not None:
            d["face_detected"] = r.face_found
        clips_json.append(d)
    payload = {
        "video_title": title,
        "client": opts.client,
        "source": source_label,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rights_confirmed": opts.rights_confirmed,
        "model": settings.claude_model,
        "whisper_model": settings.whisper_model,
        "settings": {"clips": opts.clips, "min_len": opts.min_len, "max_len": opts.max_len,
                     "smart_crop": opts.smart_crop, "captions": opts.captions},
        "moments": clips_json,
    }
    (out_dir / "moments.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    txt = captions.build_captions_txt(
        title, opts.client,
        [{"number": r.number, "filename": r.path.name, "moment": r.moment} for r in results],
    )
    (out_dir / "captions.txt").write_text(txt, encoding="utf-8")
