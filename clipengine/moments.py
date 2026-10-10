"""Pick the best standalone moments with Claude, snapped to sentence boundaries."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, asdict
from typing import Callable

from clipengine.config import ClipEngineError, fmt_ts

CHUNK_CHARS = 120_000       # transcript characters per Claude request (~30k tokens)
MAX_ATTEMPTS = 4
PAD_BEFORE = 0.15           # seconds of breathing room, never crossing into the neighbouring sentence
PAD_AFTER = 0.30
_ABBREVIATIONS = {"mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "st.", "vs.", "etc.", "inc.", "no."}


@dataclass
class Sentence:
    idx: int
    start: float
    end: float
    text: str
    words: list[dict] = field(default_factory=list)


@dataclass
class Moment:
    start: float
    end: float
    hook: str
    title: str
    virality_score: int
    reason: str
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    start_sentence: int = 0
    end_sentence: int = 0

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"], d["end"] = round(self.start, 2), round(self.end, 2)
        d["duration"] = round(self.duration, 2)
        return d


# --------------------------------------------------------------------------- sentences

def build_sentences(words: list[dict], pause_break: float = 1.2) -> list[Sentence]:
    """Group words into sentences using end punctuation, and long pauses as a fallback."""
    sentences: list[Sentence] = []
    cur: list[dict] = []

    def flush():
        if cur:
            sentences.append(Sentence(
                idx=len(sentences), start=cur[0]["start"], end=cur[-1]["end"],
                text=" ".join(w["word"] for w in cur), words=list(cur),
            ))
            cur.clear()

    for i, w in enumerate(words):
        cur.append(w)
        tok = w["word"].lower()
        ends = tok.rstrip("\"')]”’").endswith((".", "?", "!", "…")) and tok not in _ABBREVIATIONS
        gap = (words[i + 1]["start"] - w["end"]) if i + 1 < len(words) else 0
        if ends or gap >= pause_break:
            flush()
    flush()
    return sentences


def chunk_sentences(sentences: list[Sentence], max_chars: int = CHUNK_CHARS) -> list[list[Sentence]]:
    chunks, cur, size = [], [], 0
    for s in sentences:
        line = len(s.text) + 30
        if cur and size + line > max_chars:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(s)
        size += line
    if cur:
        chunks.append(cur)
    return chunks


# --------------------------------------------------------------------------- prompt

TOOL = {
    "name": "submit_moments",
    "description": "Submit the selected short-form clip moments.",
    "input_schema": {
        "type": "object",
        "properties": {
            "moments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start_sentence": {"type": "integer", "description": "Index of the first sentence of the clip."},
                        "end_sentence": {"type": "integer", "description": "Index of the last sentence of the clip (inclusive)."},
                        "hook": {"type": "string", "description": "The attention-grabbing opening line of the clip."},
                        "title": {"type": "string", "description": "Short clip title, max 8 words."},
                        "virality_score": {"type": "integer", "minimum": 1, "maximum": 10},
                        "reason": {"type": "string", "description": "One line explaining the score."},
                        "caption": {"type": "string", "description": "Ready-to-post social caption, 1-2 sentences, no hashtags."},
                        "hashtags": {"type": "array", "items": {"type": "string"}, "description": "4-6 relevant hashtags."},
                    },
                    "required": ["start_sentence", "end_sentence", "hook", "title",
                                 "virality_score", "reason", "caption", "hashtags"],
                },
            }
        },
        "required": ["moments"],
    },
}

SYSTEM = """You are an expert short-form video editor for TikTok, Instagram Reels and YouTube Shorts.
You are given a numbered, timestamped transcript of a long video. Pick the moments that would work best
as standalone vertical clips for a cold audience.

Rules:
- Each moment is a contiguous range of whole sentences (start_sentence..end_sentence, inclusive), so it
  always starts and ends at a natural sentence boundary, never mid-sentence.
- Each moment must run between {min_len} and {max_len} seconds (use the timestamps to check).
- Each moment must make sense on its own with no prior context: a clear idea, story beat, tip, bold claim,
  surprising fact or emotional peak. Prefer ones that open with a strong hook and end on a payoff.
