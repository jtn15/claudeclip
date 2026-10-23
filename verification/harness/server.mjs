// Local approximation of Shopify's storefront renderer for the Maison Rivault theme.
// Usage: node server.mjs <themeDir> <port>
// Mock store data only. Not a substitute for `shopify theme dev`.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { Liquid, Tag, Hash } from 'liquidjs';

const THEME = path.resolve(process.argv[2]);
const PORT = Number(process.argv[3] || 9292);
const HERE = path.dirname(new URL(import.meta.url).pathname);
const read = (p) => fs.readFileSync(path.join(THEME, p), 'utf8');
const locale = JSON.parse(read('locales/en.default.json'));

// ---------- settings: schema defaults + settings_data ----------
const schema = JSON.parse(read('config/settings_schema.json'));
const settings = {};
for (const g of schema) for (const s of g.settings || []) if ('default' in s) settings[s.id] = s.default;
Object.assign(settings, JSON.parse(read('config/settings_data.json')).current);
for (const k of ['logo', 'social_image', 'favicon', 'apple_touch_icon']) delete settings[k];
settings.type_header_font = settings.type_body_font = null;
settings.show_prices = true; // so the add-to-cart button renders as it does on the live store
settings.dynamic_checkout = false;

// ---------- mock catalog ----------
let imgId = 1000;
const mkImg = (n, alt = '') => ({ id: ++imgId, src: `/img/p${n}.jpg`, alt, width: 800, height: 1000, aspect_ratio: 0.8 });
const names = ['Ashby Quarter Zip', 'Beaumont Polo', 'Carrington Jeans', 'Hartwell Half Zip', 'Hollis Knit Tee', 'Lockhart Jacket', 'Sinclair Pullover', 'Whitlock Cardigan'];
const handles = ['the-ashby-quarter-zip', 'the-beaumont-polo', 'the-carrington-jeans', 'the-hartwell-half-zip', 'the-hollis-knit-tee', 'the-lockhart-jacket', 'the-sinclair-pullover', 'the-whitlock-cardigan'];
const prices = [7900, 4900, 6900, 8900, 3900, 7500, 6500, 6900];
const META = JSON.parse(process.env.MOCK_META || '{}');
const products = names.map((name, i) => {
  const images = [1, 2, 3, 4].map((n) => mkImg(((n + i - 1) % 6) + 1));
  const sizes = ['S', 'M', 'L', 'XL'];
  const variants = sizes.map((sz, j) => ({ id: 40000 + i * 10 + j, title: sz, options: [sz], option1: sz, available: true, price: prices[i], compare_at_price: i === 1 ? 6500 : null, featured_image: null }));
  return {
    id: 7000 + i, title: `The ${name}`, handle: handles[i], url: `/products/${handles[i]}`, type: 'Knitwear', available: true,
    price: prices[i], price_varies: false, compare_at_price: i === 1 ? 6500 : null, description: '<p>A clean, easy layer in a soft cotton blend.</p>',
    images, featured_image: images[0], media: images, options: ['Size'], options_with_values: [{ name: 'Size', values: sizes, position: 1 }],
    has_only_default_variant: false, variants, selected_or_first_available_variant: variants[0], collections: [],
    metafields: { custom: { fiber: { value: '100% cotton' }, fit: { value: 'Relaxed through the body.' }, care: { value: 'Machine wash cold.' }, ...(META.custom || {}) }, reviews: META.reviews || {} },
  };
});
const essentials = { id: 1, title: 'Essentials', handle: 'essentials', url: '/collections/essentials', products, products_count: products.length, all_products_count: products.length, description: '', image: null, filters: [], sort_options: [], sort_by: '', default_sort_by: 'manual' };
const allColl = { ...essentials, id: 2, title: 'All', handle: 'all', url: '/collections/all' };
products.forEach((p) => (p.collections = [essentials]));
const collections = { essentials, all: allColl };

