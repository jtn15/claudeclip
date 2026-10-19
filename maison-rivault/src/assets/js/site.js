/* Maison Rivault runtime. No dependencies.
   Reads window.MR (config, products, bundles) written by build.py. */
(function () {
  "use strict";
  var MR = window.MR || { config: {}, products: [], bundles: [] };
  var cfg = MR.config;
  var byId = {};
  MR.products.forEach(function (p) { byId[p.id] = p; });
  MR.bundles.forEach(function (b) { byId[b.id] = b; });

  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function money(n) { return n === null ? "Price at launch" : "$" + (n % 1 ? n.toFixed(2) : n); }
  function store(key, val) {
    try { if (val === undefined) { return JSON.parse(localStorage.getItem(key)); } localStorage.setItem(key, JSON.stringify(val)); } catch (e) { return null; }
  }

  /* Mobile menu */
  var menuBtn = $(".menu-btn"), nav = $("#site-nav");
  if (menuBtn && nav) {
    menuBtn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", open);
    });
  }

  /* Shop filters: tier and type combine */
  var filters = { tier: "all", type: "all" };
  $$(".filters button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var group = btn.getAttribute("data-group");
      filters[group] = btn.getAttribute("data-value");
      $$('.filters button[data-group="' + group + '"]').forEach(function (b) { b.setAttribute("aria-pressed", b === btn); });
      $$(".grid .card").forEach(function (c) {
        c.hidden = (filters.tier !== "all" && c.getAttribute("data-tier") !== filters.tier) ||
                   (filters.type !== "all" && c.getAttribute("data-type") !== filters.type);
      });
    });
  });

  /* Cart (local; checkout hands off to Shopify) */
  function getCart() { return store("mr_cart") || []; }
  function setCart(c) { store("mr_cart", c); renderCount(); }
  function renderCount() {
    var n = getCart().reduce(function (s, l) { return s + l.qty; }, 0);
    $$(".cart-count").forEach(function (el) { el.textContent = n; });
  }
  function lineKey(l) { return l.id + "|" + JSON.stringify(l.sizes || l.size || ""); }
  function addLine(line) {
    var cart = getCart();
    var existing = cart.filter(function (l) { return lineKey(l) === lineKey(line); })[0];
    if (existing) { existing.qty += 1; } else { line.qty = 1; cart.push(line); }
    setCart(cart);
  }
  renderCount();

  /* Product page */
  var addBtn = $("[data-add-product]");
  if (addBtn) {
    var sel = $("#size");
    addBtn.addEventListener("click", function () {
      if (sel && !sel.value) { $("#size-msg").textContent = "Choose a size."; sel.focus(); return; }
      addLine({ id: addBtn.getAttribute("data-add-product"), kind: "product", size: sel ? sel.value : "One size" });
      addBtn.textContent = "Added. View cart";
      addBtn.onclick = function () { location.href = addBtn.getAttribute("data-cart-url"); };
    });
  }

  /* Bundle add */
  $$("[data-add-bundle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var wrap = btn.closest(".bundle"), sizes = {}, ok = true;
      $$("select[data-item]", wrap).forEach(function (s) { if (!s.value) { ok = false; s.focus(); } sizes[s.getAttribute("data-item")] = s.value; });
      var msg = $(".bundle-msg", wrap);
      if (!ok) { msg.textContent = "Choose a size for each piece."; return; }
      addLine({ id: btn.getAttribute("data-add-bundle"), kind: "bundle", sizes: sizes });
      msg.textContent = "Added to your cart.";
    });
  });

  /* Cart page */
  var cartRoot = $("#cart-root");
  if (cartRoot) { renderCart(); }

  function lineInfo(l) {
    var item = byId[l.id];
    if (!item) { return null; }
    var desc = l.kind === "bundle"
      ? item.items.map(function (i) { var s = l.sizes[i]; return byId[i].name + (s && s !== "One size" ? " (" + s + ")" : ""); }).join(", ")
      : item.color_name + (l.size && l.size !== "One size" ? ", size " + l.size : "");
    return { item: item, desc: desc, total: item.price * l.qty };
  }

  function checkoutUrl(cart) {
    var domain = cfg.commerce.shopify_domain;
    if (!domain) { return { error: "Checkout opens when the store does, " + cfg.launch.label + "." }; }
    var parts = [];
    for (var i = 0; i < cart.length; i++) {
      var l = cart[i], item = byId[l.id], key, vid;
      key = l.kind === "bundle" ? Object.keys(l.sizes).map(function (k) { return l.sizes[k]; }).join("|") : l.size;
      vid = item.shopify_variant_ids && item.shopify_variant_ids[key];
      if (!vid) { return { error: "Checkout is not connected for " + item.name + " in this size yet." }; }
      parts.push(vid + ":" + l.qty);
    }
    return { url: "https://" + domain + "/cart/" + parts.join(",") };
  }

  function renderCart() {
    var cart = getCart().filter(function (l) { return byId[l.id]; });
    if (!cart.length) {
      cartRoot.innerHTML = '<p>Your cart is empty.</p><p><a class="btn" href="shop.html">Shop Drop 001</a></p>';
      return;
    }
    var html = "", total = 0;
    cart.forEach(function (l, idx) {
      var info = lineInfo(l); total += info.total;
      html += '<div class="cart-line"><div class="ph" style="aspect-ratio:4/5" role="img" aria-label="Photo placeholder"><span>Photo</span></div>' +
        '<div><div class="card-name">' + info.item.name + '</div><div class="card-sub">' + info.desc + '</div>' +
        '<div class="qty"><button type="button" data-q="-1" data-i="' + idx + '" aria-label="Decrease quantity">&minus;</button><span>' + l.qty + '</span><button type="button" data-q="1" data-i="' + idx + '" aria-label="Increase quantity">+</button></div>' +
        '<button type="button" class="linkbtn" data-rm="' + idx + '">Remove</button></div>' +
        '<div class="price">' + money(info.total) + '</div></div>';
    });
    var out = checkoutUrl(cart);
    html += '<div class="cart-total"><span>Subtotal</span><span class="price">' + money(total) + '</span></div>' +
      '<p class="small">Shipping and any taxes are calculated at checkout.</p>' +
      (out.url ? '<a class="btn btn-block" href="' + out.url + '">Checkout</a>'
               : '<button class="btn btn-block" disabled>Checkout</button><p class="form-msg small">' + out.error + '</p>');
    cartRoot.innerHTML = html;
    $$("[data-q]", cartRoot).forEach(function (b) { b.addEventListener("click", function () {
      var c = getCart(), l = c[+b.getAttribute("data-i")]; l.qty += +b.getAttribute("data-q");
      setCart(c.filter(function (x) { return x.qty > 0; })); renderCart();
    }); });
    $$("[data-rm]", cartRoot).forEach(function (b) { b.addEventListener("click", function () {
      var c = getCart(); c.splice(+b.getAttribute("data-rm"), 1); setCart(c); renderCart();
    }); });
  }

  /* Email signup: Klaviyo client API, or a generic JSON endpoint. Never reports success unless the request succeeded. */
  $$(".js-signup").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var msg = $(".form-msg", form.parentNode), email = form.elements.email.value.trim(), em = cfg.email || {};
      msg.textContent = "";
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { msg.textContent = "Enter a valid email address."; return; }
      var req;
      if (em.provider === "klaviyo" && em.klaviyo_public_key && em.klaviyo_list_id) {
        req = fetch("https://a.klaviyo.com/client/subscriptions/?company_id=" + encodeURIComponent(em.klaviyo_public_key), {
          method: "POST",
          headers: { "Content-Type": "application/json", "revision": "2024-10-15" },
          body: JSON.stringify({ data: { type: "subscription",
            attributes: { profile: { data: { type: "profile", attributes: { email: email } } } },
            relationships: { list: { data: { type: "list", id: em.klaviyo_list_id } } } } })
        });
      } else if (em.generic_endpoint) {
        req = fetch(em.generic_endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: email, source: form.getAttribute("data-source") || "site" }) });
      } else {
        msg.textContent = "Signup is not connected yet. Please check back soon.";
        if (window.console) { console.warn("Maison Rivault: email provider not configured (site.config.json > email)."); }
        return;
      }
      msg.textContent = "Sending...";
      req.then(function (r) {
        if (!r.ok) { throw new Error("status " + r.status); }
        form.reset(); msg.textContent = "Thank you. We will email you when doors open, " + cfg.launch.label + ".";
      }).catch(function () { msg.textContent = "Something went wrong. Please try again."; });
    });
  });

  /* Cookie consent. Non-essential tracking stays off unless the visitor accepts. */
  function loadAnalytics() {
    var a = cfg.analytics || {};
    if (a.ga4_id) {
      var s = document.createElement("script"); s.async = true; s.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(a.ga4_id); document.head.appendChild(s);
      window.dataLayer = window.dataLayer || []; window.gtag = function () { window.dataLayer.push(arguments); };
      window.gtag("js", new Date()); window.gtag("config", a.ga4_id);
    }
    if (a.meta_pixel_id) {
      /* Standard Meta Pixel loader */
      !function (f, b, e, v, n, t, s) { if (f.fbq) return; n = f.fbq = function () { n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments); }; if (!f._fbq) f._fbq = n; n.push = n; n.loaded = !0; n.version = "2.0"; n.queue = []; t = b.createElement(e); t.async = !0; t.src = v; s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s); }(window, document, "script", "https://connect.facebook.net/en_US/fbevents.js");
      window.fbq("init", a.meta_pixel_id); window.fbq("track", "PageView");
    }
  }
  function consentBanner() {
    var box = document.createElement("div");
    box.className = "consent"; box.setAttribute("role", "dialog"); box.setAttribute("aria-label", "Cookie preferences");
    box.innerHTML = '<div class="consent-inner"><p>We use essential storage to run the site. With your permission we also use analytics to see which pages are useful. <a href="privacy.html">Privacy policy</a></p>' +
      '<div class="actions"><button type="button" class="btn btn-quiet" data-c="declined">Decline</button><button type="button" class="btn btn-quiet" data-c="accepted">Accept</button></div></div>';
    document.body.appendChild(box);
    $$("button", box).forEach(function (b) { b.addEventListener("click", function () {
      var v = b.getAttribute("data-c"); store("mr_consent", v); box.remove(); if (v === "accepted") { loadAnalytics(); }
    }); });
    $("button", box).focus();
  }
  var consent = store("mr_consent");
  if (consent === "accepted") { loadAnalytics(); } else if (consent !== "declined") { consentBanner(); }
  $$("[data-cookie-settings]").forEach(function (a) { a.addEventListener("click", function (e) { e.preventDefault(); store("mr_consent", null); try { localStorage.removeItem("mr_consent"); } catch (x) {} if (!$(".consent")) { consentBanner(); } }); });
})();
