#!/usr/bin/env python3
"""Build the Maison Rivault site from site.config.json and data/products.json.

Standard library only.

  python3 build.py              # writes ./site (per SITE_MODE) and ./preview (always the full store)
  python3 build.py --mode live  # force the full store into ./site as well

Deploy ./site only. ./preview is the full store for reviewing the design before launch; it is marked
noindex and says so in the announcement bar. Preview locally with:
  python3 -m http.server -d site 8000
  python3 -m http.server -d preview 8001
"""
import argparse
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"

CFG = json.loads((ROOT / "site.config.json").read_text())
DATA = json.loads((ROOT / "data" / "products.json").read_text())
COLORS = DATA["colors"]
PRODUCTS = DATA["products"]
BUNDLES = DATA["bundles"]
TIERS = {t["id"]: t for t in DATA["tiers"]}
MODES = DATA["availability_modes"]
BY_ID = {p["id"]: p for p in PRODUCTS}
SHOW_PRICES = bool(CFG["SHOW_PRICES"])

# Set per build in build_site(): which chrome and banner text to use.
STATE = {"preview": False}


# ---------- helpers ----------

def esc(s):
    return html.escape(str(s), quote=True)


def todo(label):
    """Visible marker for anything the owner must confirm. Counted by tools/check_placeholders.py."""
    return f'<span class="todo">[confirm: {esc(label)}]</span>'


def val(value, label):
    return esc(value) if value not in (None, "") else todo(label)


def money(n):
    return f"${n:,.0f}" if float(n).is_integer() else f"${n:,.2f}"


def priced(item):
    """True when a price may be shown and bought."""
    return SHOW_PRICES and item["price"] is not None


def price_html(item):
    if priced(item):
        return f'<span class="price">{money(item["price"])}</span>'
    return '<span class="price-tbd">Price at launch</span>'


def color_of(p):
    return COLORS[p["color"]]


def tier_name(p):
    return TIERS[p["tier"]]["name"]


def ph(caption, ratio="4 / 5", alt=None):
    return (f'<div class="ph" style="aspect-ratio:{ratio}" role="img" '
            f'aria-label="{esc(alt or caption)}"><span>{esc(caption)}</span></div>')


def image(img, ratio="4 / 5", eager=False):
    """Real photo when "src" is set in products.json, neutral placeholder otherwise."""
    if img.get("src"):
        return (f'<img class="photo" src="{esc(img["src"])}" alt="{esc(img["alt"])}" '
                f'loading="{"eager" if eager else "lazy"}" style="aspect-ratio:{ratio}">')
    return ph(img["caption"], ratio, img["alt"])


def instagram_url():
    h = CFG.get("instagram_handle", "").lstrip("@")
    return f"https://www.instagram.com/{h}/" if h else None


def availability_html(p):
    """Honest availability and ship window. Windows come from config; empty ones show as confirm markers."""
    s = CFG["shipping"]
    mode = p["availability"]
    if mode == "made_to_order":
        line = f'Made to order. Estimated delivery: {val(s["made_to_order_delivery"], "made-to-order delivery window")}.'
    elif mode == "in_stock":
        line = f'In stock. Ships {val(s["in_stock_ship"], "in-stock ship time")}.'
    else:
        line = (f'Preorder. Expected to ship {val(s["preorder_ship"], "preorder ship window")}. '
                f'{val(s["preorder_policy"], "preorder charge policy, stated plainly")}')
    status = f' {todo("availability mode for this product")}' if p.get("availability_status") == "tbc" else ""
    return f'<p class="status-line">{line}{status}</p>'


def holiday_html():
    h = CFG["holiday"]
    if h["cutoff_date"] and h["cutoff_confirmed"]:
        return (f'<p class="small">Holiday orders: orders placed by {esc(h["cutoff_date"])} are expected '
                f'to arrive before December 25.</p>')
    return (f'<p class="small">We cannot yet promise delivery before December 25. '
            f'{todo("holiday cutoff date, then set cutoff_confirmed")}</p>')


# ---------- layout ----------

NAV = [("shop.html", "Shop"), ("bundles.html", "Bundles"), ("our-story.html", "Our Story"), ("contact.html", "Contact")]


