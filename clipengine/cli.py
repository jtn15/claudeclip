"""clipengine command line interface."""

from __future__ import annotations

import sys
import time

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from clipengine import __version__
from clipengine.config import CaptionStyle, ClipEngineError, check_ffmpeg, fmt_ts, load_settings
from clipengine.downloader import is_url, list_videos
from clipengine.pipeline import RunOptions, VideoResult, process_video

console = Console()

RIGHTS_TEXT = "I confirm I own this content or have permission to repurpose it"


def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(), TextColumn("[bold]{task.description}"), BarColumn(),
        TaskProgressColumn(), TimeElapsedColumn(), console=console, transient=False,
    )


def common_options(f):
    opts = [
        click.option("--client", required=True, help='Client name, used as the output folder, e.g. "Acme Roofing".'),
        click.option("--confirm-rights", is_flag=True, help="Confirm you own this content or have permission to use it."),
        click.option("--clips", default=8, show_default=True, type=int, help="Max number of clips to create."),
        click.option("--min-len", default=20.0, show_default=True, type=float, help="Minimum clip length (seconds)."),
        click.option("--max-len", default=60.0, show_default=True, type=float, help="Maximum clip length (seconds)."),
        click.option("--smart-crop", is_flag=True, help="Keep the speaker's face in frame (OpenCV); falls back to center crop."),
        click.option("--no-captions", is_flag=True, help="Skip burned-in captions."),
        click.option("--font", default="Arial", show_default=True, help="Caption font name (must be installed, or use --fonts-dir)."),
        click.option("--fonts-dir", type=click.Path(exists=True, file_okay=False), help="Folder with extra .ttf/.otf fonts."),
        click.option("--font-size", default=96, show_default=True, type=int, help="Caption font size (for a 1080x1920 frame)."),
        click.option("--caption-color", default="#FFFFFF", show_default=True, help="Caption text color (hex)."),
        click.option("--highlight-color", default="#FFE600", show_default=True, help="Color of the word being spoken (hex)."),
        click.option("--caption-words", default=3, show_default=True, type=click.IntRange(1, 4), help="Max words on screen at once."),
        click.option("--refresh-transcript", is_flag=True, help="Ignore the cached transcript and re-transcribe."),
        click.option("--allow-long", is_flag=True, help="Allow videos longer than the length limit (default 4h)."),
        click.option("--output-dir", type=click.Path(file_okay=False), help="Output root (default: ./output or CLIPENGINE_OUTPUT_DIR)."),
    ]
    for o in reversed(opts):
        f = o(f)
    return f


def build_options(kw: dict) -> RunOptions:
    style = CaptionStyle(
        font=kw["font"], font_size=kw["font_size"], color=kw["caption_color"],
        highlight_color=kw["highlight_color"], max_words=kw["caption_words"], fonts_dir=kw["fonts_dir"],
    )
    return RunOptions(
        client=kw["client"], clips=kw["clips"], min_len=kw["min_len"], max_len=kw["max_len"],
        smart_crop=kw["smart_crop"], captions=not kw["no_captions"], caption_style=style,
        refresh_transcript=kw["refresh_transcript"], allow_long=kw["allow_long"],
    )


def confirm_rights(flag: bool) -> bool:
    if flag:
        return True
    if sys.stdin.isatty():
        return click.confirm(RIGHTS_TEXT + "?", default=False)
    return False


def startup(kw: dict):
    """Environment checks that should fail fast, before any slow work."""
    check_ffmpeg()
    settings = load_settings()
    if kw.get("output_dir"):
        from pathlib import Path
        settings.output_dir = Path(kw["output_dir"])
    if not settings.anthropic_api_key:
        raise ClipEngineError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")
    opts = build_options(kw)
    if not confirm_rights(kw["confirm_rights"]):
        raise ClipEngineError(
            "Rights not confirmed. clipengine only works on content you own or have permission to use. "
            "Re-run with --confirm-rights to confirm."
        )
    opts.rights_confirmed = True
    return settings, opts


def print_summary(result: VideoResult) -> None:
    console.print()
    console.rule(f"[bold green]Done: {result.title}")
    console.print(f"Clips created: [bold]{len(result.clips)}[/bold]   "
                  f"Source length: {fmt_ts(result.duration)}   "
                  f"Transcript: {'cached' if result.transcript_cached else 'new'}")
    console.print(f"Output folder: [bold cyan]{result.out_dir.resolve()}[/bold cyan]")
    table = Table(title="Top clips by virality score", show_lines=False)
    for col in ("Score", "File", "Time", "Hook"):
        table.add_column(col, overflow="fold")
    for c in result.top(3):
        m = c.moment
        table.add_row(f"{m.virality_score}/10", c.path.name, f"{fmt_ts(m.start)}-{fmt_ts(m.end)}", m.hook)
    console.print(table)
    if result.failed:
        console.print(f"[yellow]{len(result.failed)} clip(s) failed to render:[/yellow]")
        for n, msg in result.failed:
            console.print(f"  clip {n}: {msg}")


@click.group()
@click.version_option(__version__, prog_name="clipengine")
def main():
    """clipengine: turn long-form videos you own into short-form vertical clips."""


@main.command()
@click.argument("input", metavar="INPUT")
@common_options
def run(input, **kw):
    """Process one video. INPUT is a local file path or a URL to a video you own."""
    try:
        settings, opts = startup(kw)
        with make_progress() as progress:
            result = process_video(input, opts, settings, progress)
    except ClipEngineError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    print_summary(result)
    sys.exit(1 if result.failed else 0)


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@common_options
def batch(folder, **kw):
    """Process every video in FOLDER (non-recursive)."""
    try:
        settings, opts = startup(kw)
        videos = list_videos(folder)
    except ClipEngineError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    console.print(f"Found [bold]{len(videos)}[/bold] video(s) in {folder}")
    done: list[VideoResult] = []
    errors: list[tuple[str, str]] = []
    started = time.time()
    for i, video in enumerate(videos, start=1):
        console.rule(f"[bold]Video {i}/{len(videos)}: {video.name}")
        try:
            with make_progress() as progress:
                done.append(process_video(video, opts, settings, progress))
            print_summary(done[-1])
        except ClipEngineError as e:
            errors.append((video.name, str(e)))
            console.print(f"[bold red]Skipped {video.name}:[/bold red] {e}")

    console.print()
    console.rule("[bold]Batch summary")
    console.print(f"Videos processed: {len(done)}/{len(videos)}   Clips created: "
                  f"{sum(len(r.clips) for r in done)}   Time: {fmt_ts(time.time() - started)}")
    for r in done:
        console.print(f"  [green]OK[/green] {r.title}: {len(r.clips)} clips -> {r.out_dir.resolve()}")
    for name, msg in errors:
        console.print(f"  [red]FAILED[/red] {name}: {msg.splitlines()[0]}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
