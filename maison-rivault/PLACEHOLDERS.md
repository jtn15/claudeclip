# Placeholders to replace before launch

Live list: `py build.py` then `py tools/check_placeholders.py`. This is the checklist version.

## Launch switches
- [ ] Confirm the launch target (Mon Dec 14, 2026): `site.config.json` > `launch.target_confirmed`
- [ ] Set `SITE_MODE` to `"live"` when the store should open
- [ ] Set `SHOW_PRICES` to `true` once prices are final
- [ ] Holiday cutoff date: `holiday.cutoff_date`, then `cutoff_confirmed: true`. Until then the site refuses to promise Christmas delivery.

## Business facts (`site.config.json`)
- [ ] Location for the story line (Phoenix, Arizona is unconfirmed): `location`
- [ ] Domain (maisonrivault.com or rivault.com): `domain`
- [ ] Instagram handle (@maisonrivault or @rivault): `instagram_handle`
- [ ] Contact email: `contact_email`
- [ ] Tagline winner. The first candidate is live; alternates are in `tagline_alternates`.

## Products (`data/products.json`)
- [ ] Final prices from supplier quotes: 7 products and 4 bundles (set `price` and `price_status: "final"`)
- [ ] Tier names Signature and Essentials (provisional)
- [ ] Availability mode for each product (`made_to_order`, `in_stock`, `preorder`), then set `availability_status` off `tbc`
- [ ] Which Essentials styles launch (quarter-zip and polo are assumed)
- [ ] Crewneck or mock neck
- [ ] Weekend Layers: the second piece
- [ ] Whether the Layering Bundle and Cold Morning Set use Signature pieces
- [ ] Color for each style (current assignment is a placeholder)
- [ ] Fiber content, care and fit for all 7 products. Fiber content and care are legally required for US garments; have a lawyer confirm wording.
- [ ] Where each garment is made: do not state it until each supplier is confirmed, then state it exactly
- [ ] Product photos: 26 slots, plus the home hero photo (`build.py`, `page_home`)
- [ ] Size chart measurements (`build.py`, `page_size`)
- [ ] Restock answer in the FAQ

## Shipping and policies (`site.config.json`)
- [ ] Made-to-order delivery window, in-stock ship time, preorder ship window
- [ ] Preorder charge policy, stated plainly
- [ ] Shipping cost and regions
- [ ] Return window, conditions, who pays return shipping
- [ ] Legal review of Privacy and Terms, including governing law and business entity name

## Systems
- [ ] Shopify store domain, and variant ids for every product and size
- [ ] Shopify variants for each bundle
- [ ] Klaviyo public key and list id (or another email endpoint)
- [ ] GA4 id and Meta Pixel id, if wanted
- [ ] Redrawn vector logo before any print or embroidery
- [ ] Port the prototype to a Shopify theme (Dawn or custom) using `products.json` as the model
