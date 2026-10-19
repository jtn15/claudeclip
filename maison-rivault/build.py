#!/usr/bin/env python3
"""Build the Maison Rivault site into ./site from site.config.json and data/products.json.

Standard library only. Run:  python3 build.py
Preview:                     python3 -m http.server -d site 8000
"""
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
OUT = ROOT / "site"

CFG = json.loads((ROOT / "site.config.json").read_text())
DATA = json.loads((ROOT / "data" / "products.json").read_text())
COLORS = DATA["colors"]
PRODUCTS = DATA["products"]
BUNDLES = DATA["bundles"]
BY_ID = {p["id"]: p for p in PRODUCTS}


# ---------- helpers ----------

def esc(s):
    return html.escape(str(s), quote=True)


def todo(label):
    """Visible marker for anything the owner still has to confirm. Picked up by tools/check_placeholders.py."""
    return f'<span class="todo">[confirm: {esc(label)}]</span>'


def val(value, label):
    return esc(value) if value not in (None, "") else todo(label)


def money(n):
    return f"${n:,.0f}" if float(n).is_integer() else f"${n:,.2f}"


def color_of(p):
    return COLORS[p["color"]]


def bundle_separate(b):
    return sum(BY_ID[i]["price"] for i in b["items"])


def bundle_saving(b):
    return bundle_separate(b) - b["price"]


def bundle_pct(b):
    return round(100 * bundle_saving(b) / bundle_separate(b))


def ph(caption, ratio="4 / 5", alt=None):
    return (f'<div class="ph" style="aspect-ratio:{ratio}" role="img" '
            f'aria-label="{esc(alt or caption)}"><span>{esc(caption)}</span></div>')


def image(img, ratio="4 / 5", eager=False):
    """Real photo when "src" is set in products.json, neutral placeholder otherwise."""
    if img.get("src"):
        load = "eager" if eager else "lazy"
        return (f'<img class="photo" src="{esc(img["src"])}" alt="{esc(img["alt"])}" '
                f'loading="{load}" style="aspect-ratio:{ratio}">')
    return ph(img["caption"], ratio, img["alt"])


def instagram_url():
    h = CFG.get("instagram_handle", "").lstrip("@")
    return f"https://www.instagram.com/{h}/" if h else None


# ---------- layout ----------

NAV = [("shop.html", "Shop"), ("bundles.html", "Bundles"), ("our-story.html", "Our Story"), ("contact.html", "Contact")]


def layout(path, title, description, body, root="", og_type="website"):
    domain = CFG.get("domain", "").strip()
    full_title = title if title.startswith(CFG["brand"]) else f"{title} | {CFG['brand']}"
    canonical = f'<link rel="canonical" href="https://{esc(domain)}/{path}">' if domain else ""
    og_img = f"https://{domain}/assets/img/og-image.png" if domain else f"{root}assets/img/og-image.png"
    og_url = f'<meta property="og:url" content="https://{esc(domain)}/{path}">' if domain else ""

    nav = "".join(
        f'<a href="{root}{href}"' + (' aria-current="page"' if href == path else "") + f">{label}</a>"
        for href, label in NAV
    )
    ig = instagram_url()
    ig_link = (f'<a href="{esc(ig)}" rel="noopener">Instagram</a>' if ig
               else f'Instagram {todo("Instagram handle")}')

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description)}">
{canonical}
<meta property="og:site_name" content="{esc(CFG['brand'])}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="{og_type}">
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
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="announce label"><p>Drop 001 opens {esc(CFG['launch']['label'])}</p></div>
<header class="site-header">
  <div class="wrap">
    <a class="logo" href="{root}index.html" aria-label="{esc(CFG['brand'])}, home"><span class="logo-lockup" role="img" aria-label="{esc(CFG['brand'])}"></span></a>
    <nav id="site-nav" class="nav label" aria-label="Main">{nav}</nav>
    <div class="header-right label">
      <a class="cart-link" href="{root}cart.html">Cart (<span class="cart-count">0</span>)</a>
      <button class="menu-btn label" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
    </div>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <div class="footer-grid">
      <div class="footer-brand">
        <span class="logo logo-mono" role="img" aria-label="{esc(CFG['brand'])} monogram"></span>
        <p class="muted" style="margin-top:1.25rem">{esc(CFG['tagline'])}</p>
      </div>
      <div class="footer-col"><h2>Shop</h2><ul>
        <li><a href="{root}shop.html">All of Drop 001</a></li>
        <li><a href="{root}bundles.html">Bundles</a></li>
        <li><a href="{root}index.html#waitlist">Waitlist</a></li></ul></div>
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
        <li><a href="#" data-cookie-settings>Cookie settings</a></li></ul></div>
    </div>
    <div class="footer-base">
      <p>&copy; {esc(CFG['established'])} {esc(CFG['brand'])}. Returns: {val(CFG['returns']['window_days'] and CFG['returns']['window_days'] + ' days', 'return window')}. <a href="{root}shipping-returns.html">Details</a></p>
      <p>Est. {esc(CFG['established'])}</p>
    </div>
  </div>
