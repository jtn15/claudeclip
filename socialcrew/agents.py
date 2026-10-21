"""The crew: strategist plans the week, writer drafts each post, editor tightens it against the brand.

Every agent reads the same brand profile, so tailoring lives in one editable file per client, not in prompts.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from socialcrew.brand import BrandProfile
from socialcrew.config import SocialCrewError
from socialcrew.llm import call_tool

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
FORMATS = ["image", "carousel", "reel", "story"]
OBJECTIVES = ["reach", "engagement", "trust", "leads"]
IG_CAPTION_LIMIT = 2200
IG_FOLD_CHARS = 125          # Instagram cuts the caption to "...more" around here; the hook has to land before it
MAX_HASHTAGS = 10


@dataclass
class PlanItem:
    day: str
    pillar: str
    format: str
    objective: str
    angle: str
    hook: str
    why: str
    clip: int | None = None   # clip_number from a clipengine run, for reels cut from real footage


@dataclass
class Post:
    number: int
    plan: PlanItem
    title: str
    hook: str
    instagram_caption: str
    facebook_caption: str
    hashtags: list[str]
    cta: str
    visual_brief: str
    ai_image_prompt: str = ""
    on_screen_text: str = ""
    alt_text: str = ""
    slides: list[str] = field(default_factory=list)   # carousel slides or story frames
    script: list[str] = field(default_factory=list)   # reel beats
    scores: dict = field(default_factory=dict)
    editor_notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    clip_file: str = ""

    @property
    def score(self) -> float:
        vals = [v for v in self.scores.values() if isinstance(v, (int, float))]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["score"] = self.score
        return d


# --------------------------------------------------------------------------- clips from clipengine

def load_clips(clips_dir: Path) -> list[dict]:
    """Read a clipengine output folder so reels can be written around real footage."""
    path = clips_dir / "moments.json"
    if not path.exists():
        raise SocialCrewError(f"No moments.json in {clips_dir}. Point --clips-dir at a clipengine output folder.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        {"clip_number": m["clip_number"], "file": str(clips_dir / m["file"]), "title": m.get("title", ""),
         "hook": m.get("hook", ""), "caption": m.get("caption", ""), "duration": m.get("duration"),
         "virality_score": m.get("virality_score")}
        for m in data.get("moments", []) if "clip_number" in m and "file" in m
    ]


def _clips_prompt(clips: list[dict]) -> str:
    return "\n".join(f"- clip {c['clip_number']} ({c['duration']}s, score {c['virality_score']}/10): "
                     f"{c['title']} | hook: {c['hook']}" for c in clips)


# --------------------------------------------------------------------------- strategist

STRATEGY_TOOL = {
    "name": "submit_plan",
    "description": "Submit the week's content plan.",
    "input_schema": {
        "type": "object",
        "properties": {
            "posts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "day": {"type": "string", "enum": DAYS},
                        "pillar": {"type": "string", "description": "One of the brand's content pillars."},
                        "format": {"type": "string", "enum": FORMATS},
                        "objective": {"type": "string", "enum": OBJECTIVES},
                        "angle": {"type": "string", "description": "The specific idea, one sentence. Not a topic, an argument."},
                        "hook": {"type": "string", "description": "Draft first line that stops the scroll."},
                        "why": {"type": "string", "description": "Why this post, for this audience, this week."},
                        "clip": {"type": "integer", "description": "clip_number to use, only for reels built on a provided clip."},
                    },
                    "required": ["day", "pillar", "format", "objective", "angle", "hook", "why"],
                },
            }
        },
        "required": ["posts"],
    },
}

STRATEGY_SYSTEM = """You are the content strategist at a digital marketing agency, planning one week of Facebook and
Instagram posts for a client. You get the client's brand profile, this week's focus, and sometimes a list of
ready-made video clips.

