import json
import subprocess
from pathlib import Path

import pytest

from clipengine import transcribe


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("vid") / "Sample Talk.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=100",
         "-f", "lavfi", "-i", "sine=frequency=300:duration=100", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(p)], check=True)
    return p


def make_words(n_sentences=24, words_per=8, dur=4.0):
    """Synthetic transcript: one sentence every 4s."""
    words = []
    for s in range(n_sentences):
        t0 = s * dur
        step = (dur - 0.4) / words_per
        for i in range(words_per):
            w = f"word{s}x{i}" + ("." if i == words_per - 1 else "")
            words.append({"word": w, "start": round(t0 + i * step, 3), "end": round(t0 + (i + 1) * step - 0.05, 3)})
    return words


@pytest.fixture
def seeded_transcript(sample_video):
    """Write a valid transcript cache so no Whisper model is needed."""
    def seed(out_dir: Path, model="small"):
        out_dir.mkdir(parents=True, exist_ok=True)
        words = make_words()
        data = {"fingerprint": transcribe.fingerprint(sample_video, model), "source_file": sample_video.name,
                "language": "en", "duration": 100.0, "text": "", "segments": [], "words": words}
        (out_dir / "transcript.json").write_text(json.dumps(data))
        return data
    return seed