// Pages that exist in the admin. shipping-returns is deliberately absent unless MOCK_SHIPPING_PAGE=1 (owner creates it).
const pageDefs = { faq: 'FAQ', contact: 'Contact', 'size-guide': 'Size guide', 'our-story': 'Our story' };
if (process.env.MOCK_SHIPPING_PAGE) pageDefs['shipping-returns'] = 'Shipping and returns';
const pages = Object.fromEntries(Object.entries(pageDefs).map(([h, t]) => [h, { title: t, handle: h, url: `/pages/${h}`, content: '', template_suffix: h }]));

const link = (title, url) => ({ title, url, active: false, links: [] });
// The footer menu is admin-managed (handle "footer"); these are assumed entries for the crawl.
const linklists = {
  'main-menu': { handle: 'main-menu', links: [link('Shop', '/collections/all'), link('Our Story', '/pages/our-story'), link('Contact', '/pages/contact')] },
  footer: { handle: 'footer', links: [link('Shipping and returns', '/pages/shipping-returns'), link('Size guide', '/pages/size-guide'), link('FAQ', '/pages/faq'), link('Contact', '/pages/contact')] },
};
const policies = [['Refund policy', 'refund-policy'], ['Privacy policy', 'privacy-policy'], ['Terms of service', 'terms-of-service'], ['Shipping policy', 'shipping-policy']].map(([t, h]) => ({ title: t, url: `/policies/${h}`, body: '' }));
const shop = {
  name: 'Maison Rivault', description: '', customer_accounts_enabled: false, policies, refund_policy: { body: '' }, shipping_policy: { body: '' },
  enabled_payment_types: ['visa', 'master', 'american_express', 'apple_pay', 'google_pay', 'shopify_pay', 'paypal'], currency: 'USD',
};
const mkCart = (n) => {
  const items = products.slice(0, n).map((p, i) => ({ index: i + 1, quantity: 1, url: p.url, image: p.featured_image, product: p, variant: p.variants[1], properties: {}, original_line_price: p.price, final_line_price: p.price, url_to_remove: `/cart/change?line=${i + 1}&quantity=0` }));
  return { item_count: n, items, total_price: items.reduce((a, b) => a + b.final_line_price, 0) };
};
const routes = { root_url: '/', cart_url: '/cart', cart_add_url: '/cart/add', search_url: '/search', account_url: '/account', all_products_collection_url: '/collections/all', product_recommendations_url: '/recommendations/products', collections_url: '/collections' };

// ---------- engine ----------
const missing = new Set();
const engine = new Liquid({ root: [path.join(THEME, 'snippets')], extname: '.liquid', strictFilters: false, jsTruthy: false, dynamicPartials: true });
const lookup = (key) => key.split('.').reduce((o, k) => (o && typeof o === 'object' ? o[k] : undefined), locale);
engine.registerFilter('t', (key, ...args) => {
  let v = lookup(String(key));
  if (typeof v !== 'string') { missing.add(String(key)); return `Translation missing: en.${key}`; }
  for (const [k, val] of args.filter(Array.isArray)) v = v.replaceAll(`{{ ${k} }}`, val);
  return v;
});
const money = (c) => { if (c == null || c === '') return ''; c = Number(c); return '$' + (c % 100 === 0 ? (c / 100).toString() : (c / 100).toFixed(2)); };
engine.registerFilter('money_without_trailing_zeros', money);
engine.registerFilter('money', (c) => '$' + (Number(c) / 100).toFixed(2));
engine.registerFilter('image_url', (img, ...args) => { if (!img) return ''; const src = typeof img === 'string' ? img : img.src; const w = (args.find((a) => a[0] === 'width') || [])[1]; return src + (w ? `?width=${w}` : ''); });
engine.registerFilter('image_tag', (url, ...args) => {
  const o = Object.fromEntries(args.filter(Array.isArray)); const base = String(url).split('?')[0];
  const srcset = o.widths ? ` srcset="${String(o.widths).split(',').map((w) => `${base}?width=${w.trim()} ${w.trim()}w`).join(', ')}"` : '';
  const attrs = Object.entries(o).filter(([k]) => k !== 'widths').map(([k, v]) => `${k}="${v}"`).join(' ');
  return `<img src="${url}"${srcset} ${attrs}>`;
});
engine.registerFilter('asset_url', (f) => `/assets/${f}`);
engine.registerFilter('stylesheet_tag', (u) => `<link rel="stylesheet" href="${u}">`);
engine.registerFilter('handleize', (s) => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''));
engine.registerFilter('structured_data', () => '{}');
engine.registerFilter('payment_button', () => '');
engine.registerFilter('default_errors', () => '');
engine.registerFilter('font_url', () => '');
engine.registerFilter('font_face', () => '');
engine.registerFilter('payment_type_svg_tag', (t, ...args) => { const o = Object.fromEntries(args.filter(Array.isArray)); return `<svg class="${o.class || ''}" viewBox="0 0 38 24" width="38" height="24" role="img" aria-labelledby="pi-${t}"><title id="pi-${t}">${t}</title><rect width="38" height="24" rx="3" fill="#fff" stroke="#ccc"/><text x="19" y="15" font-size="6" text-anchor="middle">${t}</text></svg>`; });
engine.registerFilter('video_tag', () => '');
engine.registerFilter('external_video_tag', () => '');
engine.registerFilter('format_code', (c) => c);