</footer>
<script src="{root}assets/js/data.js"></script>
<script src="{root}assets/js/site.js"></script>
</body>
</html>
"""


# ---------- components ----------

def signup(source, button="Notify me", note=True):
    em = ('<p class="small">One email when Drop 001 opens, and a note about Drop 002. '
          'Unsubscribe any time.</p>') if note else ""
    return f"""<form class="signup js-signup" data-source="{esc(source)}" novalidate>
  <label class="label" style="flex-basis:100%" for="email-{esc(source)}">Email address</label>
  <input id="email-{esc(source)}" type="email" name="email" autocomplete="email" placeholder="you@example.com" required>
  <button class="btn" type="submit">{esc(button)}</button>
</form>
<p class="form-msg" role="status" aria-live="polite"></p>
{em}"""


def product_card(p, root=""):
    c = color_of(p)
    return f"""<a class="card" href="{root}products/{p['slug']}.html" data-type="{esc(p['type'])}">
  {image(p['images'][0], '4 / 5')}
  <div class="card-meta">
    <div><div class="card-name">{esc(p['name'])}</div>
    <div class="card-sub"><span class="swatch" style="background:{c['hex']}"></span>{esc(c['name'])}</div></div>
    <div class="price">{money(p['price'])}</div>
  </div></a>"""


def bundle_block(b, full=False, root=""):
    items = "".join(f"<li>{esc(BY_ID[i]['name'])}, {esc(color_of(BY_ID[i])['name'])}</li>" for i in b["items"])
    tbc = any(BY_ID[i]["availability"] == "tbc" for i in b["items"])
    note = (f'<p class="small">Includes the overshirt, which may arrive after the rest of Drop 001. {todo("overshirt release date")}</p>'
            if tbc else "")
    saving = (f'<p class="saving">Save {money(bundle_saving(b))} ({bundle_pct(b)}%) against buying separately at '
              f'{money(bundle_separate(b))}.</p>')
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
        cta = f"""<div data-when="closed"><a class="btn" href="{root}index.html#waitlist">Join the waitlist</a></div>
<div data-when="open" hidden>
  <div class="bundle-sizes">{selects}</div>
  <button class="btn" type="button" data-add-bundle="{b['id']}">Add bundle to cart</button>
  <p class="form-msg small bundle-msg" role="status" aria-live="polite"></p>
</div>"""
    return f"""<article class="bundle" id="{b['slug']}">
  <h3>{esc(b['name'])}</h3>
  <p class="price">{money(b['price'])}</p>
  <ul>{items}</ul>
  {saving}
  {note if full else ''}
  {cta}
</article>"""


# ---------- pages ----------

def page_home():
    cards = "".join(product_card(p) for p in PRODUCTS)
    bundles = "".join(bundle_block(b) for b in BUNDLES)
    drop2 = ", ".join(DATA["drop_two"][:-1]).lower() + " and " + DATA["drop_two"][-1].lower()
    body = f"""
<section class="hero">
  <div class="wrap">
    <div class="hero-copy">
      <p class="label muted">Drop 001</p>
      <h1>{esc(CFG['tagline'])}</h1>
      <p class="lede">Knitwear for men, built in layers. Six styles, four colors, opening {esc(CFG['launch']['label'])}.</p>
      <div data-when="closed"><a class="btn" href="#waitlist">Join the waitlist</a></div>
      <div data-when="open" hidden><a class="btn" href="shop.html">Shop Drop 001</a></div>
    </div>
    <div class="hero-art">{ph('Hero photo: quarter-zip and polo, window light', '4 / 5')}</div>
  </div>
</section>
<hr class="rule">
<section>
  <div class="wrap">
    <div class="section-head"><h2>Drop 001</h2><a class="label" href="shop.html">View all</a></div>
    <div class="grid">{cards}</div>
  </div>