def head(path, title, description, root, noindex=False):
    domain = CFG.get("domain", "").strip()
    full_title = title if title.startswith(CFG["brand"]) else f"{title} | {CFG['brand']}"
    canonical = f'<link rel="canonical" href="https://{esc(domain)}/{path}">' if domain else ""
    og_img = f"https://{domain}/assets/img/og-image.png" if domain else f"{root}assets/img/og-image.png"
    og_url = f'<meta property="og:url" content="https://{esc(domain)}/{path}">' if domain else ""
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description)}">
{robots}
{canonical}
<meta property="og:site_name" content="{esc(CFG['brand'])}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="website">
<meta property="og:image" content="{esc(og_img)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
{og_url}
<meta name="theme-color" content="#F3EEE4">
<link rel="icon" href="{root}assets/img/favicon.svg" type="image/svg+xml">
<link rel="icon" href="{root}assets/img/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{root}assets/img/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500&family=Jost:wght@300;400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}assets/css/main.css">
</head>"""


def scripts(root):
    return (f'<script src="{root}assets/js/data.js"></script>\n'
            f'<script src="{root}assets/js/site.js"></script>\n</body>\n</html>\n')


def layout(path, title, description, body, root="", chrome="full"):
    """chrome: 'full' (store), 'simple' (logo-only header, minimal footer), 'bare' (no header)."""
    noindex = STATE["preview"]
    out = head(path, title, description, root, noindex) + "\n<body>\n"
    out += '<a class="skip" href="#main">Skip to content</a>\n'
    home = f"{root}index.html"
    lockup = (f'<a class="logo" href="{home}" aria-label="{esc(CFG["brand"])}, home">'
              f'<span class="logo-lockup" role="img" aria-label="{esc(CFG["brand"])}"></span></a>')

    if chrome == "full":
        banner = f'Doors open {esc(CFG["launch"]["label"])}'
        if STATE["preview"]:
            banner = "Preview build, not live. " + banner
        nav = "".join(
            f'<a href="{root}{href}"' + (' aria-current="page"' if href == path else "") + f">{label}</a>"
            for href, label in NAV)
        out += f"""<div class="announce label"><p>{banner}</p></div>
<header class="site-header">
  <div class="wrap">
    {lockup}
    <nav id="site-nav" class="nav label" aria-label="Main">{nav}</nav>
    <div class="header-right label">
      <a class="cart-link" href="{root}cart.html">Cart (<span class="cart-count">0</span>)</a>
      <button class="menu-btn label" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
    </div>
  </div>
</header>
"""
    elif chrome == "simple":
        out += f'<header class="site-header"><div class="wrap">{lockup}</div></header>\n'

    out += f'<main id="main">\n{body}\n</main>\n'

    cookie = '<a href="#" data-cookie-settings>Cookie settings</a>'
    if chrome == "full":
        ig = instagram_url()
        ig_link = (f'<a href="{esc(ig)}" rel="noopener">Instagram</a>' if ig
                   else f'Instagram {todo("Instagram handle")}')
        ret = CFG["returns"]["window_days"]
        ret_html = val(ret + " days" if ret else "", "return window")
        out += f"""<footer class="site-footer">
  <div class="wrap">
    <div class="footer-grid">
      <div class="footer-brand">
        <span class="logo logo-mono" role="img" aria-label="{esc(CFG['brand'])} monogram"></span>
        <p class="muted" style="margin-top:1.25rem">{esc(CFG['tagline'])}</p>
      </div>
      <div class="footer-col"><h2>Shop</h2><ul>
        <li><a href="{root}shop.html">All products</a></li>
        <li><a href="{root}bundles.html">Bundles</a></li>
        <li><a href="{root}coming-next.html">Coming next</a></li></ul></div>
      <div class="footer-col"><h2>Help</h2><ul>
        <li><a href="{root}size-guide.html">Size guide</a></li>
        <li><a href="{root}shipping-returns.html">Shipping and returns</a></li>
        <li><a href="{root}faq.html">FAQ</a></li>
        <li><a href="{root}contact.html">Contact</a></li></ul></div>
      <div class="footer-col"><h2>Maison Rivault</h2><ul>
        <li><a href="{root}our-story.html">Our Story</a></li>
        <li>{ig_link}</li></ul></div>
      <div class="footer-col"><h2>Legal</h2><ul>
        <li><a href="{root}privacy.html">Privacy</a></li>
        <li><a href="{root}terms.html">Terms</a></li>
        <li>{cookie}</li></ul></div>
    </div>
    <div class="footer-base">
      <p>&copy; {esc(CFG['established'])} {esc(CFG['brand'])}. Returns: {ret_html}. <a href="{root}shipping-returns.html">Return policy</a></p>
      <p>Est. {esc(CFG['established'])}</p>
    </div>
  </div>
