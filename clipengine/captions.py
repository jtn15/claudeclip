"""Word-by-word animated captions (ASS subtitles) and the ready-to-paste captions.txt."""

from __future__ import annotations

import re
from pathlib import Path

from clipengine.config import OUT_H, OUT_W, CaptionStyle, ClipEngineError, fmt_ts

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
_SENTENCE_END = (".", "?", "!", "…")


def ass_color(hex_color: str) -> str:
    m = _HEX_RE.match(hex_color.strip())
    if not m:
        raise ClipEngineError(f"Invalid color '{hex_color}'. Use hex like #FFFFFF.")
    rgb = m.group(1)
    r, g, b = rgb[0:2], rgb[2:4], rgb[4:6]
    return f"&H00{b}{g}{r}".upper()


def _ts(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def effective_max_chars(style: CaptionStyle) -> int:
    if style.max_chars:
        return style.max_chars
    usable = OUT_W - 140
    return max(8, int(usable / (style.font_size * 0.66)))


def group_words(words: list[dict], max_words: int, max_chars: int) -> list[list[dict]]:
    """Split words into on-screen groups of 2-4 words, breaking at punctuation and pauses."""
    max_words = max(1, min(max_words, 4))
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for i, w in enumerate(words):
        cur.append(w)
        text = w["word"]
        chars = sum(len(x["word"]) for x in cur) + len(cur) - 1
        nxt = words[i + 1] if i + 1 < len(words) else None
        next_chars = chars + 1 + len(nxt["word"]) if nxt else 0
        pause = nxt is not None and nxt["start"] - w["end"] > 0.6
        brk = (
            nxt is None
            or len(cur) >= max_words
            or next_chars > max_chars
            or text.endswith(_SENTENCE_END)
            or (text.endswith((",", ";", ":")) and len(cur) >= 2)
            or pause
        )
        if brk:
            groups.append(cur)
            cur = []
    return groups


def _clean(word: str, upper: bool) -> str:
    word = word.replace("{", "(").replace("}", ")").replace("\\", "")
    return word.upper() if upper else word


def build_ass(words: list[dict], clip_start: float, clip_end: float, style: CaptionStyle) -> str:
    """Build an ASS file for one clip. `words` are absolute (source-video) timestamps."""
    clip_words = [
        w for w in words if clip_start <= (w["start"] + w["end"]) / 2 <= clip_end and w["word"].strip()
    ]
    primary = ass_color(style.color)
    hilite = ass_color(style.highlight_color)
    outline = ass_color(style.outline_color)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OUT_W}
PlayResY: {OUT_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{style.font},{style.font_size},{primary},{primary},{outline},&H80000000,-1,0,0,0,100,100,1,0,1,{style.outline},3,2,70,70,{style.margin_bottom},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    groups = group_words(clip_words, style.max_words, effective_max_chars(style))
    for gi, group in enumerate(groups):
        next_group_start = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else None
        for wi, w in enumerate(group):
            begin = max(w["start"], clip_start) - clip_start
            if wi + 1 < len(group):
                end = group[wi + 1]["start"] - clip_start
            else:
                end = w["end"] + 0.25 - clip_start
                if next_group_start is not None:
                    end = min(end, next_group_start - clip_start)
            end = min(end, clip_end - clip_start)
            if end - begin < 0.05:
                end = begin + 0.05
            parts = []
            for wj, x in enumerate(group):
                txt = _clean(x["word"], style.uppercase)
                if wj == wi:
                    parts.append(
                        f"{{\\1c{hilite}\\fscx82\\fscy82\\t(0,90,\\fscx112\\fscy112)}}{txt}"
                        f"{{\\1c{primary}\\fscx100\\fscy100}}"
                    )
                else:
                    parts.append(txt)
            lines.append(f"Dialogue: 0,{_ts(begin)},{_ts(end)},Cap,,0,0,0,,{' '.join(parts)}")
    return header + "\n".join(lines) + "\n"


def write_ass(path: Path, words: list[dict], clip_start: float, clip_end: float, style: CaptionStyle) -> bool:
    """Write the ASS file. Returns False if the clip has no words (nothing to caption)."""
    content = build_ass(words, clip_start, clip_end, style)
    if "Dialogue:" not in content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def build_captions_txt(video_title: str, client: str, clips: list[dict]) -> str:
    """clips: dicts with number, filename, moment (Moment). Chronological order."""
    out = [f"SOCIAL CAPTIONS: {video_title}", f"Client: {client}", "=" * 60, ""]
    for c in clips:
        m = c["moment"]
        out += [
            f"{c['filename']}  |  {fmt_ts(m.start)}-{fmt_ts(m.end)}  |  virality {m.virality_score}/10",
            f"Title: {m.title}",
            f"Hook:  {m.hook}",
            "",
            m.caption or m.hook,
            "",
            " ".join(m.hashtags),
            "",
            "-" * 60,
            "",
        ]
    return "\n".join(out)
