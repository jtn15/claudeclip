# Maison Rivault Shopify theme

An Online Store 2.0 theme (Liquid, no build step, no apps required). It does the same job as the static prototype in `maison-rivault/`, rebuilt for Shopify: waitlist mode, two tiers, availability modes, "Price at launch", bundle pages, and honest `[confirm: ...]` markers wherever a fact is not yet set.

**Status:** passes Shopify Theme Check with 0 errors (the only 6 warnings are the Google Fonts links). Snippet logic (price, availability, holiday notice, bundle saving) is tested. It has **not** been previewed on a live store, so expect to do one visual pass after the first upload and send me what looks off.

## Upload

1. Get `shopify-theme.zip` from the root of this repo (or run `python3 shopify-theme/make_zip.py` to rebuild it).
2. Shopify admin > **Online Store > Themes > Add theme > Upload zip file**.
3. Click **Customize** to edit, or **Publish** when ready. Do not publish before step "Set up the store" below.

## Set up the store (the theme reads this data; it does not create it)

### 1. Metafield definitions
Settings > **Custom data > Products > Add definition**. Namespace and key must be exactly these (the default namespace is `custom`):

| Name | Key | Type | Used for |
| --- | --- | --- | --- |
| Availability | `availability` | Single line text | `made_to_order`, `in_stock` or `preorder` |
| Tier | `tier` | Single line text | `Signature` or `Essentials` |
| Color | `color` | Single line text | `Navy`, `Camel`, `Olive` or `Cream` |
| Fiber content | `fiber` | Multi-line text | Fabric and fiber content (legally required) |
| Fit | `fit` | Multi-line text | Fit note |
| Care | `care` | Multi-line text | Care instructions |
| Bundle items | `bundle_items` | List of products | Pieces in a bundle (bundles only) |
| Bundle open slots | `bundle_open_slots` | Integer | Pieces still to be chosen, e.g. `1` for The Weekend Layers |

Set each metafield's storefront access to **Active** if Shopify asks.

### 2. Products
- Create the 7 products: Signature quarter-zip, knit polo, crewneck, scarf, beanie; Essentials quarter-zip and knit polo. Prices can be `0` until quotes arrive. With **Show prices** off in theme settings, the site says "Price at launch" and Add to cart is disabled regardless.
- Tops: add an option named **Size** with S, M, L, XL, XXL. Scarf and beanie: leave the single default variant.
- Tags for the shop filters: `tier-signature` or `tier-essentials`, plus `type-tops` or `type-accessories`.
- Fill the metafields above on each product. Anything left empty shows a `[confirm: ...]` marker on the page.
- Made-to-order and preorder products: tick **Continue selling when out of stock** on each variant, or customers cannot buy them.

### 3. Bundles
- Create 4 products named The Layering Bundle, The Cold Morning Set, The Weekend Layers, The Full Rotation. Each has **one variant** (no Size option) and a price.
- Set `bundle_items` to the pieces it contains, and `availability` as for any product. The Weekend Layers: add the crewneck and set `bundle_open_slots` to `1` until the second piece is chosen.
- Customers choose each piece's size on the bundle page. Sizes arrive on the order as line item properties ("Quarter-zip size: M"), so you can read them when you make the order.
- Create a collection with the handle **`bundles`** containing the four bundles, and assign it the **collection.bundles** template. Product pages use this collection to show "Also available as a bundle".

### 4. Collections
Create `signature` and `essentials` collections and pick them in the home page sections (Customize > Home). Create a "Shop" collection with the 7 products (not the bundles) for the Shop menu link, so the tier and type filters work.

### 5. Pages
Create these pages and pick the matching template for each. The handles matter because the theme links to them:

| Page title | Handle | Template |
| --- | --- | --- |
| Our Story | `our-story` | `page.our-story` |
| Size guide | `size-guide` | `page.size-guide` |
| Shipping and returns | `shipping-returns` | `page.shipping-returns` |
| FAQ | `faq` | `page.faq` |
| Contact | `contact` | `page.contact` |
| Coming next | `coming-next` | `page.coming-next` |

### 6. Menus
Online Store > Navigation. **main-menu**: Shop, Bundles, Our Story, Contact (four items). **footer**: Size guide, Shipping and returns, FAQ, Contact, Coming next.

### 7. Waitlist mode
This is Shopify's storefront password. Online Store > **Preferences > Restrict access**: turn on the password. Visitors then see the waitlist page (logo, one line, email field, "Doors open mid-December."). The password field is under "Enter using password" at the bottom of that page. Turn the password off to open the store.

### 8. Theme settings (Customize > Theme settings)
Upload the favicon and Apple touch icon from `shopify-theme-brand/`. Fill in shipping windows, preorder policy, returns, contact email, Instagram handle and location as each is decided. Leave the holiday cutoff blank until a date is confirmed. Tick **Show prices and allow Add to cart** only when prices are final. Also upload `og-image.png` as the social sharing image under Online Store > Preferences.

### 9. Email, cookies and legal
- Waitlist signups use Shopify's own customer form: they appear under Customers with email marketing subscribed and the tag `waitlist` (or `coming-next`). They sync to Shopify Email or Klaviyo with no custom code.
- This theme has no cookie banner of its own. Use Shopify's: Settings > **Customer privacy**. Add GA4 and the Meta Pixel through Shopify's Google and Meta channels so they follow that consent.
- Privacy, terms and refund pages are Shopify policies: Settings > **Policies** (use the generators, then have a lawyer review). The footer's Legal column lists whichever exist.

## Differences from the static prototype
Cookie banner, Privacy and Terms pages, and the checkout hand-off are Shopify's own instead of custom code. Filters use product tags. Bundles are real products with sizes as line item properties instead of a client-side cart.

## What the theme will not do
It will not state where garments are made, call anything handmade or limited edition, show a fake saving, or promise Christmas delivery without a confirmed cutoff. Every missing fact shows as an orange `[confirm: ...]` marker, and you can find them all by searching the live site for `confirm:`.