</footer>
"""
    else:
        out += f"""<footer class="site-footer site-footer-slim">
  <div class="wrap footer-base" style="border:0;margin:0 auto;padding:0 var(--gutter);justify-content:center;gap:1.75rem">
    <p>Est. {esc(CFG['established'])}</p>
    <p><a href="{root}privacy.html">Privacy</a></p>
    <p><a href="{root}terms.html">Terms</a></p>
    <p>{cookie}</p>
  </div>
</footer>
"""
    return out + scripts(root)


# ---------- components ----------

def signup(source, button="Notify me"):
    return f"""<form class="signup js-signup" data-source="{esc(source)}" novalidate>
  <label class="label" style="flex-basis:100%" for="email-{esc(source)}">Email address</label>
  <input id="email-{esc(source)}" type="email" name="email" autocomplete="email" placeholder="you@example.com" required>
  <button class="btn" type="submit">{esc(button)}</button>
</form>
<p class="form-msg" role="status" aria-live="polite"></p>
<p class="small">We email once when doors open, and about what comes next. Unsubscribe any time.</p>"""


def product_card(p, root=""):
    c = color_of(p)
    return f"""<a class="card" href="{root}products/{p['slug']}.html" data-tier="{esc(p['tier'])}" data-type="{esc(p['type'])}">
  {image(p['images'][0], '4 / 5')}
  <div class="card-meta">
    <div><div class="card-name">{esc(p['name'])}</div>
    <div class="card-sub"><span class="swatch" style="background:{c['hex']}"></span>{esc(tier_name(p))} &middot; {esc(c['name'])}</div></div>
    {price_html(p)}
  </div></a>"""


def bundle_contents(b):
    rows = [f"<li>{esc(BY_ID[i]['name'])}, {esc(color_of(BY_ID[i])['name'])}</li>" for i in b["items"]]
    rows += [f"<li>One more piece {todo('second piece for ' + b['name'])}</li>"] * b["open_slots"]
    return "".join(rows)


def bundle_saving_html(b):
    """A saving is shown only when the bundle and every component have final prices."""
    parts = [BY_ID[i] for i in b["items"]]
    if b["open_slots"] or not priced(b) or not all(priced(p) for p in parts):
        return '<p class="small">The saving is shown once prices are set.</p>'
    separate = sum(p["price"] for p in parts)
    saved = separate - b["price"]
    if saved <= 0:
        return ""
    return (f'<p class="saving">Save {money(saved)} ({round(100 * saved / separate)}%) against buying '
            f'separately at {money(separate)}.</p>')


def bundle_block(b, full=False, root=""):
    if not full:
        cta = f'<a class="btn btn-quiet" href="{root}bundles.html#{b["slug"]}">View bundle</a>'
    else:
        selects = ""
        for i in b["items"]:
            p = BY_ID[i]
            if p["sizes"] == ["One size"]:
                continue
            opts = "".join(f'<option value="{s}">{s}</option>' for s in p["sizes"])
            selects += (f'<label><span class="label">{esc(p["name"])} size</span>'
                        f'<select data-item="{p["id"]}"><option value="">Choose size</option>{opts}</select></label>')
        can_buy = priced(b) and not b["open_slots"]
        disabled = "" if can_buy else " disabled"
        why = "" if can_buy else '<p class="small">Available once the price is set.</p>'
        cta = f"""<div class="bundle-sizes">{selects}</div>