Rules:
- Every post speaks to ONE specific pain or desire from the profile. No generic "tips Tuesday" filler.
- Rotate pillars and formats across the week; no two posts may share an angle.
- At least one post is built to generate leads with a single, concrete CTA from the profile.
- Use the provided clips for reels when they fit: set clip to its clip_number. Never invent clip numbers.
- Honor every compliance rule and lean on the learnings: repeat what worked, drop what flopped.
- Space posts across the week; never put two on the same day unless asked for more than 7.
Always answer by calling submit_plan."""


def validate_plan(raw: list[dict], count: int, clip_numbers: set[int]) -> list[PlanItem]:
    out: list[PlanItem] = []
    seen: set[str] = set()
    for item in raw:
        try:
            angle = str(item["angle"]).strip()
            plan = PlanItem(
                day=str(item["day"]).strip()[:3].title(), pillar=str(item["pillar"]).strip(),
                format=str(item["format"]).strip().lower(), objective=str(item["objective"]).strip().lower(),
                angle=angle, hook=str(item["hook"]).strip(), why=str(item.get("why", "")).strip(),
            )
        except (KeyError, TypeError):
            continue
        if not angle or angle.lower() in seen or plan.day not in DAYS or plan.format not in FORMATS:
            continue
        if plan.objective not in OBJECTIVES:
            plan.objective = "engagement"
        clip = item.get("clip")
        if isinstance(clip, int) and clip in clip_numbers and plan.format == "reel":
            plan.clip = clip
        seen.add(angle.lower())
        out.append(plan)
    out = out[:count]
    out.sort(key=lambda p: DAYS.index(p.day))
    return out


def plan_week(profile: BrandProfile, count: int, focus: str, clips: list[dict], client, model: str,
              on_retry: Callable[[str], None] | None = None) -> list[PlanItem]:
    user = (f"Plan {count} posts for this week.\n\nThis week's focus / promos / events:\n{focus or '(none given)'}\n\n"
            f"Brand profile:\n{profile.to_prompt()}")
    if clips:
        user += f"\nAvailable clips (vertical, captioned, ready to post):\n{_clips_prompt(clips)}"
    clip_numbers = {c["clip_number"] for c in clips}
    plan = validate_plan(call_tool(client, model, STRATEGY_SYSTEM, user, STRATEGY_TOOL, on_retry).get("posts", []),
                         count, clip_numbers)
    if not plan:
        raise SocialCrewError("The strategist did not return a usable plan. Try again or simplify --focus.")
    return plan


# --------------------------------------------------------------------------- writer + editor

_POST_PROPS = {
    "title": {"type": "string", "description": "Internal name, max 8 words."},
    "hook": {"type": "string", "description": "First line. Must land within 125 characters."},
    "instagram_caption": {"type": "string", "description": "Full IG caption starting with the hook. Line breaks for skimming. No hashtags."},
    "facebook_caption": {"type": "string", "description": "FB version: more conversational, may be longer, links allowed. No hashtags."},
    "hashtags": {"type": "array", "items": {"type": "string"}, "description": "3-8 hashtags with #."},
    "cta": {"type": "string", "description": "The one next step."},
    "visual_brief": {"type": "string", "description": "What the designer/photographer/videographer makes: subject, composition, mood, brand cues."},
    "ai_image_prompt": {"type": "string", "description": "Prompt for an AI image generator, if a generated image fits. Empty for real-footage posts."},
    "on_screen_text": {"type": "string", "description": "Text overlaid on the image/cover. Max 8 words."},
    "alt_text": {"type": "string"},
    "slides": {"type": "array", "items": {"type": "string"}, "description": "Carousel: 5-8 slides, slide 1 is the hook, last is the CTA. Story: 3-5 frames."},
    "script": {"type": "array", "items": {"type": "string"}, "description": "Reel: beats like '0-3s: ...' with voiceover + on-screen text."},
}
_POST_REQUIRED = ["title", "hook", "instagram_caption", "facebook_caption", "hashtags", "cta", "visual_brief", "alt_text"]

WRITE_TOOL = {
    "name": "submit_post",
    "description": "Submit the finished post.",
    "input_schema": {"type": "object", "properties": _POST_PROPS, "required": _POST_REQUIRED},
}

EDIT_TOOL = {
    "name": "submit_review",
    "description": "Submit the review and the final, improved post.",
    "input_schema": {
        "type": "object",
        "properties": {
            "scores": {
                "type": "object",
                "properties": {k: {"type": "integer", "minimum": 1, "maximum": 10}
                               for k in ("brand_voice", "hook", "specificity", "cta")},
                "required": ["brand_voice", "hook", "specificity", "cta"],
                "description": "Honest 1-10 scores of the FINAL post. Reserve 9-10 for exceptional.",
            },
            "notes": {"type": "array", "items": {"type": "string"}, "description": "What you changed and why, or anything the account manager must check."},
            "post": {"type": "object", "properties": _POST_PROPS, "required": _POST_REQUIRED},
        },
        "required": ["scores", "notes", "post"],
    },
}

WRITE_SYSTEM = """You are a direct-response social copywriter at a digital marketing agency, writing one Facebook +
Instagram post for a client. You write for ONE specific person from the brand profile, at the moment they feel
the pain, in the brand's voice.

Rules:
- The hook names the pain, a surprising truth, or a story in plain words. No "Did you know", no emoji-first openers.
- Prefer a short, concrete story or example over a list of claims. Use the client's real proof, never invented proof.
- One CTA, taken from the profile, stated once, dead simple.
- Sound like the example posts. Follow voice_do/voice_dont. Never use banned words. Obey every compliance rule.
- Instagram and Facebook versions say the same thing; adapt the length and tone, don't just copy.
- Fill slides for carousels/stories and script for reels. When a real clip is provided, write the caption around
  what the clip says and leave ai_image_prompt empty.