</section>
<hr class="rule">
<section>
  <div class="wrap">
    <div class="section-head"><h2>Bundles</h2><a class="label" href="bundles.html">View all</a></div>
    <p class="muted" style="margin-bottom:2rem">Four sets, each priced about ten percent under the separate price.</p>
    <div class="bundles">{bundles}</div>
  </div>
</section>
<section class="story-block">
  <div class="col center">
    <p class="statement">{esc(CFG['story_sentence'])}</p>
    <p class="label muted">Est. {esc(CFG['established'])}{' &middot; ' + esc(CFG['location']) if CFG['location'] else ' &middot; ' + todo('location, e.g. Phoenix, Arizona')}</p>
    <p style="margin-top:1.5rem"><a class="label" href="our-story.html">Our story</a></p>
  </div>
</section>
<section id="waitlist">
  <div class="col">
    <h2>Drop 001 opens {esc(CFG['launch']['label'])}.</h2>
    <p class="muted">Leave your email and we will write once when it opens. Drop 002 follows: {esc(drop2)}. It is not for sale yet.</p>
    {signup('home')}
  </div>
</section>"""
    return ("index.html", f"{CFG['brand']}: {CFG['tagline']}",
            "Quiet, well-made men's knitwear in layers. Drop 001 is six styles in navy, camel, olive and cream, opening "
            + CFG["launch"]["label"] + ".", body)


def page_shop():
    types = []
    for p in PRODUCTS:
        if p["type"] not in types:
            types.append(p["type"])
    filters = '<button type="button" data-type="all" aria-pressed="true">All</button>' + "".join(
        f'<button type="button" data-type="{esc(t)}" aria-pressed="false">{esc(t)}</button>' for t in types)
    cards = "".join(product_card(p) for p in PRODUCTS)
    body = f"""
<section class="page-head"><div class="wrap">
  <h1>Drop 001</h1>
  <p class="lede">Six knitwear styles, each in one color. Opens {esc(CFG['launch']['label'])}.</p>
</div></section>
<section style="padding-top:1rem"><div class="wrap">
  <div class="filters" role="group" aria-label="Filter by type">{filters}</div>
  <div class="grid">{cards}</div>
  <p class="muted" style="margin-top:3rem">Buying more than one piece? See the <a href="bundles.html">bundles</a>.</p>
</div></section>"""
    return ("shop.html", "Shop Drop 001", "Six knitwear styles for men in navy, camel, olive and cream. Drop 001 opens "
            + CFG["launch"]["label"] + ".", body)


def page_bundles():
    blocks = "".join(bundle_block(b, full=True) for b in BUNDLES)
    body = f"""
<section class="page-head"><div class="wrap">
  <h1>Bundles</h1>
  <p class="lede">Four sets, each about ten percent under the separate price. The saving is shown on each one.</p>
</div></section>
<section style="padding-top:1rem"><div class="wrap"><div class="bundles">{blocks}</div></div></section>"""
    return ("bundles.html", "Bundles", "Four Drop 001 bundles, each about ten percent under buying the pieces separately.", body)


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
    avail = ""
    if p["availability"] == "tbc":
        avail = f'<p class="status-line">{esc(p["availability_note"])} {todo("release date")}</p>'
    ship = val(CFG["shipping"]["estimate"], "shipping estimate")
    body = f"""
<section style="padding-top:2.5rem"><div class="wrap">
  <p class="crumbs label"><a href="../shop.html">Shop</a> / {esc(p['name'])}</p>
  <div class="product">
    <div class="product-gallery">{gallery}</div>
    <div class="product-info">
      <h1>{esc(p['name'])}</h1>
      <p class="price">{money(p['price'])}</p>
      <p class="card-sub"><span class="swatch" style="background:{c['hex']}"></span>{esc(c['name'])}</p>
      <p>{esc(p['summary'])}</p>
      {avail}
      {size_ui}
      <div style="margin-top:1.25rem">
        <div data-when="closed"><a class="btn btn-block" href="../index.html#waitlist">Join the waitlist</a>
          <p class="small" style="margin-top:0.75rem">Drop 001 opens {esc(CFG['launch']['label'])}.</p></div>
        <div data-when="open" hidden><button class="btn btn-block" type="button" data-add-product="{p['id']}" data-cart-url="../cart.html">Add to cart</button></div>
      </div>
      <p class="small" style="margin-top:1rem">Shipping: {ship}. Returns: see <a href="../shipping-returns.html">shipping and returns</a>.</p>
      <div style="margin-top:2rem">
        <details open><summary class="label">Fabric and fiber content</summary><div><p>{val(p['fiber'], 'fiber content, required by law for US garments')}</p></div></details>
        <details><summary class="label">Fit</summary><div><p>{val(p['fit'], 'fit note')}</p></div></details>
        <details><summary class="label">Care</summary><div><p>{val(p['care'], 'care instructions')}</p></div></details>
        <details><summary class="label">Shipping and returns</summary><div><p>Ships {ship}.</p><p><a href="../shipping-returns.html">Full shipping and returns policy</a></p></div></details>
      </div>
    </div>
  </div>
