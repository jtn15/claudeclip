"""Client brand profiles: the shared memory every agent writes against.

A profile is a YAML file in brands/ that you own and edit. The onboarding agent drafts the first version
from the client's website and your notes; after that, every edit (a new offer, a phrase the client hates,
a lesson from last month's numbers) makes every future post better.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

import yaml

from clipengine.config import slugify
from socialcrew.config import SocialCrewError
from socialcrew.llm import call_tool

MAX_SITE_CHARS = 40_000


@dataclass
class BrandProfile:
    client: str
    business: str = ""                 # what they do, in one or two sentences
    location: str = ""                 # service area; drives local references
    website: str = ""
    offers: list[str] = field(default_factory=list)
    audience: str = ""                 # who buys, described as a real person
    pains: list[str] = field(default_factory=list)       # the felt frustrations, in the customer's words
    desires: list[str] = field(default_factory=list)     # the outcome they actually want
    proof: list[str] = field(default_factory=list)       # reviews, years in business, numbers, guarantees
    voice: str = ""
    voice_do: list[str] = field(default_factory=list)
    voice_dont: list[str] = field(default_factory=list)
    banned_words: list[str] = field(default_factory=list)
    content_pillars: list[dict] = field(default_factory=list)  # [{name, description}]
    ctas: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    compliance: list[str] = field(default_factory=list)  # claims we must never make, required disclaimers
    example_posts: list[str] = field(default_factory=list)  # approved posts that nailed the voice
    learnings: list[str] = field(default_factory=list)      # what worked / flopped; you add these over time

    def to_prompt(self) -> str:
        """Brand brief handed to every agent."""
        d = {k: v for k, v in asdict(self).items() if v}
        return yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=110)


def profile_path(brands_dir: Path, client: str) -> Path:
    return brands_dir / f"{slugify(client)}.yaml"


def load_profile(brands_dir: Path, client: str) -> BrandProfile:
    path = profile_path(brands_dir, client)
    if not path.exists():
        raise SocialCrewError(
            f"No brand profile for '{client}' at {path}. Create one with:\n"
            f'  socialcrew onboard --client "{client}" --website https://...'
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise SocialCrewError(f"{path} is not valid YAML: {e}") from e
    known = {f.name for f in fields(BrandProfile)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise SocialCrewError(f"{path} has unknown field(s): {', '.join(unknown)}")
    data.setdefault("client", client)
    return BrandProfile(**data)


def save_profile(brands_dir: Path, profile: BrandProfile) -> Path:
    brands_dir.mkdir(parents=True, exist_ok=True)
    path = profile_path(brands_dir, profile.client)
    path.write_text(yaml.safe_dump(asdict(profile), sort_keys=False, allow_unicode=True, width=110),
                    encoding="utf-8")
    return path


# --------------------------------------------------------------------------- website text

class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    return re.sub(r"\s+", " ", " ".join(p.parts)).strip()


def fetch_site_text(url: str) -> str:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (socialcrew brand onboarding)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read(2_000_000).decode(resp.headers.get_content_charset() or "utf-8", "replace")
    except (urllib.error.URLError, ValueError, TimeoutError) as e:
        raise SocialCrewError(f"Could not fetch {url}: {e}") from e
    return html_to_text(html)[:MAX_SITE_CHARS]


# --------------------------------------------------------------------------- onboarding agent

_LIST = {"type": "array", "items": {"type": "string"}}

ONBOARD_TOOL = {
    "name": "submit_brand_profile",
    "description": "Submit the drafted brand profile.",
    "input_schema": {
        "type": "object",
        "properties": {
            "business": {"type": "string"},
            "location": {"type": "string"},
            "offers": _LIST,
            "audience": {"type": "string", "description": "The buyer as one specific person: who, situation, moment they buy."},
            "pains": {**_LIST, "description": "5-8 felt frustrations in the customer's own words."},
            "desires": {**_LIST, "description": "3-6 outcomes they actually want."},
            "proof": {**_LIST, "description": "Only proof stated in the source material. Never invent."},
            "voice": {"type": "string"},
            "voice_do": _LIST,
            "voice_dont": _LIST,
            "banned_words": _LIST,
            "content_pillars": {
                "type": "array",
                "items": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
                          "required": ["name", "description"]},
                "description": "4-5 recurring themes, e.g. education, proof, behind the scenes, offer, community.",
            },
            "ctas": {**_LIST, "description": "3-5 concrete next steps (call, book, DM a keyword...)."},
            "hashtags": {**_LIST, "description": "8-15 niche + local hashtags, with #."},
            "compliance": {**_LIST, "description": "Claims to avoid for this industry (guarantees, licensing, health, pricing)."},
        },
        "required": ["business", "offers", "audience", "pains", "desires", "voice", "voice_do", "voice_dont",
                     "content_pillars", "ctas", "hashtags", "compliance"],
    },
}

ONBOARD_SYSTEM = """You are the brand strategist at a digital marketing agency. From a client's website text and the
account manager's notes, draft the brand profile that copywriters will use to write their Facebook and Instagram
content.

Rules:
- Be specific to THIS business. "Quality service" and "customer satisfaction" are useless; find what is actually
  different about them.
- Pains are the real, felt frustration behind the purchase, written the way a customer would say it out loud.
- proof: only facts present in the material (reviews, years, counts, certifications). Never invent numbers.
- banned_words: generic marketing filler this brand must never use, plus anything the notes forbid.
- If the material is thin, make careful, conservative inferences; the account manager will edit the file.
Always answer by calling submit_brand_profile."""


def draft_profile(client_name: str, site_text: str, notes: str, client, model: str,
                  on_retry: Callable[[str], None] | None = None, website: str = "") -> BrandProfile:
    if not site_text.strip() and not notes.strip():
        raise SocialCrewError("Give the onboarding agent something to work with: --website and/or --notes.")
    user = (f"Client: {client_name}\n\nAccount manager notes:\n{notes or '(none)'}\n\n"
            f"Website text:\n{site_text or '(none)'}")
    data = call_tool(client, model, ONBOARD_SYSTEM, user, ONBOARD_TOOL, on_retry)
    known = {f.name for f in fields(BrandProfile)}
    clean = {k: v for k, v in data.items() if k in known and k != "client"}
    return BrandProfile(client=client_name, website=website, **clean)
