# Placeholders to replace before launch

Run `python3 build.py && python3 tools/check_placeholders.py` for the live list. This is the checklist version.

## Business facts
- [ ] Location for the story line (Phoenix, Arizona is unconfirmed): `site.config.json` > `location`
- [ ] Domain (maisonrivault.com or rivault.com): `domain`. Also fills canonical and share-image URLs.
- [ ] Instagram handle (@maisonrivault or @rivault): `instagram_handle`
- [ ] Contact email: `contact_email`
- [ ] Tagline winner. The first candidate is live; alternates are in `tagline_alternates`.

## Products (`data/products.json`)
- [ ] Final prices from supplier quotes, then set `price_status` to `final` (10 items)
- [ ] Color assigned to each style. The current assignment is a placeholder.
- [ ] Crewneck or mock-neck decision (the page says "Knit crewneck" for now)
- [ ] Overshirt release date, which affects The Weekend Layers and The Full Rotation
- [ ] Fiber content for all six styles. Required by law for US garments; have a lawyer confirm wording.
- [ ] Care instructions and fit note for all six styles
- [ ] Size chart measurements (`size-guide.html`, edit in `build.py`)
- [ ] Product photos, 23 slots across six styles, shot Nov 9 to 22, plus the home hero photo (`build.py`, `page_home`)
- [ ] Restock answer in the FAQ

## Policies (`site.config.json`)
- [ ] Shipping estimate (a real range you will keep), cost and regions
- [ ] Return window, conditions and who pays return shipping
- [ ] Legal review of Privacy and Terms, including governing law and business entity name

## Systems
- [ ] Shopify store domain and variant ids for every product and size
- [ ] Shopify variants for each bundle and size combination
- [ ] Klaviyo public key and list id (or a Shopify Email endpoint)
- [ ] GA4 id and Meta Pixel id, if wanted
- [ ] Redrawn vector logo before any print or embroidery