</div></section>"""
    return (f"products/{p['slug']}.html", f"{p['name']} in {c['name']}",
            f"{p['name']} in {c['name'].lower()}, {money(p['price'])}. {p['summary']}", body)


def page_story():
    body = f"""
<section class="page-head"><div class="col"><h1>Our Story</h1></div></section>
<section style="padding-top:1rem"><div class="col prose">
  <p class="lede">{esc(CFG['story_sentence'])} Est. {esc(CFG['established'])}. {val(CFG['location'], 'location, e.g. Phoenix, Arizona')}</p>
  <p>Maison Rivault begins with a narrow idea: a small set of knitwear, in four colors, that goes together without effort. Navy, camel, olive and cream. Pieces that sit over and under each other, so a cold morning and a mild afternoon call for the same few things.</p>
  <p>Drop 001 is six styles: a quarter-zip, a knit polo, a crewneck, an overshirt, a scarf and a beanie. Each comes in one color, chosen to work with the rest. There are no seasonal reinventions and no long catalog to sort through.</p>
  <p>We are a new brand, and we would rather say so than borrow a history. What we can offer is a short list of well-chosen pieces, described plainly, with fabric, fit and care stated on every page. Drop 002, with a cardigan, trousers and footwear, comes next.</p>
</div></section>
<section class="story-block"><div class="col">
  <h2 style="text-align:center">Join the waitlist</h2>
  <p class="muted" style="text-align:center;margin-left:auto;margin-right:auto">Drop 001 opens {esc(CFG['launch']['label'])}.</p>
  <div style="display:flex;flex-direction:column;align-items:center">{signup('story')}</div>
</div></section>"""
    return ("our-story.html", "Our Story", "Maison Rivault makes quiet, well-made knitwear for men, built in layers. A new brand, est. "
            + CFG["established"] + ".", body)


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
    return ("size-guide.html", "Size guide", "Garment measurements and how to find your size.", body)


def page_shipping():
    s, r = CFG["shipping"], CFG["returns"]
    body = f"""
<section class="page-head"><div class="col"><h1>Shipping and returns</h1></div></section>
<section style="padding-top:1rem"><div class="col prose">
  <h2>Shipping</h2>
  <p><strong>Estimate:</strong> {val(s['estimate'], 'shipping time range, and keep to it')}.</p>
  <p><strong>Cost:</strong> {val(s['cost'], 'shipping cost')}.</p>
  <p><strong>Where we ship:</strong> {val(s['regions'], 'shipping regions')}.</p>
  <p>Drop 001 orders open on {esc(CFG['launch']['label'])}. The estimate above counts from the day an order is placed.</p>
  <h2>Returns</h2>
  <p><strong>Window:</strong> {val(r['window_days'] and r['window_days'] + ' days from delivery', 'return window')}.</p>
  <p><strong>Condition:</strong> {val(r['conditions'], 'return conditions, e.g. unworn with tags')}.</p>
  <p><strong>Return shipping:</strong> {val(r['return_shipping'], 'who pays return shipping')}.</p>
  <p>To start a return, <a href="contact.html">contact us</a> with your order number.</p>
