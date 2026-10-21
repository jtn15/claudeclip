"""One structured Claude call with retries, shared by every agent."""

from __future__ import annotations

import time
from typing import Callable

from socialcrew.config import SocialCrewError

MAX_ATTEMPTS = 4


def make_client(api_key: str | None):
    if not api_key:
        raise SocialCrewError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")
    import anthropic
    return anthropic.Anthropic(api_key=api_key, max_retries=0, timeout=180)


def call_tool(client, model: str, system: str, user: str, tool: dict,
              on_retry: Callable[[str], None] | None = None, max_tokens: int = 8000) -> dict:
    """Force Claude to answer with `tool` and return its input. Retries transient errors with backoff."""
    import anthropic

    delay = 2.0
    last: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                tools=[tool], tool_choice={"type": "tool", "name": tool["name"]},
                messages=[{"role": "user", "content": user}],
            )
            for block in resp.content:
                if block.type == "tool_use" and block.name == tool["name"]:
                    return block.input
            raise ValueError("model did not return structured output")
        except anthropic.AuthenticationError as e:
            raise SocialCrewError("Anthropic API key was rejected. Check ANTHROPIC_API_KEY in your .env.") from e
        except anthropic.NotFoundError as e:
            raise SocialCrewError(f"Model '{model}' was not found. Check SOCIALCREW_MODEL in your .env.") from e
        except anthropic.BadRequestError as e:
            raise SocialCrewError(f"Claude API rejected the request: {e}") from e
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APIStatusError, ValueError) as e:
            last = e
            if attempt == MAX_ATTEMPTS:
                break
            if on_retry:
                on_retry(f"Claude API error ({type(e).__name__}); retrying in {delay:.0f}s "
                         f"(attempt {attempt}/{MAX_ATTEMPTS - 1})")
            time.sleep(delay)
            delay *= 2
    raise SocialCrewError(f"Claude API failed after {MAX_ATTEMPTS} attempts: {last}")
