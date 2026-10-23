/* Maison Rivault theme 3.0.0. Dependency-free: mobile menu, variant picker, add to cart, recommendations, auto-submitting filters.
   Everything degrades to plain HTML if this file does not run. Checkout stays Shopify's own. */
(function () {
  var strings = {};
  try { strings = JSON.parse(document.getElementById('theme-strings').textContent); } catch (e) {}

  /* ---------- Mobile menu: Escape and outside click close it; without JS the links simply show ---------- */
  var btn = document.querySelector('.menu-btn');
  var nav = document.getElementById('site-nav');
  if (btn && nav) {
    var setMenu = function (open) {
      nav.classList.toggle('open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    };
    btn.addEventListener('click', function () { setMenu(!nav.classList.contains('open')); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('open')) { setMenu(false); btn.focus(); }
    });
    document.addEventListener('click', function (e) {
      if (nav.classList.contains('open') && !nav.contains(e.target) && !btn.contains(e.target)) { setMenu(false); }
    });
  }

  /* ---------- Dialogs (size chart): native <dialog>, Escape closes, click outside closes ---------- */
  document.querySelectorAll('[data-open-dialog]').forEach(function (opener) {
    var dlg = document.getElementById(opener.getAttribute('data-open-dialog'));
    if (!dlg || typeof dlg.showModal !== 'function') { return; }
    opener.addEventListener('click', function () { dlg.showModal(); });
    dlg.addEventListener('click', function (e) {
      if (e.target === dlg || e.target.hasAttribute('data-close-dialog')) { dlg.close(); }
    });
    dlg.addEventListener('close', function () { opener.focus(); });
  });

  /* ---------- Welcome popup: email -> optional phone -> discount code ---------- */
  (function () {
    var dlg = document.getElementById('welcome-popup');
    if (!dlg || typeof dlg.showModal !== 'function') { return; }
    var form = dlg.querySelector('form');
    var steps = dlg.querySelectorAll('.popup-step');
    var errBox = dlg.querySelector('.popup-error');
    var phoneInput = document.getElementById('popup-phone');
    var KEY = 'mr_popup';
    var forced = /[?&]popup=1/.test(window.location.search);
    var email = '';

    function store(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
    function read() { try { return localStorage.getItem(KEY) || ''; } catch (e) { return ''; } }
    function show(n) {
      steps.forEach(function (s) { s.hidden = s.getAttribute('data-step') !== String(n); });
      if (phoneInput) { phoneInput.disabled = n !== 2; }
      if (errBox) { errBox.hidden = true; }
      var first = dlg.querySelector('.popup-step:not([hidden]) input:not([type="hidden"]), .popup-step:not([hidden]) a, .popup-step:not([hidden]) button');
      if (first) { first.focus(); }
    }
    function error(msg) { if (errBox) { errBox.textContent = msg; errBox.hidden = false; } }

    /* Don't show again: 7 days after closing, or for good after signing up */
    var saved = read();
    var skip = false;
    if (saved === 'done') { skip = true; }
    else if (saved) { var t = parseInt(saved.replace('closed:', ''), 10); if (t && Date.now() - t < 7 * 864e5) { skip = true; } }
    if (!skip || forced) {
      setTimeout(function () { if (!dlg.open) { dlg.showModal(); show(1); } }, forced ? 300 : (parseInt(dlg.getAttribute('data-delay'), 10) || 8) * 1000);
    }

    dlg.addEventListener('click', function (e) {
      if (e.target === dlg || e.target.hasAttribute('data-popup-close')) { dlg.close(); }
    });
    dlg.addEventListener('close', function () { if (read() !== 'done') { store('closed:' + Date.now()); } });

    function post(extra) {
      var fd = new FormData(form);
      Object.keys(extra).forEach(function (k) { fd.set(k, extra[k]); });
      return fetch(form.action, { method: 'POST', body: fd, credentials: 'same-origin' });
    }

    form.addEventListener('submit', function (e) {
      var step = dlg.querySelector('.popup-step:not([hidden])');
      var n = step ? step.getAttribute('data-step') : '1';
      if (n === '3' || !window.fetch || !window.FormData) { return; }
      e.preventDefault();
      if (n === '1') {
        email = document.getElementById('popup-email').value.trim();
        if (!email) { error('Please enter your email.'); return; }
        post({ 'contact[email]': email, 'contact[tags]': 'newsletter,welcome-popup' })
          .then(function (res) {
            if (res.url.indexOf('/challenge') > -1) { form.submit(); return; } /* Shopify spam check: finish the normal way */
            if (res.url.indexOf('customer_posted=true') === -1) { error('That email did not go through. Check it and try again.'); return; }
            store('done');
            show(2);
          })
          .catch(function () { error('Something went wrong. Please try again.'); });
      } else if (n === '2') {
        var phone = phoneInput.value.trim();
        if (!phone) { show(3); return; }
        phoneInput.disabled = false;
        post({ 'contact[email]': email, 'contact[phone]': phone, 'contact[tags]': 'newsletter,welcome-popup,sms-opt-in' })
          .then(function () { show(3); })
          .catch(function () { show(3); });
      }
    });

    var skipBtn = dlg.querySelector('[data-popup-skip]');
    if (skipBtn) { skipBtn.addEventListener('click', function () { show(3); }); }
    var copyBtn = dlg.querySelector('[data-popup-copy]');
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        var code = dlg.getAttribute('data-code');
        if (navigator.clipboard) { navigator.clipboard.writeText(code).then(function () { copyBtn.textContent = 'Copied'; }); }
      });
    }
  })();

  /* ---------- Cart count ---------- */
  function setCartCount(n) {
    document.querySelectorAll('[data-cart-count]').forEach(function (el) { el.textContent = n; });
  }

  /* ---------- Filters: submit when a box changes ---------- */
  document.querySelectorAll('form[data-auto-submit]').forEach(function (f) {
    f.addEventListener('change', function () { f.submit(); });
  });

  /* ---------- Estimated delivery dates: today + N business days (weekends skipped) ---------- */
  document.querySelectorAll('[data-delivery-estimate]').forEach(function (node) {
    var min = parseInt(node.getAttribute('data-min'), 10);
    var max = parseInt(node.getAttribute('data-max'), 10);
    var tpl = node.getAttribute('data-template');
    if (!(min > 0) || !(max >= min) || !tpl || !window.Intl) { return; }
    var addBusinessDays = function (n) {
      var d = new Date();
      while (n > 0) { d.setDate(d.getDate() + 1); if (d.getDay() !== 0 && d.getDay() !== 6) { n--; } }
      return d;
    };
    try {
      var fmt = new Intl.DateTimeFormat(document.documentElement.lang || undefined, { weekday: 'short', month: 'short', day: 'numeric' });
      var day = function (n) { return fmt.format(addBusinessDays(n)).replace(/ /g, '\u00a0'); };
      node.textContent = tpl.replace('%range%', day(min) + ' \u2013 ' + day(max));
    } catch (e) {}
  });

  /* ---------- Related products (Recommendations API) ---------- */
  document.querySelectorAll('.js-recommendations[data-url]').forEach(function (box) {
    if (!window.fetch) { return; }
    fetch(box.dataset.url)
      .then(function (r) { return r.ok ? r.text() : ''; })
      .then(function (html) {
        if (!html) { return; }
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var recs = doc.querySelector('.js-recs');
        if (recs) { box.innerHTML = recs.outerHTML; }
      })
      .catch(function () {});
  });

  /* ---------- Product form ---------- */
  var form = document.getElementById('product-form');
  if (!form) { return; }

  var priceWrap = document.querySelector('[data-price-wrap]');
  var addBtn = form.querySelector('[name="add"]');
  var msg = form.querySelector('.cart-msg');
  var err = form.querySelector('.cart-error');
  var addLabel = addBtn ? (addBtn.getAttribute('data-add-label') || addBtn.textContent) : '';
  var canBuy = !!(addBtn && addBtn.hasAttribute('data-add-label'));

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    n.textContent = text;
    return n;
  }

  var variants = [];
  try { variants = JSON.parse(document.getElementById('variant-data').textContent); } catch (e) {}
  var select = form.querySelector('select[name="id"]');
  var groups = form.querySelectorAll('.variant-picker');

  /* Show the chosen variant's price (real price only, no crossed-out comparison) */
  var stickyPrice = document.querySelector('[data-sticky-price]');
  function showPrice(v) {
    if (stickyPrice && v.price) { stickyPrice.textContent = v.price; }
    if (!priceWrap) { return; }
    priceWrap.textContent = '';
    if (v.price) { priceWrap.appendChild(el('span', 'price', v.price)); }
  }
  /* Add button follows the chosen variant: Sold out when that combination is unavailable */
  function showButton(v) {
    if (!addBtn || !canBuy) { return; }
    if (v.available) { addBtn.disabled = false; addBtn.textContent = addLabel; }
    else { addBtn.disabled = true; addBtn.textContent = strings.soldOut || 'Sold out'; }
  }
  /* Carousel: arrows, thumbnails, swipe (native scroll-snap) */
  var gallery = document.querySelector('[data-gallery]');
  var track = gallery ? gallery.querySelector('.gallery-track') : null;
  var slides = track ? Array.prototype.slice.call(track.children) : [];
  var thumbs = [];
  var prevBtn, nextBtn;
  function current() { return track ? Math.round(track.scrollLeft / (track.clientWidth || 1)) : 0; }
  function goTo(i, smooth) {
    if (!track) { return; }
    i = Math.max(0, Math.min(slides.length - 1, i));
    track.scrollTo({ left: i * track.clientWidth, behavior: smooth === false ? 'auto' : 'smooth' });
  }
  function sync() {
    var i = current();
    if (prevBtn) { prevBtn.disabled = i <= 0; nextBtn.disabled = i >= slides.length - 1; }
    thumbs.forEach(function (t, n) { t.setAttribute('aria-current', n === i ? 'true' : 'false'); });
  }
  if (track && slides.length > 1) {
    gallery.classList.add('has-carousel');
    prevBtn = el('button', 'gallery-arrow gallery-prev', '\u2039');
    nextBtn = el('button', 'gallery-arrow gallery-next', '\u203A');
    prevBtn.type = nextBtn.type = 'button';
    prevBtn.setAttribute('aria-label', 'Previous photo');
    nextBtn.setAttribute('aria-label', 'Next photo');
    prevBtn.addEventListener('click', function () { goTo(current() - 1); });
    nextBtn.addEventListener('click', function () { goTo(current() + 1); });
    gallery.insertBefore(prevBtn, track);
    gallery.insertBefore(nextBtn, track);
    /* Thumbnails are rendered by Liquid with their own small images (main-product.liquid); this only wires them up */
    var strip = gallery.querySelector('[data-gallery-thumbs]');
    if (strip) {
      thumbs = Array.prototype.slice.call(strip.querySelectorAll('.gallery-thumb'));
      thumbs.forEach(function (b, n) {
        b.setAttribute('aria-label', 'Show photo ' + (n + 1));
        b.addEventListener('click', function () { goTo(n); });
      });
      strip.hidden = false;
    }
    var tick;
    track.addEventListener('scroll', function () { clearTimeout(tick); tick = setTimeout(sync, 60); });
    window.addEventListener('resize', function () { goTo(current(), false); sync(); });
    gallery.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { goTo(current() - 1); } else if (e.key === 'ArrowRight') { goTo(current() + 1); }
    });
    sync();
  }
  /* Jump to the chosen color's photo */
  function showImage(v) {
    if (!track || !v.image) { return; }
    for (var i = 0; i < slides.length; i++) {
      if (slides[i].querySelector('[data-image-id="' + v.image + '"]') || slides[i].getAttribute('data-image-id') === String(v.image)) { goTo(i); return; }
    }
  }
  function onOptions() {
    var chosen = [];
    groups.forEach(function (g) {
      var on = g.querySelector('input:checked');
      chosen[parseInt(g.getAttribute('data-option-index'), 10)] = on ? on.value : null;
    });
    var match = null;
    variants.forEach(function (v) { if (!match && v.options.join('|') === chosen.join('|')) { match = v; } });
    if (!match) { return; }
    if (select) { select.value = String(match.id); }
    showPrice(match);
    showButton(match);
    showImage(match);
    try {
      var url = new URL(window.location.href);
      url.searchParams.set('variant', match.id);
      window.history.replaceState({}, '', url.toString());
    } catch (e) {}
  }
  form.addEventListener('change', function (e) {
    if (e.target.type === 'radio' && /^option-/.test(e.target.name)) { onOptions(); }
  });

  function showError(text) {
    if (msg) { msg.hidden = true; }
    if (err) { err.textContent = text; err.hidden = false; }
  }
  function reset() {
    if (!addBtn || !canBuy) { return; }
    var v = null;
    variants.forEach(function (x) { if (select && String(x.id) === select.value) { v = x; } });
    if (v) { showButton(v); } else { addBtn.disabled = false; addBtn.textContent = addLabel; }
  }
  /* Back/forward cache restores the page with the button still disabled */
  window.addEventListener('pageshow', function (e) { if (e.persisted) { reset(); } });

  /* Mobile sticky Add to cart: shown only after the real button has scrolled off the top of the screen,
     so it can never sit on top of the title, price or options. It presses the real button and mirrors its state. */
  var sticky = document.querySelector('[data-sticky-atc]');
  var stickyBtn = sticky ? sticky.querySelector('[data-sticky-add]') : null;
  var addRow = form.querySelector('.add-row');
  if (sticky && stickyBtn && addBtn && addRow && 'IntersectionObserver' in window) {
    var mirror = function () { stickyBtn.disabled = addBtn.disabled; stickyBtn.textContent = addBtn.textContent; };
    new MutationObserver(mirror).observe(addBtn, { attributes: true, childList: true, characterData: true, subtree: true });
    mirror();
    stickyBtn.addEventListener('click', function () {
      if (addBtn.disabled) { return; }
      addBtn.click();
    });
    new IntersectionObserver(function (entries) {
      var r = entries[0];
      var show = !r.isIntersecting && r.boundingClientRect.bottom < 0;
      sticky.hidden = !show;
      document.body.classList.toggle('has-sticky-atc', show);
    }).observe(addRow);
  }

  var addUrl = form.dataset.cartAdd;
  var cartUrl = form.dataset.cartUrl;
  if (!canBuy || !addUrl || !cartUrl || !window.fetch || !window.FormData) { return; }

  form.addEventListener('submit', function (e) {
    /* Let Shopify's accelerated checkout buttons do their own thing */
    if (e.submitter && e.submitter.name === 'checkout') { return; }
    e.preventDefault();
    if (err) { err.hidden = true; }
    if (msg) { msg.hidden = true; }
    addBtn.disabled = true;
    addBtn.textContent = strings.adding || 'Adding...';
    fetch(addUrl + '.js', { method: 'POST', body: new FormData(form), headers: { 'Accept': 'application/json' } })
      .then(function (r) {
        return r.json().then(function (data) {
          if (!r.ok) { throw new Error(data.description || data.message || strings.error); }
          return data;
        });
      })
      .then(function () { return fetch(cartUrl + '.js', { headers: { 'Accept': 'application/json' } }).then(function (r) { return r.json(); }); })
      .then(function (cart) {
        setCartCount(cart.item_count);
        addBtn.textContent = strings.added || 'Added';
        if (msg) { msg.hidden = false; }
        setTimeout(reset, 1800);
      })
      .catch(function (error) {
        showError((error && error.message) || strings.error || 'Something went wrong.');
        reset();
      });
  });
})();
