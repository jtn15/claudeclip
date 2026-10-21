import csv
import json
from datetime import date

import pytest

from socialcrew import agents, brand, llm, pack
from socialcrew.config import SocialCrewError


def profile(**kw):
    base = dict(client="Acme Roofing", business="Residential roofing in Phoenix", banned_words=["synergy"],
                content_pillars=[{"name": "Education", "description": "x"}], ctas=["Call for a free inspection"])
    return brand.BrandProfile(**(base | kw))


def plan_item(i, day="Mon", fmt="image", clip=None):
    return {"day": day, "pillar": "Education", "format": fmt, "objective": "leads", "angle": f"angle {i}",
            "hook": f"hook {i}", "why": "because", **({"clip": clip} if clip is not None else {})}


def post_data(n):
    return {"title": f"Post {n}", "hook": "Your roof is older than you think.",
            "instagram_caption": "Your roof is older than you think.\n\nHere's how to tell.",
            "facebook_caption": "FB version", "hashtags": ["phoenix roofing", "#roof", "#Roof"],
            "cta": "Call for a free inspection", "visual_brief": "Close-up of cracked shingles", "alt_text": "shingles",
            "slides": ["s1", "s2", "s3"], "script": []}


class FakeClient:
    """Answers each agent's tool with canned data and records every request."""

    def __init__(self, plan):
        self.plan, self.calls = plan, []
        self.messages = self

    def create(self, **kw):
        name = kw["tool_choice"]["name"]
        self.calls.append(name)
        n = len(self.calls)
        data = {
            "submit_plan": {"posts": self.plan},
            "submit_post": post_data(n),
            "submit_review": {"scores": {"brand_voice": 8, "hook": 9, "specificity": 7, "cta": 8},
                              "notes": ["Tightened hook"], "post": post_data(n)},
            "submit_brand_profile": {"business": "Roofing", "offers": ["Repairs"], "audience": "Homeowners",
                                     "pains": ["leaks"], "desires": ["dry house"], "voice": "plain",
                                     "voice_do": [], "voice_dont": [], "content_pillars": [], "ctas": ["Call"],
                                     "hashtags": ["#roof"], "compliance": [], "made_up_field": "dropped"},
        }[name]
        block = type("B", (), {"type": "tool_use", "name": name, "input": data})()
        return type("R", (), {"content": [block]})()


def test_validate_plan_drops_bad_items_and_sorts():
    raw = [plan_item(1, "Fri"), plan_item(2, "Monday"), plan_item(1, "Tue"),  # duplicate angle
           plan_item(3, "Blursday"), plan_item(4, "Wed", "tweet"), {"junk": 1},
           plan_item(5, "Thu", "reel", clip=3), plan_item(6, "Sat", "image", clip=3), plan_item(7, "Sun", "reel", clip=99)]
    out = agents.validate_plan(raw, 10, {3})
    assert [p.day for p in out] == ["Mon", "Thu", "Fri", "Sat", "Sun"]
    assert [p.clip for p in out] == [None, 3, None, None, None]  # clip only on reels, only if it exists
    assert len(agents.validate_plan(raw, 2, set())) == 2


def test_lint_catches_banned_words_and_limits():
    p = agents._post_from(post_data(1) | {"facebook_caption": "Real Synergy here", "hashtags": ["#dup"] * 3 + [f"#x{i}" for i in range(11)],
                                          "instagram_caption": "x" * 130}, 1, agents.PlanItem(**plan_item(1, fmt="reel")))
    issues = agents.lint_post(p, profile())
    assert any("synergy" in i for i in issues)
    assert any("first line" in i for i in issues)
    assert any("hashtags" in i for i in issues)
    assert any("Reel has no script" in i for i in issues)
    assert len(p.hashtags) == 12  # de-duplicated case-insensitively
    clean = agents._post_from(post_data(1), 1, agents.PlanItem(**plan_item(1, fmt="carousel")))
    assert agents.lint_post(clean, profile()) == []
    assert clean.hashtags == ["#phoenixroofing", "#roof"]


