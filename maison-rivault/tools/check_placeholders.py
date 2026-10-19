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
OPTIONAL = {"klaviyo_public_key", "klaviyo_list_id", "generic_endpoint", "ga4_id", "meta_pixel_id", "cutoff_date"}


def walk(obj, path=""):
    for k, v in obj.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict):
            walk(v, f"{path}{k}.")
        elif isinstance(v, str) and v == "" and k not in OPTIONAL and k != "provider":
            found.append(("config", f"site.config.json: {path}{k} is empty"))


walk(cfg)
if cfg["SITE_MODE"] != "live":
    found.append(("launch", 'SITE_MODE is "waitlist" (correct until launch; set to "live" to ship the store)'))
if not cfg["SHOW_PRICES"]:
    found.append(("launch", "SHOW_PRICES is false (prices are hidden)"))
if not cfg["launch"]["target_confirmed"]:
    found.append(("launch", f"launch target {cfg['launch']['target_date']} is not confirmed"))
if not (cfg["holiday"]["cutoff_date"] and cfg["holiday"]["cutoff_confirmed"]):
    found.append(("launch", "holiday cutoff date not set and confirmed (the site says it cannot promise Christmas delivery)"))
if not cfg["email"]["provider"] and not cfg["email"]["generic_endpoint"]:
    found.append(("systems", "email provider not set (signup will refuse to submit)"))
if not cfg["commerce"]["shopify_domain"]:
    found.append(("systems", "Shopify store domain not set (checkout stays disabled)"))

for t in data["tiers"]:
    if t["name_status"] == "provisional":
        found.append(("content", f"tier name '{t['name']}' is provisional"))

for p in data["products"]:
    label = f"{data['tiers'][0]['name'] if p['tier']=='signature' else data['tiers'][1]['name']} {p['name']}"
    if p["price"] is None or p["price_status"] != "final":
        found.append(("price", f"{label}: no final price"))
    if p.get("color_status") == "placeholder":
        found.append(("content", f"{label}: color {p['color']} is a placeholder assignment"))
    if p.get("availability_status") == "tbc":
        found.append(("content", f"{label}: availability mode '{p['availability']}' unconfirmed"))
    if p.get("launch_status"):
        found.append(("content", f"{label}: launch status is '{p['launch_status']}'"))
    if p.get("name_status"):
        found.append(("content", f"{label}: {p['name_status']}"))
    for key in ("fiber", "fit", "care"):
        if not p.get(key):
            found.append(("content", f"{label}: {key} missing"))
    for img in p["images"]:
        if not img.get("src"):
            found.append(("photo", f"{label}: no photo for '{img['caption']}'"))
    if not p.get("shopify_variant_ids"):
        found.append(("systems", f"{label}: no Shopify variant ids"))
for b in data["bundles"]:
    if b["price"] is None or b["price_status"] != "final":
        found.append(("price", f"{b['name']}: no final price"))
    if b["open_slots"] or "assumed" in b["contents_status"]:
        found.append(("content", f"{b['name']}: {b['contents_status']}"))

for d in (ROOT / "site", ROOT / "preview"):
    if d.exists():
        for f in sorted(d.rglob("*.html")):
            n = len(re.findall(r'class="todo"', f.read_text()))
            if n:
                found.append(("page", f"{d.name}/{f.relative_to(d)}: {n} visible [confirm: ...] marker(s)"))
    else:
        found.append(("build", f"{d.name}/ not built yet: run python3 build.py"))

for kind in ["launch", "config", "price", "content", "photo", "systems", "page", "build"]:
    rows = [m for k, m in found if k == kind]
    if rows:
        print(f"\n[{kind}] {len(rows)}")
        for m in rows:
            print("  -", m)
print(f"\n{len(found)} placeholder item(s) remain." if found else "No placeholders remain.")
sys.exit(1 if found else 0)
