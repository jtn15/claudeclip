// Crawl + checks for item 20. Usage: node verify.mjs <base> <themeDir>
import { chromium } from 'playwright-core';
import fs from 'node:fs';
const [base, theme] = process.argv.slice(2);
const res = {};
// 1. static: every literal 'x.y' | t key exists in the locale
const loc = JSON.parse(fs.readFileSync(theme + '/locales/en.default.json', 'utf8'));
const files = fs.readdirSync(theme, { recursive: true }).filter(f => f.endsWith('.liquid')).map(f => theme + '/' + f);
const keys = new Set(); const dynamicT = [];
for (const f of files) { const s = fs.readFileSync(f, 'utf8');
  for (const m of s.matchAll(/'([a-z_]+\.[a-z_.]+)'\s*\|\s*t\b/g)) keys.add(m[1]);
  for (const m of s.matchAll(/\{\{[^}]*?([a-z_.\]\[]+)\s*\|\s*(default:[^|]*\|\s*)?t\b[^}]*\}\}/g)) if (!/'[a-z_]+\.[a-z_.]+'\s*\|\s*t/.test(m[0])) dynamicT.push(f.replace(theme + '/', '') + ': ' + m[0]); }
const missingKeys = [...keys].filter(k => typeof k.split('.').reduce((o, p) => o && o[p], loc) !== 'string');
res.static_translation_keys = { checked: keys.size, missing: missingKeys, non_literal_t_calls: dynamicT };
// 2. crawl
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
const ctx = await b.newContext({ viewport: { width: 375, height: 812 }, isMobile: true });
const start = ['/', '/products/the-ashby-quarter-zip', '/pages/faq', '/cart', '/collections/all', '/pages/contact', '/pages/size-guide', '/pages/our-story', '/pages/shipping-returns', '/search'];
const pagesSeen = {}; const links = new Map(); const consoleErr = {};
for (const u of start) {
  const pg = await ctx.newPage(); const errs = [];
  pg.on('console', m => { if (m.type() === 'error') errs.push(m.text()); }); pg.on('pageerror', e => errs.push('pageerror: ' + e));
  pg.on('requestfailed', r => errs.push('requestfailed ' + r.url()));
  pg.on('response', r => { if (r.status() >= 400 && !r.url().includes('/recommendations/')) errs.push(r.status() + ' ' + r.url()); });
  const r = await pg.goto(base + u, { waitUntil: 'networkidle' });
  const text = await pg.evaluate(() => document.body.innerText);
  pagesSeen[u] = { status: r.status(), translation_missing: (text.match(/Translation missing[^\n]*/g) || []) };
  consoleErr[u] = errs.filter(e => !/^404 .*\/pages\/shipping-returns$/.test(e) && !/status of 404/.test(e) || u !== '/pages/shipping-returns');
  for (const h of await pg.$$eval('a[href]', as => as.map(a => a.getAttribute('href')))) {
    if (/^(https?:|mailto:|tel:|#)/.test(h) && !h.startsWith(base)) continue;
    const p = h.replace(base, ''); if (!links.has(p)) links.set(p, new Set()); links.get(p).add(u);
  }
  await pg.close();
}
const linkStatus = {};
for (const [p, from] of links) { const r = await fetch(base + p); linkStatus[p] = { status: r.status, found_on: [...from] }; }
res.pages = pagesSeen; res.links = linkStatus; res.console = consoleErr;
// 3. wording identical
const grab = async (u) => (await (await fetch(base + u)).text()).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
const want = { returns: 'Returns: 30 days.', returns_full: 'Returns are accepted within 30 days of delivery.', shipping: 'Standard Shipping: ships in 1-2 business days, then arrives in 2-7 business days.' };
const wording = {};
for (const u of ['/products/the-ashby-quarter-zip', '/cart', '/pages/faq', '/pages/shipping-returns', '/']) { const t = await grab(u); wording[u] = Object.fromEntries(Object.entries(want).map(([k, v]) => [k, t.includes(v)])); wording[u].old_14_days = /14 days/.test(t); wording[u].old_5_7 = /5-7 business/.test(t); wording[u].comparable = /Comparable value/i.test(t); }
res.wording = wording;
console.log(JSON.stringify(res, null, 1));
await b.close();