def test_run_week_writes_pack(tmp_path):
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    (clips_dir / "moments.json").write_text(json.dumps({"moments": [
        {"clip_number": 3, "file": "clip_03_x.mp4", "title": "Leak story", "hook": "h", "caption": "c",
         "duration": 30, "virality_score": 8}]}))
    clips = agents.load_clips(clips_dir)
    fake = FakeClient([plan_item(1, "Wed"), plan_item(2, "Mon", "reel", clip=3), plan_item(3, "Fri", "carousel")])
    res = pack.run_week(profile(), date(2026, 10, 26), 3, "Monsoon season", clips, tmp_path / "out", fake, "m")

    assert fake.calls.count("submit_plan") == 1 and fake.calls.count("submit_post") == 3
    assert fake.calls.count("submit_review") == 3
    assert [p.plan.day for p in res.posts] == ["Mon", "Wed", "Fri"] and not res.failed
    assert res.posts[0].clip_file.endswith("clip_03_x.mp4") and res.posts[0].score == 8.0
    assert res.out_dir == tmp_path / "out" / "Acme Roofing" / "2026-10-26"
    md = (res.out_dir / "content_pack.md").read_text()
    assert "week of October 26, 2026" in md and "Mon Oct 26" in md and "clip_03_x.mp4" in md
    data = json.loads((res.out_dir / "posts.json").read_text())
    assert [p["date"] for p in data["posts"]] == ["2026-10-26", "2026-10-28", "2026-10-30"]
    with (res.out_dir / "posts.csv").open(newline="") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 4 and rows[1][7].startswith("Your roof")


def test_failed_post_does_not_sink_the_week(tmp_path, monkeypatch):
    real = agents.write_post

    def flaky(number, *a, **kw):
        if number == 2:
            raise SocialCrewError("boom")
        return real(number, *a, **kw)

    monkeypatch.setattr(pack, "write_post", flaky)
    fake = FakeClient([plan_item(1), plan_item(2, "Tue")])
    res = pack.run_week(profile(), date(2026, 10, 26), 2, "", [], tmp_path, fake, "m")
    assert len(res.posts) == 1 and len(res.failed) == 1
    assert "Not written" in (res.out_dir / "content_pack.md").read_text()


def test_profile_roundtrip_and_onboarding(tmp_path):
    p = brand.draft_profile("Acme Roofing", "site text", "", FakeClient([]), "m", website="https://acme.test")
    assert p.business == "Roofing" and p.website == "https://acme.test"
    path = brand.save_profile(tmp_path, p)
    assert path.name == "acme-roofing.yaml"
    p.learnings.append("Before/after posts win")
    brand.save_profile(tmp_path, p)
    assert brand.load_profile(tmp_path, "Acme Roofing").learnings == ["Before/after posts win"]
    path.write_text(path.read_text() + "typo_field: 1\n")
    with pytest.raises(SocialCrewError, match="typo_field"):
        brand.load_profile(tmp_path, "Acme Roofing")
    with pytest.raises(SocialCrewError, match="onboard"):
        brand.load_profile(tmp_path, "Nobody")
    with pytest.raises(SocialCrewError, match="something to work with"):
        brand.draft_profile("X", "", " ", FakeClient([]), "m")


def test_html_to_text_and_weeks():
    html = "<html><head><title>t</title></head><body><script>x()</script><h1>Acme</h1><p>Roofs  since\n1998</p></body></html>"
    assert brand.html_to_text(html) == "Acme Roofs since 1998"
    assert pack.parse_week("2026-10-29") == date(2026, 10, 26)
    assert pack.next_monday(date(2026, 10, 26)) == date(2026, 11, 2)
    assert pack.next_monday(date(2026, 10, 21)) == date(2026, 10, 26)
    with pytest.raises(SocialCrewError):
        pack.parse_week("next week")


def test_call_tool_retries(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    import anthropic
    try:
        import httpx2 as httpx  # newer anthropic SDKs
    except ImportError:
        import httpx

    fake, n = FakeClient([]), {"i": 0}
    real = fake.create

    def create(**kw):
        n["i"] += 1
        if n["i"] < 3:
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "http://x"))
        return real(**kw)

    fake.create = create
    out = llm.call_tool(fake, "m", "s", "u", {"name": "submit_plan"})
    assert out == {"posts": []} and n["i"] == 3
    with pytest.raises(SocialCrewError, match="not set"):
        llm.make_client(None)