Always answer by calling submit_post."""

EDIT_SYSTEM = """You are the senior editor at a digital marketing agency. You review a drafted Facebook + Instagram post
against the client's brand profile before the account manager sees it.

Check, then fix it yourself:
- Would the target customer stop scrolling at the hook? Does it land within the first 125 characters?
- Is every line specific to this business, or could a competitor post it unchanged? Cut the generic.
- Voice matches the profile and examples; no banned words; every compliance rule respected; no invented proof.
- Exactly one clear CTA.
Return the improved post (unchanged fields as they were) and honest scores of the final version.
Always answer by calling submit_review."""


def _clean_tags(tags) -> list[str]:
    out = []
    for t in tags or []:
        t = "#" + re.sub(r"\s+", "", str(t)).lstrip("#")
        if len(t) > 1 and t.lower() not in {x.lower() for x in out}:
            out.append(t)
    return out


def _post_from(data: dict, number: int, plan: PlanItem) -> Post:
    s = lambda k: str(data.get(k) or "").strip()  # noqa: E731
    lst = lambda k: [str(x).strip() for x in (data.get(k) or []) if str(x).strip()]  # noqa: E731
    return Post(
        number=number, plan=plan, title=s("title") or plan.angle[:60], hook=s("hook") or plan.hook,
        instagram_caption=s("instagram_caption"), facebook_caption=s("facebook_caption"),
        hashtags=_clean_tags(data.get("hashtags")), cta=s("cta"), visual_brief=s("visual_brief"),
        ai_image_prompt=s("ai_image_prompt"), on_screen_text=s("on_screen_text"), alt_text=s("alt_text"),
        slides=lst("slides"), script=lst("script"),
    )


def lint_post(post: Post, profile: BrandProfile) -> list[str]:
    """Checks that don't need a model: platform limits and hard brand rules."""
    issues = []
    if not post.instagram_caption or not post.facebook_caption:
        issues.append("Missing a caption for Instagram or Facebook.")
    text = " ".join([post.hook, post.instagram_caption, post.facebook_caption, post.on_screen_text, *post.slides])
    for w in profile.banned_words:
        if w.strip() and re.search(rf"(?<!\w){re.escape(w.strip())}(?!\w)", text, re.IGNORECASE):
            issues.append(f'Uses banned word "{w.strip()}".')
    if len(post.instagram_caption) > IG_CAPTION_LIMIT:
        issues.append(f"Instagram caption is {len(post.instagram_caption)} chars (limit {IG_CAPTION_LIMIT}).")
    first_line = post.instagram_caption.strip().split("\n", 1)[0]
    if len(first_line) > IG_FOLD_CHARS:
        issues.append(f"Instagram first line is {len(first_line)} chars; the hook gets cut at ~{IG_FOLD_CHARS}.")
    if len(post.hashtags) > MAX_HASHTAGS:
        issues.append(f"{len(post.hashtags)} hashtags; keep it to {MAX_HASHTAGS} or fewer.")
    if post.plan.format == "carousel" and len(post.slides) < 3:
        issues.append("Carousel has fewer than 3 slides.")
    if post.plan.format == "reel" and not post.script and not post.clip_file:
        issues.append("Reel has no script and no clip.")
    return issues


def write_post(number: int, plan: PlanItem, profile: BrandProfile, others: list[PlanItem], clips: list[dict],
               client, model: str, on_retry: Callable[[str], None] | None = None) -> Post:
    """Writer drafts, editor improves and scores, then the hard rules are checked."""
    clip = next((c for c in clips if c["clip_number"] == plan.clip), None)
    brief = (f"Brand profile:\n{profile.to_prompt()}\n\nThis post:\n{json.dumps(asdict(plan), indent=2)}\n\n"
             "Other posts this week (don't repeat their angles):\n"
             + "\n".join(f"- {o.day} {o.format}: {o.angle}" for o in others if o is not plan))
    if clip:
        brief += (f"\n\nThis reel uses a finished clip. Title: {clip['title']}\nIt opens with: {clip['hook']}\n"
                  f"Clip summary: {clip['caption']}")

    draft = call_tool(client, model, WRITE_SYSTEM, brief, WRITE_TOOL, on_retry)
    review = call_tool(client, model, EDIT_SYSTEM,
                       brief + f"\n\nDraft to review:\n{json.dumps(draft, indent=2, ensure_ascii=False)}",
                       EDIT_TOOL, on_retry)
    post = _post_from(review.get("post") or draft, number, plan)
    post.scores = {k: int(v) for k, v in (review.get("scores") or {}).items() if isinstance(v, (int, float))}
    post.editor_notes = [str(n).strip() for n in review.get("notes") or [] if str(n).strip()]
    if clip:
        post.clip_file = clip["file"]
    post.warnings = lint_post(post, profile)
    return post