<button class="btn" type="button" data-add-bundle="{b['id']}"{disabled}>Add bundle to cart</button>
{why}<p class="form-msg small bundle-msg" role="status" aria-live="polite"></p>"""
    status = f'<p class="small">{todo(b["contents_status"]) }</p>' if b["contents_status"] not in ("the whole Signature range",) else ""
    return f"""<article class="bundle" id="{b['slug']}">
  <h3>{esc(b['name'])}</h3>
  <p>{price_html(b)}</p>
  <ul>{bundle_contents(b)}</ul>
  {bundle_saving_html(b)}
  {status if full else ''}
  {cta}
</article>"""


def tier_section(tier_id, root=""):
    t = TIERS[tier_id]
    items = [p for p in PRODUCTS if p["tier"] == tier_id]
    cards = "".join(product_card(p, root) for p in items)
    extra = f' {todo("Essentials launch styles")}' if tier_id == "essentials" else ""
    flag = f' {todo("tier name")}' if t["name_status"] == "provisional" else ""
    return f"""<section id="{tier_id}">
  <div class="wrap">
    <div class="section-head"><h2>{esc(t['name'])}{flag}</h2><a class="label" href="shop.html">View all</a></div>
    <p class="muted" style="margin-bottom:2rem">{esc(t['blurb'])}{extra}</p>
    <div class="grid">{cards}</div>
  </div>
</section>"""


# ---------- pages: each returns dict(path, title, desc, body, chrome) ----------

def page(path, title, desc, body, chrome="full"):
    return {"path": path, "title": title, "desc": desc, "body": body, "chrome": chrome}


def page_waitlist(path="index.html"):
    body = f"""
<div class="waitlist">
  <div class="waitlist-inner">
    <span class="logo logo-hero" role="img" aria-label="{esc(CFG['brand'])}"></span>
    <h1>{esc(CFG['tagline'])}</h1>
    <p class="label muted">Doors open {esc(CFG['launch']['label'])}.</p>
    <div class="waitlist-form">{signup('waitlist', 'Join the waitlist')}</div>
  </div>
</div>"""
    return page(path, f"{CFG['brand']}: {CFG['tagline']}",
                f"Quiet, well-made knitwear for men. Doors open {CFG['launch']['label']}. Join the waitlist.",
                body, chrome="bare")


def page_home():
    bundles = "".join(bundle_block(b) for b in BUNDLES)
    loc = esc(CFG["location"]) if CFG["location"] else todo("location, e.g. Phoenix, Arizona")
    body = f"""
<section class="hero">
  <div class="wrap">
    <div class="hero-copy">
      <p class="label muted">Menswear in layers</p>
      <h1>{esc(CFG['tagline'])}</h1>
      <p class="lede">Knitwear for men, built in layers, in navy, camel, olive and cream. Doors open {esc(CFG['launch']['label'])}.</p>
      <a class="btn" href="shop.html">Shop the line</a>
    </div>
    <div class="hero-art">{ph('Hero photo: quarter-zip and polo, window light', '4 / 5')}</div>
  </div>
</section>
<hr class="rule">
{tier_section('signature')}
<hr class="rule">
{tier_section('essentials')}
<hr class="rule">
<section>
  <div class="wrap">
    <div class="section-head"><h2>Bundles</h2><a class="label" href="bundles.html">View all</a></div>
    <div class="bundles">{bundles}</div>
  </div>
</section>
<section class="story-block">
  <div class="col center">
    <p class="statement">{esc(CFG['story_sentence'])}</p>
    <p class="label muted">Est. {esc(CFG['established'])} &middot; {loc}</p>
    <p style="margin-top:1.5rem"><a class="label" href="our-story.html">Our story</a></p>
  </div>
</section>
<section id="waitlist">
  <div class="col">
    <h2>Doors open {esc(CFG['launch']['label'])}.</h2>
    <p class="muted">Leave your email and we will write once when they do.</p>
    {signup('home')}
  </div>
