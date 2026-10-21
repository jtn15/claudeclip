"""socialcrew command line interface."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from socialcrew import __version__
from socialcrew.agents import load_clips
from socialcrew.brand import draft_profile, fetch_site_text, load_profile, profile_path, save_profile
from socialcrew.config import SocialCrewError, load_settings
from socialcrew.llm import make_client
from socialcrew.pack import parse_week, run_week

console = Console()


def warn(msg: str) -> None:
    console.print(f"[yellow]{msg}[/yellow]")


def fail(e: SocialCrewError) -> None:
    console.print(f"[bold red]Error:[/bold red] {e}")
    sys.exit(1)


def read_text_arg(value: str | None) -> str:
    """Accept either inline text or a path to a text file."""
    if not value:
        return ""
    p = Path(value)
    return p.read_text(encoding="utf-8") if p.is_file() else value


@click.group()
@click.version_option(__version__, prog_name="socialcrew")
def main():
    """socialcrew: a team of agents that plans and writes on-brand Facebook + Instagram content per client."""


@main.command()
@click.option("--client", required=True, help='Client name, e.g. "Acme Roofing".')
@click.option("--website", help="Client website to learn the business from.")
@click.option("--notes", help="Your notes (inline text or a path to a .txt/.md file): offers, voice, do's and don'ts.")
@click.option("--force", is_flag=True, help="Overwrite an existing brand profile.")
def onboard(client, website, notes, force):
    """Draft a brand profile for a new client. Review and edit the YAML it writes before running a week."""
    try:
        settings = load_settings()
        path = profile_path(settings.brands_dir, client)
        if path.exists() and not force:
            raise SocialCrewError(f"{path} already exists. Edit it directly, or pass --force to redraft it.")
        api = make_client(settings.anthropic_api_key)
        site = ""
        if website:
            with console.status(f"Reading {website}"):
                site = fetch_site_text(website)
        with console.status("Brand strategist is drafting the profile"):
            profile = draft_profile(client, site, read_text_arg(notes), api, settings.claude_model, warn, website or "")
        path = save_profile(settings.brands_dir, profile)
    except SocialCrewError as e:
        fail(e)
    console.print(f"[bold green]Brand profile drafted:[/bold green] {path.resolve()}")
    console.print("Open it and fix anything wrong: offers, proof, voice, banned words. Paste 2-3 of the client's best "
                  "past posts into example_posts. The better this file, the better every post.")


@main.command()
@click.option("--client", required=True, help="Client name (must have a brand profile).")
@click.option("--posts", "count", default=5, show_default=True, type=click.IntRange(1, 14), help="Posts to create.")
@click.option("--week", help="Any date in the target week (default: next week).")
@click.option("--focus", help="This week's promos, events, seasonal angle (inline text or a file path).")
@click.option("--clips-dir", type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="A clipengine output folder; reels get written around those clips.")
def week(client, count, week, focus, clips_dir):
    """Plan, write and edit a week of content for CLIENT, ready for your approval."""
    try:
        settings = load_settings()
        profile = load_profile(settings.brands_dir, client)
        target = parse_week(week)
        clips = load_clips(clips_dir) if clips_dir else []
        api = make_client(settings.anthropic_api_key)
        with console.status("Working") as st:
            result = run_week(profile, target, count, read_text_arg(focus), clips, settings.output_dir, api,
                              settings.claude_model, on_status=lambda s: (st.update(s), console.log(s)),
                              on_retry=warn)
    except SocialCrewError as e:
        fail(e)

    console.print()
    console.rule(f"[bold green]{result.client}: week of {result.week:%b %d}")
    table = Table(show_lines=False)
    for col in ("#", "Day", "Format", "Score", "Hook"):
        table.add_column(col, overflow="fold")
    for p in result.posts:
        flag = " [yellow]⚠[/yellow]" if p.warnings else ""
        table.add_row(str(p.number), p.plan.day, p.plan.format, f"{p.score}{flag}", p.hook)
    console.print(table)
    console.print(f"Review and approve: [bold cyan]{(result.out_dir / 'content_pack.md').resolve()}[/bold cyan]")
    if result.failed:
        warn(f"{len(result.failed)} post(s) failed to write; re-run to retry.")
    sys.exit(1 if result.failed else 0)


@main.command()
@click.option("--client", required=True)
@click.argument("lesson")
def learn(client, lesson):
    """Record what worked or flopped (e.g. "Before/after carousels got 3x saves") so the crew uses it next time."""
    try:
        settings = load_settings()
        profile = load_profile(settings.brands_dir, client)
        profile.learnings.append(lesson.strip())
        path = save_profile(settings.brands_dir, profile)
    except SocialCrewError as e:
        fail(e)
    console.print(f"Saved to {path} ({len(profile.learnings)} learnings).")


if __name__ == "__main__":
    main()
