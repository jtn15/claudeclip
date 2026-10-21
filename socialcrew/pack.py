"""Run the crew for one client-week and write the content pack you review and approve."""

from __future__ import annotations

import csv
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from clipengine.config import safe_dirname
from socialcrew.agents import DAYS, PlanItem, Post, plan_week, write_post
from socialcrew.brand import BrandProfile
from socialcrew.config import SocialCrewError

WRITERS = 4   # posts written in parallel


@dataclass
class WeekResult:
    client: str
    week: date
    out_dir: Path
    posts: list[Post]
    failed: list[tuple[PlanItem, str]] = field(default_factory=list)


def next_monday(today: date | None = None) -> date:
    today = today or date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def parse_week(value: str | None) -> date:
    if not value:
        return next_monday()
    try:
        d = date.fromisoformat(value)
    except ValueError as e:
        raise SocialCrewError(f"--week must be a date like 2026-10-26, got '{value}'.") from e
    return d - timedelta(days=d.weekday())


def post_date(week: date, day: str) -> date:
    return week + timedelta(days=DAYS.index(day))


def run_week(profile: BrandProfile, week: date, count: int, focus: str, clips: list[dict], output_dir: Path,
             client, model: str, on_status: Callable[[str], None] | None = None,
             on_retry: Callable[[str], None] | None = None) -> WeekResult:
    status = on_status or (lambda s: None)
    status(f"Strategist is planning {count} posts")
    plan = plan_week(profile, count, focus, clips, client, model, on_retry)

    posts: list[Post] = []
    failed: list[tuple[PlanItem, str]] = []
    with ThreadPoolExecutor(max_workers=WRITERS) as pool:
        futures = {pool.submit(write_post, i, p, profile, plan, clips, client, model, on_retry): p
                   for i, p in enumerate(plan, start=1)}
        for fut in as_completed(futures):
            try:
                posts.append(fut.result())
                status(f"Wrote + edited {len(posts)}/{len(plan)}: {posts[-1].title}")
            except SocialCrewError as e:
                failed.append((futures[fut], str(e)))
                status(f"[yellow]Failed: {futures[fut].angle}[/yellow]")
    if not posts:
        raise SocialCrewError("Every post failed:\n" + "\n".join(msg for _, msg in failed))
    posts.sort(key=lambda p: p.number)

    out_dir = output_dir / safe_dirname(profile.client) / week.isoformat()
    write_pack(out_dir, profile, week, focus, model, posts, failed)
    return WeekResult(profile.client, week, out_dir, posts, failed)


# --------------------------------------------------------------------------- output files

def _section(post: Post, week: date) -> str:
    p = post.plan
    lines = [
        f"## {post.number}. {post.title}",
        "",
        f"**{p.day} {post_date(week, p.day):%b %d}** · {p.format} · {p.pillar} · goal: {p.objective} · "
        f"editor score {post.score}/10",
        "",
        "- [ ] Approved",
        "- [ ] Needs changes: ______________________",
        "",
        f"> **Why this post:** {p.why}",
        "",
    ]
    if post.warnings:
        lines += ["**⚠ Check before approving:**", *[f"- {w}" for w in post.warnings], ""]
    if post.clip_file:
        lines += [f"**Video:** `{post.clip_file}`", ""]
    lines += ["### Instagram", "", post.instagram_caption, "", " ".join(post.hashtags), "",
              "### Facebook", "", post.facebook_caption, ""]
    lines += ["### Visual", "", f"**Brief:** {post.visual_brief}"]
    if post.on_screen_text:
        lines.append(f"\n**On-screen text:** {post.on_screen_text}")
    if post.ai_image_prompt:
        lines.append(f"\n**AI image prompt:** {post.ai_image_prompt}")
    lines.append(f"\n**Alt text:** {post.alt_text}\n")
    if post.slides:
        lines += ["**Slides / frames:**", *[f"{i}. {s}" for i, s in enumerate(post.slides, 1)], ""]
    if post.script:
        lines += ["**Reel script:**", *[f"- {b}" for b in post.script], ""]
    if post.editor_notes:
        lines += ["<details><summary>Editor notes</summary>", "", *[f"- {n}" for n in post.editor_notes], "",
                  "</details>", ""]
    return "\n".join(lines)


def build_pack_md(profile: BrandProfile, week: date, posts: list[Post], failed: list[tuple[PlanItem, str]]) -> str:
    head = [
        f"# {profile.client}: content for the week of {week:%B %d, %Y}",
        "",
        "Tick a box on each post, then schedule the approved ones in Meta Business Suite. "
        "Add anything you learn to `learnings` in the brand profile (`socialcrew learn`) so next week is better.",
        "",
        "| # | Day | Format | Pillar | Hook | Score |",
        "|---|---|---|---|---|---|",
        *[f"| {p.number} | {p.plan.day} | {p.plan.format} | {p.plan.pillar} | {p.hook.replace('|', '/')} | "
          f"{p.score}{' ⚠' if p.warnings else ''} |" for p in posts],
        "",
    ]
    if failed:
        head += ["**Not written (re-run to retry):**", *[f"- {p.day} {p.format}: {p.angle} ({msg.splitlines()[0]})"
                                                       for p, msg in failed], ""]
    return "\n".join(head) + "\n---\n\n" + "\n\n---\n\n".join(_section(p, week) for p in posts) + "\n"


def write_pack(out_dir: Path, profile: BrandProfile, week: date, focus: str, model: str,
               posts: list[Post], failed: list[tuple[PlanItem, str]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "content_pack.md").write_text(build_pack_md(profile, week, posts, failed), encoding="utf-8")
    payload = {
        "client": profile.client,
        "week_of": week.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "focus": focus,
        "posts": [p.to_dict() | {"date": post_date(week, p.plan.day).isoformat()} for p in posts],
    }
    (out_dir / "posts.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    with (out_dir / "posts.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["number", "date", "day", "format", "pillar", "objective", "hook", "instagram_caption",
                    "hashtags", "facebook_caption", "cta", "visual_brief", "ai_image_prompt", "clip_file",
                    "score", "warnings"])
        for p in posts:
            w.writerow([p.number, post_date(week, p.plan.day).isoformat(), p.plan.day, p.plan.format, p.plan.pillar,
                        p.plan.objective, p.hook, p.instagram_caption, " ".join(p.hashtags), p.facebook_caption,
                        p.cta, p.visual_brief, p.ai_image_prompt, p.clip_file, p.score, " | ".join(p.warnings)])
