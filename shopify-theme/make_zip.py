#!/usr/bin/env python3
"""Rebuild shopify-theme.zip (theme folders at the zip root, as Shopify requires)."""
import zipfile
from pathlib import Path

here = Path(__file__).resolve().parent
out = here.parent / "shopify-theme.zip"
keep = {"assets", "config", "layout", "locales", "sections", "snippets", "templates"}
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(here.rglob("*")):
        rel = f.relative_to(here)
        if f.is_file() and rel.parts[0] in keep:
            z.write(f, rel.as_posix())
print(f"Wrote {out} ({out.stat().st_size // 1024} KB)")
