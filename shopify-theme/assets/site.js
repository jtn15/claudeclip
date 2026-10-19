/* Maison Rivault theme: the only script is the mobile menu. Cart, signup and checkout are Shopify's own. */
(function () {
  var btn = document.querySelector('.menu-btn');
  var nav = document.getElementById('site-nav');
  if (!btn || !nav) { return; }
  btn.addEventListener('click', function () {
    var open = nav.classList.toggle('open');
    btn.setAttribute('aria-expanded', open);
  });
})();
