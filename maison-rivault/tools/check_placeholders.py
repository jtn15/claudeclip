#!/usr/bin/env python3
"""List everything that is still a placeholder. Exits 1 if anything is left, so it can gate a deploy.

Run after build:  python3 build.py && python3 tools/check_placeholders.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cfg = json.loads((ROOT / "site.config.json").read_text())
data = json.loads((ROOT / "data" / "products.json").read_text())
found = []


def walk(obj, path=""):
    for k, v in obj.items():
        if k.startswith("_") or k in ("launch_price_window_end",):
            continue
        if isinstance(v, dict):
            walk(v, f"{path}{k}.")
        elif isinstance(v, str) and v == "" and k != "provider":
            found.append(("config", f"site.config.json: {path}{k} is empty"))


walk(cfg)
if not cfg["email"]["provider"] and not cfg["email"]["generic_endpoint"]:
    found.append(("config", "site.config.json: email provider not set (signup will refuse to submit)"))

for p in data["products"]:
    if p["price_status"] != "final":
        found.append(("price", f"{p['name']}: price ${p['price']} is a placeholder"))
    if p.get("color_status") == "placeholder":
        found.append(("color", f"{p['name']}: color {p['color']} is a placeholder assignment"))
    for key in ("fiber", "fit", "care"):
        if not p.get(key):
            found.append(("content", f"{p['name']}: {key} missing"))
    for img in p["images"]:
        if not img.get("src"):
            found.append(("photo", f"{p['name']}: no photo for '{img['caption']}'"))
    if p.get("name_status"):
        found.append(("content", f"{p['name']}: {p['name_status']}"))
    if p["availability"] == "tbc":
        found.append(("content", f"{p['name']}: release date unconfirmed"))
    if not p.get("shopify_variant_ids"):
        found.append(("shopify", f"{p['name']}: no Shopify variant ids"))
for b in data["bundles"]:
    if b["price_status"] != "final":
        found.append(("price", f"{b['name']}: price ${b['price']} is a placeholder"))

site = ROOT / "site"
if site.exists():
    for f in sorted(site.rglob("*.html")):
        n = len(re.findall(r'class="todo"', f.read_text()))
        if n:
            found.append(("page", f"{f.relative_to(site)}: {n} visible [confirm: ...] marker(s)"))
else:
    found.append(("build", "site/ not built yet: run python3 build.py"))

order = ["config", "price", "color", "content", "photo", "shopify", "page", "build"]
for kind in order:
    rows = [m for k, m in found if k == kind]
    if rows:
        print(f"\n[{kind}] {len(rows)}")
        for m in rows:
            print("  -", m)
print(f"\n{len(found)} placeholder item(s) remain." if found else "No placeholders remain.")
sys.exit(1 if found else 0)