</section>"""
    return page("index.html", f"{CFG['brand']}: {CFG['tagline']}",
                f"Quiet, well-made men's knitwear in two tiers, Signature and Essentials. Doors open {CFG['launch']['label']}.", body)


def filter_group(label, group, values):
    btns = '<button type="button" data-group="%s" data-value="all" aria-pressed="true">All</button>' % group
    btns += "".join(f'<button type="button" data-group="{group}" data-value="{esc(v)}" aria-pressed="false">{esc(n)}</button>'
                    for v, n in values)
    return f'<div class="filters" role="group" aria-label="{esc(label)}">{btns}</div>'


def page_shop():
    tiers = [(t["id"], t["name"]) for t in DATA["tiers"]]
    types = []
    for p in PRODUCTS:
        if p["type"] not in types:
            types.append(p["type"])
    cards = "".join(product_card(p) for p in PRODUCTS)
    body = f"""
<section class="page-head"><div class="wrap">
  <h1>Shop</h1>
  <p class="lede">Two tiers, one color per style. Doors open {esc(CFG['launch']['label'])}.</p>
</div></section>
<section style="padding-top:1rem"><div class="wrap">
  {filter_group('Filter by tier', 'tier', tiers)}
  {filter_group('Filter by type', 'type', [(t, t) for t in types])}
  <div class="grid">{cards}</div>
  <p class="muted" style="margin-top:3rem">Buying more than one piece? See the <a href="bundles.html">bundles</a>.</p>
</div></section>"""
    return page("shop.html", "Shop", "Knitwear for men in two tiers, Signature and Essentials, in navy, camel, olive and cream.", body)


def page_bundles():
    blocks = "".join(bundle_block(b, full=True) for b in BUNDLES)
    body = f"""
<section class="page-head"><div class="wrap">
  <h1>Bundles</h1>
  <p class="lede">Four sets. Each shows what is in it, and the saving once prices are set.</p>
</div></section>
<section style="padding-top:1rem"><div class="wrap"><div class="bundles">{blocks}</div></div></section>"""
    return page("bundles.html", "Bundles", "Four bundles: The Layering Bundle, The Cold Morning Set, The Weekend Layers and The Full Rotation.", body)


def page_product(p):
    c = color_of(p)
    gallery = "".join(image(img, "4 / 5", eager=(i == 0)) for i, img in enumerate(p["images"]))
    one_size = p["sizes"] == ["One size"]
    opts = "".join(f'<option value="{s}">{s}</option>' for s in p["sizes"])
    size_ui = (f'<p class="muted">One size.</p><select id="size" hidden><option value="One size" selected>One size</option></select>'
               if one_size else
               f'<div class="size-row"><label class="label" for="size">Size</label><a class="small" href="../size-guide.html">Size guide</a></div>'
               f'<select id="size"><option value="">Choose a size</option>{opts}</select>'
               f'<p class="form-msg small" id="size-msg" role="status" aria-live="polite"></p>')
    buyable = priced(p)
    cta = (f'<button class="btn btn-block" type="button" data-add-product="{p["id"]}" data-cart-url="../cart.html">Add to cart</button>'
           if buyable else
           '<button class="btn btn-block" type="button" disabled>Add to cart</button>'
           '<p class="small" style="margin-top:0.75rem">Available once the price is set.</p>')
    ret = CFG["returns"]
    ret_line = val(ret["window_days"] + " days" if ret["window_days"] else "", "return window")
    name_flag = f' {todo(p["name_status"])}' if p.get("name_status") else ""
    launch_flag = f' {todo("whether this launches: " + p["launch_status"])}' if p.get("launch_status") else ""
    body = f"""
<section style="padding-top:2.5rem"><div class="wrap">
  <p class="crumbs label"><a href="../shop.html">Shop</a> / {esc(p['name'])}</p>
  <div class="product">
    <div class="product-gallery">{gallery}</div>
    <div class="product-info">
      <p class="label muted">{esc(tier_name(p))}</p>
      <h1>{esc(p['name'])}{name_flag}</h1>
      <p>{price_html(p)}</p>
      <p class="card-sub"><span class="swatch" style="background:{c['hex']}"></span>{esc(c['name'])}</p>
      <p>{esc(p['summary'])}{launch_flag}</p>
      {availability_html(p)}
      {size_ui}
      <div style="margin-top:1.25rem">{cta}</div>
      {holiday_html()}
      <p class="small">Returns: {ret_line}. See <a href="../shipping-returns.html">shipping and returns</a>.</p>
      <div style="margin-top:2rem">
        <details open><summary class="label">Fabric and fiber content</summary><div><p>{val(p['fiber'], 'fiber content, required by law for US garments')}</p></div></details>
        <details><summary class="label">Fit</summary><div><p>{val(p['fit'], 'fit note')}</p></div></details>
        <details><summary class="label">Care</summary><div><p>{val(p['care'], 'care instructions')}</p></div></details>
        <details><summary class="label">Shipping and returns</summary><div><p><a href="../shipping-returns.html">Full shipping and returns policy</a></p></div></details>
      </div>
    </div>
  </div>