</div></section>"""
    return ("shipping-returns.html", "Shipping and returns", "Shipping times and costs, and how returns work.", body)


def page_faq():
    qa = [
        ("When does Drop 001 open?", f"Drop 001 opens on {esc(CFG['launch']['label'])}. <a href=\"index.html#waitlist\">Join the waitlist</a> and we will email once when it does."),
        ("What colors are available?", "Four colors across the drop: navy, camel, olive and cream. Each style comes in one color. Each product page names its color."),
        ("What is in Drop 002?", "A cardigan, trousers and footwear (loafers and boots). They are announced only and are not for sale yet."),
        ("Will pieces be restocked?", f"{todo('restock plan')}"),
        ("How do the bundles work?", "Each bundle is priced about ten percent under buying the pieces separately. The exact saving is shown on the <a href=\"bundles.html\">bundles page</a>."),
        ("How do I find my size?", "See the <a href=\"size-guide.html\">size guide</a> for garment measurements."),
        ("What is your return policy?", "See <a href=\"shipping-returns.html\">shipping and returns</a>."),
    ]
    items = "".join(f"<details><summary>{q}</summary><div><p>{a}</p></div></details>" for q, a in qa)
    body = f"""
<section class="page-head"><div class="col"><h1>FAQ</h1></div></section>
<section style="padding-top:1rem"><div class="col">{items}</div></section>"""
    return ("faq.html", "FAQ", "Answers about Drop 001, sizing, bundles, shipping and returns.", body)


def page_contact():
    email = CFG.get("contact_email", "")
    mail = f'<a href="mailto:{esc(email)}">{esc(email)}</a>' if email else todo("contact email")
    body = f"""
<section class="page-head"><div class="col"><h1>Contact</h1></div></section>
<section style="padding-top:1rem"><div class="col prose">
  <p>Questions about an order, sizing or a return: write to {mail}.</p>
  <p class="muted">Please include your order number if you have one.</p>
</div></section>"""
    return ("contact.html", "Contact", "Get in touch about orders, sizing or returns.", body)


def page_legal(kind):
    if kind == "privacy":
        title, intro = "Privacy", "This is a plain-language draft. Have a lawyer review it before launch."
        paras = f"""
  <h2>What we collect</h2>
  <p>If you join the waitlist, we collect your email address. When you place an order through our store, the checkout provider collects the details needed to process and ship it.</p>
  <h2>How we use it</h2>
  <p>We use your email to tell you when Drop 001 opens and to share news of Drop 002. You can unsubscribe at any time from any email we send.</p>
  <h2>Cookies and analytics</h2>
  <p>The site stores your cart and your cookie choice in your browser. Analytics and advertising cookies stay off unless you accept them in the banner. You can change your choice from "Cookie settings" in the footer.</p>
  <h2>Contact</h2>
  <p>Questions about your data: {val(CFG.get('contact_email'), 'contact email')}.</p>"""
    else:
        title, intro = "Terms", "This is a plain-language draft. Have a lawyer review it before launch."
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
  <p class="muted">{intro} {todo('legal review')}</p>{paras}
</div></section>"""
    return (f"{kind}.html", title, f"{title} for {CFG['brand']}.", body)


def page_cart():
    body = """
<section class="page-head"><div class="col"><h1>Cart</h1></div></section>
<section style="padding-top:1rem"><div class="col"><div id="cart-root"><noscript><p>The cart needs JavaScript.</p></noscript></div></div></section>"""
    return ("cart.html", "Cart", "Your cart.", body)


# ---------- build ----------

def runtime_data():
    products = [{
        "id": p["id"], "kind": "product", "name": p["name"], "price": p["price"], "sizes": p["sizes"],
        "color_name": color_of(p)["name"], "slug": p["slug"], "shopify_variant_ids": p.get("shopify_variant_ids", {}),
    } for p in PRODUCTS]
    bundles = [{
        "id": b["id"], "kind": "bundle", "name": b["name"], "price": b["price"], "items": b["items"],
        "shopify_variant_ids": b.get("shopify_variant_ids", {}),
    } for b in BUNDLES]
    public_cfg = {k: CFG[k] for k in ("brand", "launch", "commerce", "email", "analytics")}
    return "window.MR = " + json.dumps({"config": public_cfg, "products": products, "bundles": bundles}, indent=1) + ";\n"


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT, ignore=shutil.ignore_patterns("maison-rivault-logo-*"))
    (OUT / "assets" / "js" / "data.js").write_text(runtime_data())

    pages = [page_home(), page_shop(), page_bundles(), page_story(), page_size(), page_shipping(),
             page_faq(), page_contact(), page_legal("privacy"), page_legal("terms"), page_cart()]
    pages += [page_product(p) for p in PRODUCTS]
    for path, title, desc, body in pages:
        root = "../" if "/" in path else ""
        out = OUT / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(layout(path, title, desc, body, root=root))
    print(f"Built {len(pages)} pages into {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
