"""Cut moments with ffmpeg and reformat to 1080x1920 (9:16), optionally burning in captions."""

from __future__ import annotations

import statistics
import subprocess
from pathlib import Path

from clipengine.config import OUT_H, OUT_W, ClipEngineError


def probe_video(path: Path) -> tuple[int, int]:
    """Display width/height (accounts for rotation metadata)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:stream_side_data=rotation:stream_tags=rotate",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout
        import json
        stream = json.loads(out)["streams"][0]
    except (subprocess.CalledProcessError, KeyError, IndexError, ValueError) as e:
        raise ClipEngineError(f"Could not read video stream from {path}") from e
    w, h = int(stream["width"]), int(stream["height"])
    rot = stream.get("tags", {}).get("rotate")
    for sd in stream.get("side_data_list", []) or []:
        rot = sd.get("rotation", rot)
    if rot is not None and abs(int(float(rot))) % 180 == 90:
        w, h = h, w
    return w, h


def crop_box(src_w: int, src_h: int, center_x: float | None = None) -> tuple[int, int, int, int]:
    """Largest 9:16 box inside the frame. center_x is a 0-1 horizontal focus (None = center)."""
    target = OUT_W / OUT_H
    if src_w / src_h >= target:
        ch = src_h
        cw = int(round(src_h * target / 2)) * 2
    else:
        cw = src_w
        ch = int(round(src_w / target / 2)) * 2
    cw, ch = min(cw, src_w), min(ch, src_h)
    cx = 0.5 if center_x is None else center_x
    x = int(round(cx * src_w - cw / 2))
    x = max(0, min(x, src_w - cw))
    y = (src_h - ch) // 2
    return cw, ch, x - (x % 2), y - (y % 2)


def detect_face_center(video: Path, start: float, end: float, samples: int = 24) -> float | None:
    """Median horizontal position (0-1) of the largest face across the clip, or None."""
    try:
        import cv2
    except ImportError:
        return None
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cascade.empty():
        return None
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return None
    centers = []
    try:
        n = max(2, min(samples, int(end - start)))
        for i in range(n):
            t = start + (end - start) * (i + 0.5) / n
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            h, w = frame.shape[:2]
            scale = 640 / w if w > 640 else 1.0
            small = cv2.resize(frame, None, fx=scale, fy=scale) if scale != 1.0 else frame
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6,
                                             minSize=(max(30, small.shape[1] // 20),) * 2)
            if len(faces):
                fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                centers.append((fx + fw / 2) / small.shape[1])
    finally:
        cap.release()
    if len(centers) < max(2, int(n * 0.2)):
        return None
    return float(statistics.median(centers))


def _filter_path(p: Path) -> str:
    s = str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return s


def render_clip(
    src: Path,
    start: float,
    end: float,
    out_path: Path,
    src_size: tuple[int, int],
    center_x: float | None = None,
    ass_path: Path | None = None,
    fonts_dir: str | None = None,
) -> None:
    cw, ch, x, y = crop_box(*src_size, center_x=center_x)
    vf = f"crop={cw}:{ch}:{x}:{y},scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1"
    if ass_path is not None:
        vf += f",ass=filename='{_filter_path(ass_path)}'"
        if fonts_dir:
            vf += f":fontsdir='{_filter_path(Path(fonts_dir))}'"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{end - start:.3f}",
        "-vf", vf, "-r", "30",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
        "-movflags", "+faststart", str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_path.exists():
        tail = "\n".join(proc.stderr.strip().splitlines()[-6:])
        out_path.unlink(missing_ok=True)
        raise ClipEngineError(f"ffmpeg failed on {out_path.name}:\n{tail}")