</div></section>"""
    return page(f"products/{p['slug']}.html", f"{tier_name(p)} {p['name'].lower()} in {c['name'].lower()}",
                f"{tier_name(p)} {p['name'].lower()} in {c['name'].lower()}. {p['summary']}", body)


def page_story():
    loc = val(CFG["location"], "location, e.g. Phoenix, Arizona")
    body = f"""
<section class="page-head"><div class="col"><h1>Our Story</h1></div></section>
<section style="padding-top:1rem"><div class="col prose">
  <p class="lede">{esc(CFG['story_sentence'])} Est. {esc(CFG['established'])}. {loc}</p>
  <p>Maison Rivault begins with a narrow idea: a small set of knitwear, in four colors, that goes together without effort. Navy, camel, olive and cream. Pieces that sit over and under each other, so a cold morning and a mild afternoon call for the same few things.</p>
  <p>The line has two tiers, Signature and Essentials. Each style comes in one color at launch, and each product page says plainly how the piece is made available and when to expect it.</p>
  <p>We are a new brand, and we would rather say so than borrow a history. What we can offer is a short list of well-chosen pieces, described plainly, with fabric, fit and care stated on every page.</p>
</div></section>
<section class="story-block"><div class="col">
  <h2 style="text-align:center">Join the waitlist</h2>
  <p class="muted" style="text-align:center;margin-left:auto;margin-right:auto">Doors open {esc(CFG['launch']['label'])}.</p>
  <div style="display:flex;flex-direction:column;align-items:center">{signup('story')}</div>
</div></section>"""
    return page("our-story.html", "Our Story", f"Maison Rivault makes quiet, well-made knitwear for men, built in layers. A new brand, est. {CFG['established']}.", body)


def page_coming_next():
    items = "".join(f"<li>{esc(i)}</li>" for i in DATA["coming_next"])
    body = f"""
<section class="page-head"><div class="col"><h1>Coming next</h1></div></section>
<section style="padding-top:1rem"><div class="col prose">
  <p class="lede">After the first line, we plan to add:</p>
  <ul>{items}</ul>
  <p>None of this is for sale yet. Leave your email and we will tell you when it is.</p>
  {signup('coming-next', 'Tell me')}
</div></section>"""
    return page("coming-next.html", "Coming next", "What Maison Rivault plans to add after the first line. Not for sale yet.", body)


def page_size():
    rows = "".join(f"<tr><td>{s}</td><td>{todo('chest')}</td><td>{todo('length')}</td><td>{todo('sleeve')}</td></tr>"
                   for s in ["S", "M", "L", "XL", "XXL"])
    body = f"""
<section class="page-head"><div class="col"><h1>Size guide</h1></div></section>
<section style="padding-top:1rem"><div class="col prose">
  <p>Garment measurements in inches, taken flat. Compare them with a piece you already wear and like.</p>
  <div class="table-scroll"><table>
    <thead><tr><th>Size</th><th>Chest</th><th>Length</th><th>Sleeve</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  <h2>How to measure</h2>
  <p>Lay a favorite sweater flat. Measure across the chest, from underarm to underarm, and double it. Measure length from the high point of the shoulder to the hem.</p>
  <p>Scarf and beanie are one size. Questions about fit: <a href="contact.html">contact us</a>.</p>
</div></section>"""
    return page("size-guide.html", "Size guide", "Garment measurements and how to find your size.", body)


def page_shipping():
    s, r = CFG["shipping"], CFG["returns"]
    body = f"""
