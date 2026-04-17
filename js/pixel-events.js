// Meta Pixel — Standard + Custom events shared across pages.
// Base pixel (PageView) is installed inline in each page's <head>.
// This file adds: ViewContent (pricing), ScrollDepth (custom), Contact (mailto/tel).

(function () {
  if (typeof fbq !== 'function') return;

  // --- 1. ViewContent: fire when pricing section becomes visible ---
  var pricingEl = document.getElementById('pricing');
  if (pricingEl && 'IntersectionObserver' in window) {
    var viewContentFired = false;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && !viewContentFired) {
          viewContentFired = true;
          fbq('track', 'ViewContent', {
            content_name: 'Pricing Section',
            content_category: 'event-ticket',
            content_type: 'product_group',
          });
          io.disconnect();
        }
      });
    }, { threshold: 0.4 });
    io.observe(pricingEl);
  }

  // --- 2. Scroll depth: custom events at 50%, 75%, 90% ---
  var scrollFired = {};
  var thresholds = [50, 75, 90];

  function onScroll() {
    var doc = document.documentElement;
    var scrollTop = window.pageYOffset || doc.scrollTop;
    var viewport = window.innerHeight || doc.clientHeight;
    var height = Math.max(doc.scrollHeight, doc.offsetHeight) - viewport;
    if (height <= 0) return;
    var pct = Math.round((scrollTop / height) * 100);

    thresholds.forEach(function (t) {
      if (pct >= t && !scrollFired[t]) {
        scrollFired[t] = true;
        fbq('trackCustom', 'ScrollDepth', {
          depth: t,
          page: window.location.pathname,
        });
      }
    });

    if (thresholds.every(function (t) { return scrollFired[t]; })) {
      window.removeEventListener('scroll', throttled);
    }
  }

  var ticking = false;
  function throttled() {
    if (!ticking) {
      window.requestAnimationFrame(function () {
        onScroll();
        ticking = false;
      });
      ticking = true;
    }
  }
  window.addEventListener('scroll', throttled, { passive: true });

  // --- 3. Contact: fire on mailto:/tel: clicks ---
  document.addEventListener('click', function (e) {
    var link = e.target.closest('a[href^="mailto:"], a[href^="tel:"]');
    if (!link) return;
    var method = link.getAttribute('href').indexOf('tel:') === 0 ? 'phone' : 'email';
    fbq('track', 'Contact', {
      content_name: link.textContent.trim().slice(0, 60) || method,
      content_category: method,
    });
  });

  // --- 4. TimeOnPage: custom event at 60s engaged time ---
  var engaged = false;
  setTimeout(function () {
    if (engaged) return;
    engaged = true;
    fbq('trackCustom', 'EngagedUser', {
      seconds: 60,
      page: window.location.pathname,
    });
  }, 60000);
})();