class FormTag extends Tag {
  constructor(token, remain, liquid) {
    super(token, remain, liquid);
    const m = token.args.match(/^\s*'([^']+)'\s*(.*)$/s); this.type = m[1]; this.rest = m[2];
    this.tpls = []; const stream = liquid.parser.parseStream(remain);
    stream.on('tag:endform', () => stream.stop()).on('template', (t) => this.tpls.push(t)).on('end', () => { throw new Error('form not closed'); }); stream.start();
  }
  *render(ctx, emitter) {
    const attrs = [...this.rest.matchAll(/([\w-]+):\s*([^,]+)/g)];
    let out = ''; for (const [, k, expr] of attrs) { const v = yield this.liquid.evalValue(expr.trim(), ctx); out += ` ${k}="${v}"`; }
    const action = { product: '/cart/add', customer: '/contact#signup', contact: '/contact' }[this.type] || '/';
    emitter.write(`<form method="post" action="${action}"${out}><input type="hidden" name="form_type" value="${this.type}">`);
    ctx.push({ form: { errors: null, 'posted_successfully?': false } });
    yield this.liquid.renderer.renderTemplates(this.tpls, ctx, emitter); ctx.pop(); emitter.write('</form>');
  }
}
engine.registerTag('form', FormTag);
class Skip extends Tag { constructor(token, remain, liquid, name) { super(token, remain, liquid); const end = 'end' + token.name; while (remain.length) { const t = remain.shift(); if (t.name === end) return; } } render() { return ''; } }
engine.registerTag('schema', Skip);
class Paginate extends Tag {
  constructor(token, remain, liquid) { super(token, remain, liquid); this.tpls = []; const s = liquid.parser.parseStream(remain); s.on('tag:endpaginate', () => s.stop()).on('template', (t) => this.tpls.push(t)).on('end', () => { throw new Error('x'); }); s.start(); }
  *render(ctx, em) { ctx.push({ paginate: { previous: null, next: null, pages: 1 } }); yield this.liquid.renderer.renderTemplates(this.tpls, ctx, em); ctx.pop(); }
}
engine.registerTag('paginate', Paginate);
class Sections extends Tag {
  constructor(token, remain, liquid) { super(token, remain, liquid); this.group = token.args.replace(/['"\s]/g, ''); }
  *render(ctx, em) { const g = JSON.parse(read(`sections/${this.group}.json`)); em.write(yield renderSections(g, ctx.getAll())); }
}
engine.registerTag('sections', Sections);

function sectionSchema(type) { const src = read(`sections/${type}.liquid`); const m = src.match(/\{%-?\s*schema\s*-?%\}([\s\S]*?)\{%-?\s*endschema/); return m ? JSON.parse(m[1]) : {}; }
function resolveSetting(def, v) {
  if (def && def.type === 'link_list' && typeof v === 'string') return linklists[v] || null;
  if (def && def.type === 'collection' && typeof v === 'string') return collections[v] || null;
  if (def && def.type === 'page' && typeof v === 'string') return pages[v] || null;
  if (def && def.type === 'image_picker' && typeof v === 'string') return v ? mkImg(1) : null;
  return v;
}
function buildSettings(defs = [], given = {}) { const out = {}; for (const d of defs) { if (!d.id) continue; out[d.id] = resolveSetting(d, d.id in given ? given[d.id] : d.default); } return out; }
async function renderSections(tmpl, scope) {
  let html = '';
  for (const id of tmpl.order) {
    const s = tmpl.sections[id]; if (s.disabled) continue;
    const sch = sectionSchema(s.type);
    const blocks = (s.block_order || Object.keys(s.blocks || {})).map((bid) => { const b = s.blocks[bid]; const bdef = (sch.blocks || []).find((x) => x.type === b.type) || {}; return { id: bid, type: b.type, settings: buildSettings(bdef.settings, b.settings), shopify_attributes: '' }; });
    const section = { id: `template--${id}`, settings: buildSettings(sch.settings, s.settings || {}), blocks };
    html += `<div id="shopify-section-${id}" class="shopify-section">` + (await engine.parseAndRender(read(`sections/${s.type}.liquid`), { ...scope, section }, { globals: GLOBALS(scope) })) + '</div>';
  }
  return html;
}

const GLOBALS = (sc) => ({ settings, shop, routes, linklists, collections, pages, cart: sc.cart, request: sc.request, template: sc.template, product: sc.product });
async function page(templateName, scope) {
  const tmpl = JSON.parse(read(`templates/${templateName}.json`));
  const base = { settings, shop, routes, linklists, collections, pages, cart: scope.cart || mkCart(0), request: { design_mode: false, locale: { iso_code: 'en' } }, template: { name: templateName.split('.')[0], suffix: templateName.split('.')[1] || null }, page_title: scope.title || 'Maison Rivault', canonical_url: 'http://localhost', content_for_header: '', recommendations: { performed: false }, ...scope };
  base.content_for_layout = await renderSections(tmpl, base);
  return engine.parseAndRender(read('layout/theme.liquid'), base, { globals: GLOBALS(base) });
}

const MIME = { '.css': 'text/css', '.js': 'application/javascript', '.png': 'image/png', '.jpg': 'image/jpeg' };
http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://x'); const p = u.pathname.replace(/\/$/, '') || '/';
  try {
    if (p.startsWith('/assets/') || p.startsWith('/img/')) {
      const f = p.startsWith('/img/') ? path.join(HERE, p) : path.join(THEME, p);
      if (!fs.existsSync(f)) { res.writeHead(404); return res.end(); }
      res.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' }); return res.end(fs.readFileSync(f));
    }
    let html, status = 200;
    const cartN = Number(u.searchParams.get('cart') || 2);
    if (p === '/') html = await page('index', { title: 'Maison Rivault' });
    else if (p.startsWith('/products/')) { const pr = products.find((x) => x.handle === p.split('/')[2]); if (pr) html = await page('product', { product: pr, title: pr.title }); }
    else if (p.startsWith('/collections/')) { const c = collections[p.split('/')[2]]; if (c) html = await page('collection', { collection: c, title: c.title }); }
    else if (p === '/collections') html = await page('list-collections', {});
    else if (p === '/cart') html = await page('cart', { cart: mkCart(cartN), title: 'Cart' });
    else if (p.startsWith('/pages/')) { const pg = pages[p.split('/')[2]]; if (pg) { const t = fs.existsSync(path.join(THEME, `templates/page.${pg.handle}.json`)) ? `page.${pg.handle}` : 'page'; html = await page(t, { page: pg, title: pg.title }); } }
    else if (p.startsWith('/policies/')) { if (policies.some((x) => x.url === p)) html = '<!doctype html><title>policy</title><p>Shopify policy page</p>'; }
    else if (p === '/search') html = await page('search', { search: { performed: false, results: [], terms: '' } });
    else if (p === '/__missing') { res.writeHead(200, { 'content-type': 'application/json' }); return res.end(JSON.stringify([...missing])); }
    if (!html) { status = 404; html = await page('404', { title: '404' }); }
    res.writeHead(status, { 'content-type': 'text/html' }); res.end(html);
  } catch (e) { res.writeHead(500, { 'content-type': 'text/plain' }); res.end(String(e.stack)); }
}).listen(PORT, () => console.log('listening', PORT));