<section class="page-head"><div class="col"><h1>Shipping and returns</h1></div></section>
<section style="padding-top:1rem"><div class="col prose">
  <h2>How products are made available</h2>
  <p><strong>Made to order:</strong> made after you order. Estimated delivery: {val(s['made_to_order_delivery'], 'made-to-order delivery window')}.</p>
  <p><strong>In stock:</strong> ships right away. Ships {val(s['in_stock_ship'], 'in-stock ship time')}.</p>
  <p><strong>Preorder:</strong> not made yet. Expected to ship {val(s['preorder_ship'], 'preorder ship window')}. {val(s['preorder_policy'], 'preorder charge policy, stated plainly')}</p>
  <p>Each product page says which of these applies.</p>
  <h2>Shipping</h2>
  <p><strong>Cost:</strong> {val(s['cost'], 'shipping cost')}.</p>
  <p><strong>Where we ship:</strong> {val(s['regions'], 'shipping regions')}.</p>
  <h2>Holiday orders</h2>
  {holiday_html()}
  <h2>Returns</h2>
  <p><strong>Window:</strong> {val(r['window_days'] and r['window_days'] + ' days from delivery', 'return window')}.</p>
  <p><strong>Condition:</strong> {val(r['conditions'], 'return conditions, e.g. unworn with tags')}.</p>
  <p><strong>Return shipping:</strong> {val(r['return_shipping'], 'who pays return shipping')}.</p>
  <p>To start a return, <a href="contact.html">contact us</a> with your order number.</p>
</div></section>"""
    return page("shipping-returns.html", "Shipping and returns", "How products are made available, shipping times and costs, and how returns work.", body)


def page_faq():
    qa = [
        ("When do doors open?", f"Doors open {esc(CFG['launch']['label'])}. <a href=\"index.html#waitlist\">Join the waitlist</a> and we will email once when they do."),
        ("What are Signature and Essentials?", "Two tiers of the same line. Each product page says which tier it belongs to and how it is made available."),
        ("What does made to order mean?", f"The piece is made after you order. Estimated delivery: {val(CFG['shipping']['made_to_order_delivery'], 'made-to-order delivery window')}."),
        ("What is a preorder?", f"A preorder is not made yet. {val(CFG['shipping']['preorder_policy'], 'preorder charge policy, stated plainly')}"),
        ("What colors are available?", "Four colors across the line: navy, camel, olive and cream. Each style comes in one color at launch."),
        ("What comes next?", "A cardigan, trousers and footwear. They are not for sale yet. See <a href=\"coming-next.html\">Coming next</a>."),
        ("Will pieces be restocked?", f"{todo('restock plan')}"),
        ("How do I find my size?", "See the <a href=\"size-guide.html\">size guide</a>."),
        ("What is your return policy?", "See <a href=\"shipping-returns.html\">shipping and returns</a>."),
    ]
    items = "".join(f"<details><summary>{q}</summary><div><p>{a}</p></div></details>" for q, a in qa)
    body = f"""
<section class="page-head"><div class="col"><h1>FAQ</h1></div></section>
<section style="padding-top:1rem"><div class="col">{items}</div></section>"""
    return page("faq.html", "FAQ", "Answers about availability, sizing, bundles, shipping and returns.", body)


def page_contact():
    email = CFG.get("contact_email", "")
    mail = f'<a href="mailto:{esc(email)}">{esc(email)}</a>' if email else todo("contact email")
    body = f"""
<section class="page-head"><div class="col"><h1>Contact</h1></div></section>
<section style="padding-top:1rem"><div class="col prose">
  <p>Questions about an order, sizing or a return: write to {mail}.</p>
  <p class="muted">Please include your order number if you have one.</p>