- Moments must not overlap each other.
- hook: the opening line, punchy and curiosity-driven. Use the first sentence of the clip, tightened only if needed.
- virality_score: honest 1-10. Do not give everything an 8. Reserve 9-10 for exceptional moments.
- caption: a ready-to-post caption in the speaker's voice; hashtags: 4-6, relevant to the topic, no spaces.
Always answer by calling submit_moments."""


def render_transcript(sentences: list[Sentence]) -> str:
    return "\n".join(f"[{s.idx}] ({s.start:.1f}s-{s.end:.1f}s) {s.text}" for s in sentences)


# --------------------------------------------------------------------------- validation

def _span(sentences: list[Sentence], a: int, b: int) -> float:
    return sentences[b].end - sentences[a].start


def validate_moments(raw: list[dict], sentences: list[Sentence], min_len: float, max_len: float,
                     video_duration: float, lo: int | None = None, hi: int | None = None) -> list[Moment]:
    """Validate/repair raw model output. Invalid items are dropped; overlaps resolved by score."""
    by_idx = {s.idx: s for s in sentences}
    lo = sentences[0].idx if lo is None else lo
    hi = sentences[-1].idx if hi is None else hi
    ok: list[Moment] = []

    for item in raw:
        try:
            a, b = int(item["start_sentence"]), int(item["end_sentence"])
            score = int(round(float(item["virality_score"])))
            hook, title = str(item["hook"]).strip(), str(item["title"]).strip()
            reason = str(item.get("reason", "")).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not (lo <= a <= b <= hi) or a not in by_idx or b not in by_idx or not hook or not title:
            continue
        # Repair durations by trimming or extending whole sentences.
        while b > a and _span(sentences, a, b) > max_len:
            b -= 1
        while _span(sentences, a, b) < min_len and b < hi:
            b += 1
        while _span(sentences, a, b) > max_len and b > a:
            b -= 1
        dur = _span(sentences, a, b)
        if dur < min_len or dur > max_len:
            continue

        start = sentences[a].start - min(PAD_BEFORE, max(0.0, sentences[a].start - (sentences[a - 1].end if a > 0 else 0.0)) / 2)
        nxt = sentences[b + 1].start if b + 1 < len(sentences) else video_duration
        end = min(sentences[b].end + min(PAD_AFTER, max(0.0, nxt - sentences[b].end) / 2), video_duration)
        tags = [("#" + str(t).strip().lstrip("#").replace(" ", "")) for t in (item.get("hashtags") or []) if str(t).strip()]
        ok.append(Moment(
            start=max(0.0, start), end=end, hook=hook, title=title,
            virality_score=max(1, min(10, score)), reason=reason,
            caption=str(item.get("caption", "")).strip(), hashtags=tags[:8],
            start_sentence=a, end_sentence=b,
        ))

    # Resolve overlaps, keeping higher scores.
    ok.sort(key=lambda m: (-m.virality_score, m.start))
    kept: list[Moment] = []
    for m in ok:
        if all(m.end_sentence < k.start_sentence or m.start_sentence > k.end_sentence for k in kept):
            kept.append(m)
    return kept


# --------------------------------------------------------------------------- Claude call

def _call_claude(client, model: str, system: str, user: str, on_retry: Callable[[str], None] | None):
    import anthropic

    delay = 2.0
    last: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.messages.create(
                model=model, max_tokens=8000, system=system,
                tools=[TOOL], tool_choice={"type": "tool", "name": "submit_moments"},
                messages=[{"role": "user", "content": user}],
            )
            for block in resp.content:
                if block.type == "tool_use" and block.name == "submit_moments":
                    return block.input.get("moments", [])
            raise ValueError("model did not return structured moments")
        except anthropic.AuthenticationError as e:
            raise ClipEngineError("Anthropic API key was rejected. Check ANTHROPIC_API_KEY in your .env.") from e
        except anthropic.NotFoundError as e:
            raise ClipEngineError(f"Model '{model}' was not found. Check CLIPENGINE_MODEL in your .env.") from e
        except anthropic.BadRequestError as e:
            raise ClipEngineError(f"Claude API rejected the request: {e}") from e
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APIStatusError, ValueError) as e:
            last = e
            if attempt == MAX_ATTEMPTS:
                break
            if on_retry:
                on_retry(f"Claude API error ({type(e).__name__}); retrying in {delay:.0f}s "
                         f"(attempt {attempt}/{MAX_ATTEMPTS - 1})")
            time.sleep(delay)
            delay *= 2
    raise ClipEngineError(f"Claude API failed after {MAX_ATTEMPTS} attempts: {last}")


def pick_moments(
    transcript: dict,
    api_key: str | None,
    model: str,
    clips: int = 8,
    min_len: float = 20,
    max_len: float = 60,
    on_progress: Callable[[float], None] | None = None,
    on_retry: Callable[[str], None] | None = None,
    client=None,
) -> list[Moment]:
    """Return up to `clips` moments, sorted chronologically."""
    if client is None:
        if not api_key:
            raise ClipEngineError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")
        import anthropic
        client = anthropic.Anthropic(api_key=api_key, max_retries=0, timeout=120)

    sentences = build_sentences(transcript["words"])
    if not sentences:
        raise ClipEngineError("Transcript is empty.")
    duration = transcript.get("duration") or sentences[-1].end
    chunks = chunk_sentences(sentences)
    per_chunk = clips if len(chunks) == 1 else max(3, math.ceil(clips * 1.5 / len(chunks)))

    system = SYSTEM.format(min_len=int(min_len), max_len=int(max_len))
    found: list[Moment] = []
    for i, chunk in enumerate(chunks):
        user = (
            f"Pick the {per_chunk} best moments (fewer only if the content truly doesn't have that many "
            f"good ones). Total video length: {fmt_ts(duration)}.\n\nTranscript:\n{render_transcript(chunk)}"
        )
        raw = _call_claude(client, model, system, user, on_retry)
        valid = validate_moments(raw, sentences, min_len, max_len, duration, chunk[0].idx, chunk[-1].idx)
        if not valid:
            # One more try with a nudge before giving up on this chunk.
            raw = _call_claude(client, model, system,
                               user + f"\n\nIMPORTANT: every moment must last {int(min_len)}-{int(max_len)} seconds "
                                      f"and use valid sentence indices {chunk[0].idx}-{chunk[-1].idx}.", on_retry)
            valid = validate_moments(raw, sentences, min_len, max_len, duration, chunk[0].idx, chunk[-1].idx)
        found.extend(valid)
        if on_progress:
            on_progress((i + 1) / len(chunks))

    if not found:
        raise ClipEngineError(
            "Claude did not return any valid moments. Try different --min-len/--max-len values or a different model."
        )
    found.sort(key=lambda m: (-m.virality_score, m.start))
    top = found[:clips]
    top.sort(key=lambda m: m.start)
    return top
