import pytest

from clipengine import captions, moments, render
from clipengine.config import CaptionStyle, ClipEngineError, safe_dirname, slugify
from conftest import make_words


def test_slug_and_dirname():
    assert slugify("Why Roofs Leak!! (3 tips)") == "why-roofs-leak-3-tips"
    assert slugify("???") == "untitled"
    assert safe_dirname('A/B: "Acme" Roofing') == "A B Acme Roofing"


def test_sentences_split_on_punctuation_and_abbrev():
    words = [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in
             enumerate("Dr. Smith said hi. Then he left!".split())]
    s = moments.build_sentences(words)
    assert [x.text for x in s] == ["Dr. Smith said hi.", "Then he left!"]


def raw(a, b, score=8):
    return {"start_sentence": a, "end_sentence": b, "hook": "h", "title": "t", "virality_score": score,
            "reason": "r", "caption": "c", "hashtags": ["a b", "#c"]}


def test_validation_repairs_drops_and_dedups():
    sents = moments.build_sentences(make_words())  # 24 sentences x 4s (3.6s speech each)
    out = moments.validate_moments(
        [raw(0, 1), raw(0, 20), raw(3, 9, 9), raw(5, 12, 5), raw(-1, 4), raw(30, 40), {"junk": 1}],
        sents, 20, 60, 100.0)
    for m in out:
        assert 20 <= (sents[m.end_sentence].end - sents[m.start_sentence].start) <= 60
        assert m.start_sentence >= 0 and m.hashtags[0] == "#ab"
    spans = sorted((m.start_sentence, m.end_sentence) for m in out)
    assert all(spans[i][1] < spans[i + 1][0] for i in range(len(spans) - 1))  # no overlap
    # padding never crosses into neighbouring sentences
    for m in out:
        assert m.start > (sents[m.start_sentence - 1].end if m.start_sentence else -1)
        assert m.end < (sents[m.end_sentence + 1].start if m.end_sentence + 1 < len(sents) else 1e9)


def test_pick_moments_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(moments.time, "sleep", lambda s: None)
    import anthropic, httpx

    calls = {"n": 0}

    class Block:
        type, name = "tool_use", "submit_moments"
        input = {"moments": [raw(2, 8, 9), raw(12, 18, 7)]}

    class Messages:
        def create(self, **kw):
            calls["n"] += 1
            if calls["n"] < 3:
                raise anthropic.APIConnectionError(request=httpx.Request("POST", "http://x"))
            return type("R", (), {"content": [Block()]})()

    client = type("C", (), {"messages": Messages()})()
    t = {"words": make_words(), "duration": 100.0}
    got = moments.pick_moments(t, "k", "m", clips=5, client=client)
    assert calls["n"] == 3 and len(got) == 2 and got[0].start < got[1].start


def test_api_failure_after_retries(monkeypatch):
    monkeypatch.setattr(moments.time, "sleep", lambda s: None)
    import anthropic, httpx

    class Messages:
        def create(self, **kw):
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "http://x"))

    with pytest.raises(ClipEngineError, match="failed after"):
        moments.pick_moments({"words": make_words(), "duration": 100.0}, "k", "m",
                             client=type("C", (), {"messages": Messages()})())


def test_caption_groups_and_ass():
    words = make_words(2, 8)
    groups = captions.group_words(words, 4, 20)
    assert all(1 <= len(g) <= 4 for g in groups)
    ass = captions.build_ass(words, 0, 8, CaptionStyle(font="Impact", color="#FF0000"))
    assert "Impact" in ass and "&H000000FF" in ass and ass.count("Dialogue:") == 16
    assert captions.ass_color("#FFE600") == "&H0000E6FF"
    with pytest.raises(ClipEngineError):
        captions.ass_color("red")


def test_crop_box():
    assert render.crop_box(1920, 1080) == (608, 1080, 656, 0)
    cw, ch, x, _ = render.crop_box(1920, 1080, center_x=0.1)
    assert x == 0
    cw, ch, x, _ = render.crop_box(1920, 1080, center_x=0.99)
    assert x + cw == 1920
    assert render.crop_box(1080, 1920)[:2] == (1080, 1920)
