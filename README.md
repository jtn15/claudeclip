# clipengine

Turn long-form videos **you own (or have rights to)** into short-form vertical clips (1080x1920) with
burned-in, word-by-word animated captions. Built for producing client content at A & J Web Services.

Pipeline: video/URL -> local Whisper transcript (word timestamps) -> Claude picks the best 20-60s moments
(snapped to sentence boundaries) -> ffmpeg cuts + 9:16 crop + captions -> clips, transcript, scores and
ready-to-paste social captions in a tidy folder.

## Rights and responsible use

clipengine only processes content you own or have permission to use. Every run requires `--confirm-rights`
(or an interactive y/n confirmation); the confirmation is recorded in `moments.json`. It handles one URL
at a time and has no channel/playlist/bulk-download features by design.

## Setup

Requires Python 3.11+ and ffmpeg.

```bash
# 1. ffmpeg
brew install ffmpeg                         # macOS
sudo apt update && sudo apt install ffmpeg  # Ubuntu/Debian
winget install Gyan.FFmpeg                  # Windows

# 2. Python environment
python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .          # optional: gives you the `clipengine` command (else use `python -m clipengine`)

# 3. API key
cp .env.example .env      # then put your ANTHROPIC_API_KEY in .env
```

The first transcription downloads the Whisper model (`small` is ~500 MB). Use `WHISPER_MODEL=base` for
faster/lighter runs, `medium` or `large-v3` for better accuracy (a GPU helps a lot).

## Usage

```bash
# one local file
clipengine run ./interview.mp4 --client "Acme Roofing" --confirm-rights

# a URL to a video you own
clipengine run "https://www.youtube.com/watch?v=..." --client "Acme Roofing" --confirm-rights

# more options
clipengine run talk.mp4 --client "Acme Roofing" --confirm-rights \
    --clips 6 --min-len 25 --max-len 45 --smart-crop \
    --font "Impact" --font-size 104 --caption-color "#FFFFFF" --highlight-color "#00E5FF"

# every video in a folder (non-recursive)
clipengine batch ./raw_footage --client "Acme Roofing" --confirm-rights

# clips only, no captions
clipengine run talk.mp4 --client "Acme Roofing" --confirm-rights --no-captions
```

Run `clipengine run --help` for all flags.

| Flag | What it does |
|---|---|
| `--clips N` | Max clips (default 8) |
| `--min-len / --max-len` | Clip length bounds in seconds (default 20 / 60) |
| `--smart-crop` | Track the speaker's face with OpenCV to choose the 9:16 crop; center crop if no face is found |
| `--no-captions` | Skip burned-in captions |
| `--font`, `--fonts-dir`, `--font-size` | Caption font (installed font name, or point `--fonts-dir` at a folder of .ttf/.otf), size |
| `--caption-color`, `--highlight-color` | Hex colors for text and the word being spoken |
| `--caption-words` | Max words on screen at once (1-4, default 3) |
| `--refresh-transcript` | Ignore the cached transcript and re-transcribe |
| `--allow-long` | Process videos over the 4-hour limit |
| `--output-dir` | Output root (default `./output`) |

## Output

```
output/{client}/{video title}/
  clip_01_{slug}.mp4        numbered in chronological order
  clip_02_{slug}.mp4
  transcript.json           word-level transcript (also the re-run cache)
  moments.json              start/end, hook, title, virality score + reason, caption, hashtags
  captions.txt              ready-to-paste caption + hashtags per clip
  .cache/source.mp4         only for URL inputs, so re-runs don't re-download
```

The end-of-run summary shows clips created, the output path, and the top 3 clips by virality score.
Re-running the same video reuses `transcript.json` (no re-transcribing) and replaces the previous `clip_*.mp4` files.
A clip may run up to ~0.5s over `--max-len` because of a small padding added around sentence boundaries.

## Configuration (.env)

