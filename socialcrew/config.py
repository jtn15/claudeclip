"""Configuration: environment variables and defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


class SocialCrewError(Exception):
    """Base class for errors that should be shown to the user without a traceback."""


@dataclass
class Settings:
    anthropic_api_key: str | None = None
    claude_model: str = "claude-sonnet-5-5"
    brands_dir: Path = field(default_factory=lambda: Path("brands"))
    output_dir: Path = field(default_factory=lambda: Path("content"))


def load_settings() -> Settings:
    """Load settings from the environment (and a .env file in the working directory)."""
    load_dotenv()
    env = os.environ.get
    return Settings(
        anthropic_api_key=env("ANTHROPIC_API_KEY") or None,
        claude_model=env("SOCIALCREW_MODEL") or "claude-sonnet-5-5",
        brands_dir=Path(env("SOCIALCREW_BRANDS_DIR") or "brands"),
        output_dir=Path(env("SOCIALCREW_OUTPUT_DIR") or "content"),
    )
