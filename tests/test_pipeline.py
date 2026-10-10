import json
import subprocess

from rich.progress import Progress

from clipengine.config import Settings
from clipengine.pipeline import RunOptions, process_video
from test_units import raw


class FakeClient:
    class messages:
        @staticmethod
        def create(**kw):
            block = type("B", (), {"type": "tool_use", "name": "submit_moments",
                                   "input": {"moments": [raw(8, 14, 6), raw(1, 6, 9), raw(16, 21, 7)]}})()
            return type("R", (), {"content": [block]})()


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(p)],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    return d["streams"][0]["width"], d["streams"][0]["height"], float(d["format"]["duration"])


def run(sample_video, seeded_transcript, tmp_path, **kw):
    settings = Settings(output_dir=tmp_path / "out")
    opts = RunOptions(client="Acme Roofing", rights_confirmed=True, **kw)
    seeded_transcript(settings.output_dir / "Acme Roofing" / "Sample Talk")
    with Progress(disable=True) as p:
        return process_video(sample_video, opts, settings, p, claude_client=FakeClient())


def test_end_to_end(sample_video, seeded_transcript, tmp_path):
    res = run(sample_video, seeded_transcript, tmp_path, smart_crop=True)
    assert res.transcript_cached and len(res.clips) == 3
    names = [c.path.name for c in res.clips]
    assert [n[:7] for n in names] == ["clip_01", "clip_02", "clip_03"]
    assert [c.moment.start for c in res.clips] == sorted(c.moment.start for c in res.clips)
    for c in res.clips:
        w, h, d = probe(c.path)
        assert (w, h) == (1080, 1920) and 19 < d < 61
        assert c.face_found is False  # synthetic video has no faces -> center crop fallback
    assert res.top(1)[0].moment.virality_score == 9
    d = res.out_dir
    for f in ("transcript.json", "moments.json", "captions.txt"):
        assert (d / f).exists()
    mj = json.loads((d / "moments.json").read_text())
    assert mj["rights_confirmed"] is True and len(mj["moments"]) == 3
    assert "#ab" in (d / "captions.txt").read_text()


def test_no_captions_and_rerun_cleans_old_clips(sample_video, seeded_transcript, tmp_path):
    res = run(sample_video, seeded_transcript, tmp_path, captions=False)
    stale = res.out_dir / "clip_09_stale.mp4"
    stale.write_bytes(b"x")
    res2 = run(sample_video, seeded_transcript, tmp_path, captions=False)
    assert not stale.exists() and len(res2.clips) == 3


def test_requires_rights(sample_video, tmp_path):
    import pytest
    from clipengine.config import ClipEngineError
    with pytest.raises(ClipEngineError, match="Rights"):
        with Progress(disable=True) as p:
            process_video(sample_video, RunOptions(client="x"), Settings(output_dir=tmp_path), p)