| Variable | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | required |
| `CLIPENGINE_MODEL` | `claude-sonnet-4-6` | Claude model for moment selection |
| `WHISPER_MODEL` | `small` | tiny / base / small / medium / large-v3 |
| `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE` | `auto` | e.g. `cuda` + `float16`, or `cpu` + `int8` |
| `CLIPENGINE_OUTPUT_DIR` | `output` | |
| `CLIPENGINE_MAX_VIDEO_HOURS` | `4` | guard against accidental very long inputs |

## How it handles problems

- **ffmpeg missing**: checked at startup with install instructions.
- **Bad URL / download failure**: clear error; in `batch`, one failing video doesn't stop the rest.
- **No speech**: that video is skipped with an explanation.
- **Claude API errors**: up to 4 attempts with exponential backoff (2s, 4s, 8s); bad keys/models fail immediately with a clear message.
- **Invalid model output**: validated against the transcript; clips are snapped to whole sentences, length-repaired, de-overlapped, and bad items dropped.
- **Very long videos**: the transcript is sent to Claude in chunks; videos over 4 hours need `--allow-long`.

## Notes and v1 limits

- `--smart-crop` picks one horizontal crop position per clip (median face position). It does not pan with a moving speaker yet.
- Face detection uses OpenCV's Haar cascade: fast, no extra model files, but front-facing faces only.
- Captions use an installed font. If "Arial" isn't available (common on Linux), pass `--font` with an installed font or `--fonts-dir`.

## socialcrew: on-brand Facebook + Instagram content

A team of Claude agents that **creates and tailors** a week of posts per client. It doesn't post anything:
you review the content pack, tick what's approved and schedule it yourself (e.g. Meta Business Suite).

| Agent | Job |
|---|---|
| Brand strategist (`onboard`) | Reads the client's website + your notes and drafts their brand profile |
| Content strategist | Plans the week: one specific pain/desire per post, rotating pillars and formats |
| Copywriter | Writes each post: hook, IG + FB captions, hashtags, CTA, visual brief, AI image prompt, carousel slides or reel script |
| Editor | Reviews each draft against the brand, rewrites what's generic, scores it |
| Checker (no AI) | Banned words, IG caption limit, hook cut off by "...more", hashtag count, missing slides/script |

Tailoring lives in one editable file per client, `brands/{client}.yaml`: offers, audience, pains in the
customer's words, real proof, voice do's/don'ts, banned words, pillars, CTAs, compliance rules, example posts
and learnings. See `brands/desert-ridge-roofing.yaml` for a filled-in example.

```bash
# 1. once per client: draft the brand profile, then open the YAML and fix it
socialcrew onboard --client "Acme Roofing" --website https://acmeroofing.com --notes notes.txt

# 2. every week: plan + write + edit
socialcrew week --client "Acme Roofing" --posts 5 --focus "Monsoon season; 10% off tile repair through Friday"

# turn clipengine output into reels with captions written around the real footage
socialcrew week --client "Acme Roofing" --clips-dir "output/Acme Roofing/Owner Interview"

# 3. feed results back so next week is better
socialcrew learn --client "Acme Roofing" "Before/after carousels got 3x the saves of tips posts"
```

`--focus` and `--notes` take inline text or a path to a file. `--week` takes any date in the target week
(default: next week).

Output:

```
content/{client}/{week monday}/
  content_pack.md   review doc: summary table, then every post with approve/changes checkboxes
  posts.json        everything, including scores, editor notes and warnings
  posts.csv         one row per post, for spreadsheets or a scheduler import
```

| Variable | Default | Notes |
|---|---|---|
| `SOCIALCREW_MODEL` | `claude-sonnet-5-5` | Claude model for every agent |
| `SOCIALCREW_BRANDS_DIR` | `brands` | where brand profiles live |
| `SOCIALCREW_OUTPUT_DIR` | `content` | |

Cost: about 2 Claude calls per post plus 1 for the plan (11 calls for a 5-post week). Posts are written 4 at
a time; one failed post doesn't sink the week, it's listed in the pack to re-run.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```