</div></section>"""
    return page("contact.html", "Contact", "Get in touch about orders, sizing or returns.", body)


def page_legal(kind, chrome="full"):
    if kind == "privacy":
        title = "Privacy"
        paras = f"""
  <h2>What we collect</h2>
  <p>If you join the waitlist, we collect your email address. When you place an order through our store, the checkout provider collects the details needed to process and ship it.</p>
  <h2>How we use it</h2>
  <p>We use your email to tell you when doors open and to share what comes next. You can unsubscribe at any time from any email we send.</p>
  <h2>Cookies and analytics</h2>
  <p>The site stores your cart and your cookie choice in your browser. Analytics and advertising cookies stay off unless you accept them in the banner. You can change your choice from "Cookie settings" in the footer.</p>
  <h2>Contact</h2>
  <p>Questions about your data: {val(CFG.get('contact_email'), 'contact email')}.</p>"""
    else:
        title = "Terms"
        paras = f"""
  <h2>Orders</h2>
  <p>Prices are shown in US dollars. We may cancel an order if a product is unavailable, and will refund it in full.</p>
  <h2>Shipping and returns</h2>
  <p>See our <a href="shipping-returns.html">shipping and returns</a> page. It forms part of these terms.</p>
  <h2>Governing law</h2>
  <p>{todo('governing law and business entity name')}</p>"""
    body = f"""
<section class="page-head"><div class="col"><h1>{title}</h1></div></section>
<section style="padding-top:1rem"><div class="col prose">
  <p class="muted">This is a plain-language draft. {todo('legal review')}</p>{paras}
</div></section>"""
    return page(f"{kind}.html", title, f"{title} for {CFG['brand']}.", body, chrome=chrome)


def page_cart():
    body = """
<section class="page-head"><div class="col"><h1>Cart</h1></div></section>
<section style="padding-top:1rem"><div class="col"><div id="cart-root"><noscript><p>The cart needs JavaScript.</p></noscript></div></div></section>"""
    return page("cart.html", "Cart", "Your cart.", body)


# ---------- build ----------

def runtime_data():
    products = [{
        "id": p["id"], "kind": "product", "name": f"{tier_name(p)} {p['name'].lower()}", "price": p["price"] if SHOW_PRICES else None,
        "sizes": p["sizes"], "color_name": color_of(p)["name"], "slug": p["slug"],
        "shopify_variant_ids": p.get("shopify_variant_ids", {}),
    } for p in PRODUCTS]
    bundles = [{
        "id": b["id"], "kind": "bundle", "name": b["name"], "price": b["price"] if SHOW_PRICES else None, "items": b["items"],
        "shopify_variant_ids": b.get("shopify_variant_ids", {}),
    } for b in BUNDLES]
    public_cfg = {k: CFG[k] for k in ("brand", "launch", "commerce", "email", "analytics")}
    return "window.MR = " + json.dumps({"config": public_cfg, "products": products, "bundles": bundles}, indent=1) + ";\n"


def full_store():
    pages = [page_home(), page_shop(), page_bundles(), page_story(), page_coming_next(), page_size(),
             page_shipping(), page_faq(), page_contact(), page_legal("privacy"), page_legal("terms"), page_cart()]
    return pages + [page_product(p) for p in PRODUCTS]


def waitlist_site():
    return [page_waitlist("index.html"), page_legal("privacy", "simple"), page_legal("terms", "simple")]


def write_site(out, pages, preview):
    STATE["preview"] = preview
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SRC, out, ignore=shutil.ignore_patterns("maison-rivault-logo-*"))
    (out / "assets" / "js" / "data.js").write_text(runtime_data())
    for pg in pages:
        root = "../" if "/" in pg["path"] else ""
        f = out / pg["path"]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(layout(pg["path"], pg["title"], pg["desc"], pg["body"], root=root, chrome=pg["chrome"]))
    print(f"Built {len(pages):>2} pages into {out.relative_to(ROOT)}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["waitlist", "live"], help="override SITE_MODE for ./site")
    args = ap.parse_args()
    mode = args.mode or CFG["SITE_MODE"]
    if mode not in ("waitlist", "live"):
        raise SystemExit(f'SITE_MODE must be "waitlist" or "live", got {mode!r}')

    # Production output, chosen by SITE_MODE.
    write_site(ROOT / "site", waitlist_site() if mode == "waitlist" else full_store(), preview=False)
    print(f"SITE_MODE = {mode}")

    # Full store for design review, plus the waitlist page. Never deploy this folder.
    write_site(ROOT / "preview", full_store() + [page_waitlist("waitlist.html")], preview=True)


if __name__ == "__main__":
    main()
