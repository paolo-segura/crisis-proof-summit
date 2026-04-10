// Main interactive features for Crisis-Proof Business Summit v2

document.addEventListener('DOMContentLoaded', () => {
  initCountdown();
  initEarlyBird();
  initFAQ();
  initSmoothScroll();
  initNavbar();
  initScrollAnimations();
  initCheckout();
  initBgVideo();
});

// --- 1. Countdown Timer ---

function initCountdown() {
  const targetDate = new Date('2026-05-09T09:00:00+08:00');

  const timers = [
    document.getElementById('countdown'),
    document.getElementById('countdown-bottom'),
  ].filter(Boolean);

  if (timers.length === 0) return;

  function pad(n) { return String(n).padStart(2, '0'); }

  function updateTimers() {
    const now = new Date();
    const diff = targetDate - now;

    if (diff <= 0) {
      timers.forEach((timer) => {
        timer.innerHTML = '<span class="countdown-message">EVENT DAY IS HERE!</span>';
      });
      return;
    }

    const totalSeconds = Math.floor(diff / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    timers.forEach((timer) => {
      const d = timer.querySelector('[data-unit="days"]');
      const h = timer.querySelector('[data-unit="hours"]');
      const m = timer.querySelector('[data-unit="minutes"]');
      const s = timer.querySelector('[data-unit="seconds"]');
      if (d) d.textContent = pad(days);
      if (h) h.textContent = pad(hours);
      if (m) m.textContent = pad(minutes);
      if (s) s.textContent = pad(seconds);
    });
  }

  updateTimers();
  setInterval(updateTimers, 1000);
}

// --- 1b. Early Bird → Regular auto-switch ---

function initEarlyBird() {
  // Early bird ends May 2, 2026 at 00:00 PHT (UTC+8)
  var earlyBirdEnd = new Date('2026-05-02T00:00:00+08:00');

  var card = document.getElementById('general-ticket-card');
  var badge = document.getElementById('general-badge');
  var strike = document.getElementById('general-price-strike');
  var priceAmount = document.getElementById('general-price-amount');
  var btn = document.getElementById('general-ticket-btn');
  var countdownEl = document.getElementById('early-bird-countdown');

  if (!card) return;

  function pad(n) { return String(n).padStart(2, '0'); }

  function applyRegularRate() {
    if (badge) badge.textContent = 'REGULAR RATE';
    if (strike) strike.style.display = 'none';
    if (priceAmount) priceAmount.textContent = '2,500';
    if (btn) btn.setAttribute('data-tier', 'regular');
    if (countdownEl) countdownEl.style.display = 'none';
  }

  function updateEarlyBirdCountdown() {
    var now = new Date();
    var diff = earlyBirdEnd - now;

    if (diff <= 0) {
      applyRegularRate();
      return true; // done
    }

    var totalSeconds = Math.floor(diff / 1000);
    var days = Math.floor(totalSeconds / 86400);
    var hours = Math.floor((totalSeconds % 86400) / 3600);
    var minutes = Math.floor((totalSeconds % 3600) / 60);
    var seconds = totalSeconds % 60;

    if (countdownEl) {
      var d = countdownEl.querySelector('[data-eb-unit="days"]');
      var h = countdownEl.querySelector('[data-eb-unit="hours"]');
      var m = countdownEl.querySelector('[data-eb-unit="minutes"]');
      var s = countdownEl.querySelector('[data-eb-unit="seconds"]');
      if (d) d.textContent = pad(days);
      if (h) h.textContent = pad(hours);
      if (m) m.textContent = pad(minutes);
      if (s) s.textContent = pad(seconds);
    }
    return false;
  }

  var done = updateEarlyBirdCountdown();
  if (!done) {
    var interval = setInterval(function () {
      if (updateEarlyBirdCountdown()) clearInterval(interval);
    }, 1000);
  }
}

// --- 2. FAQ Accordion ---

function initFAQ() {
  const faqItems = document.querySelectorAll('.faq-item');

  faqItems.forEach((item) => {
    const question = item.querySelector('.faq-question');
    const answer = item.querySelector('.faq-answer');
    if (!question || !answer) return;

    question.addEventListener('click', () => {
      const isActive = item.classList.contains('active');

      faqItems.forEach((other) => {
        other.classList.remove('active');
        const otherQ = other.querySelector('.faq-question');
        const otherA = other.querySelector('.faq-answer');
        if (otherQ) otherQ.setAttribute('aria-expanded', 'false');
        if (otherA) otherA.hidden = true;
      });

      if (!isActive) {
        item.classList.add('active');
        question.setAttribute('aria-expanded', 'true');
        answer.hidden = false;
      }
    });
  });
}

// --- 3. Smooth Scroll ---

function initSmoothScroll() {
  const NAVBAR_OFFSET = 70;

  document.addEventListener('click', (e) => {
    const link = e.target.closest('a[href^="#"]');
    if (!link) return;

    const href = link.getAttribute('href');
    if (!href || href === '#') return;

    const target = document.querySelector(href);
    if (!target) return;

    e.preventDefault();

    // Close mobile nav if open
    const navLinks = document.getElementById('nav-links');
    const navToggle = document.getElementById('nav-toggle');
    if (navLinks && navLinks.classList.contains('mobile-open')) {
      navLinks.classList.remove('mobile-open');
      navToggle.classList.remove('open');
      navToggle.setAttribute('aria-expanded', 'false');
      var scrollY = document.body.style.top;
      document.body.classList.remove('nav-open');
      document.body.style.top = '';
      window.scrollTo(0, parseInt(scrollY || '0') * -1);
    }

    const targetTop = target.getBoundingClientRect().top + window.scrollY - NAVBAR_OFFSET;
    window.scrollTo({ top: targetTop, behavior: 'smooth' });
  });
}

// --- 4. Navbar: scroll effect, toggle, active link ---

function initNavbar() {
  const nav = document.querySelector('.nav-bar');
  const navToggle = document.getElementById('nav-toggle');
  const navLinks = document.getElementById('nav-links');
  const allLinks = document.querySelectorAll('.nav-link:not(.nav-cta)');
  const sections = [];

  // Build section list for active tracking
  allLinks.forEach((link) => {
    const href = link.getAttribute('href');
    if (href && href.startsWith('#')) {
      const section = document.querySelector(href);
      if (section) sections.push({ link, section });
    }
  });

  // Scroll effect
  function handleScroll() {
    if (window.scrollY > 60) {
      nav.classList.add('scrolled');
    } else {
      nav.classList.remove('scrolled');
    }

    // Active link tracking
    const scrollPos = window.scrollY + 120;
    let activeFound = false;
    for (let i = sections.length - 1; i >= 0; i--) {
      if (sections[i].section.offsetTop <= scrollPos) {
        allLinks.forEach((l) => l.classList.remove('active'));
        sections[i].link.classList.add('active');
        activeFound = true;
        break;
      }
    }
    if (!activeFound) allLinks.forEach((l) => l.classList.remove('active'));
  }

  window.addEventListener('scroll', handleScroll, { passive: true });
  handleScroll();

  // Mobile toggle
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      const isOpen = navLinks.classList.contains('mobile-open');
      if (isOpen) {
        navLinks.classList.remove('mobile-open');
        navToggle.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
        var scrollY = document.body.style.top;
        document.body.classList.remove('nav-open');
        document.body.style.top = '';
        window.scrollTo(0, parseInt(scrollY || '0') * -1);
      } else {
        navLinks.classList.add('mobile-open');
        navToggle.classList.add('open');
        navToggle.setAttribute('aria-expanded', 'true');
        document.body.style.top = '-' + window.scrollY + 'px';
        document.body.classList.add('nav-open');
      }
    });
  }
}

// --- 5. Scroll Animations ---

function initScrollAnimations() {
  const animatedEls = document.querySelectorAll('.animate-in');
  if (animatedEls.length === 0) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1 }
  );

  animatedEls.forEach((el) => observer.observe(el));
}

// --- 6. Checkout: tier selection sync, form handling ---

function initCheckout() {
  const tierRadios = document.querySelectorAll('input[name="ticket_tier"]');
  const checkoutTierName = document.getElementById('checkout-tier-name');
  const checkoutTotal = document.getElementById('checkout-total');
  const btnPrice = document.getElementById('btn-price');
  const qtyDisplay = document.getElementById('checkout-qty');
  const qtyMinusBtn = document.getElementById('qty-minus');
  const qtyPlusBtn = document.getElementById('qty-plus');
  const qtyHiddenInput = document.getElementById('ticket-qty-input');

  let currentQty = 1;
  const MAX_QTY = 10;

  const tierNames = {
    early_bird: 'Early Bird',
    regular: 'Regular',
    vip: 'VIP Access',
  };

  const tierIncludes = {
    early_bird: ['Full-day access (9AM-6PM)', 'Event kit & materials', 'The New Normal Blueprint', 'Networking opportunities'],
    regular: ['Full-day access (9AM-6PM)', 'Event kit & materials', 'The New Normal Blueprint', 'Networking opportunities'],
    vip: ['Everything in Regular +', 'VIP Registration Lane', '6-Month ExU Access', 'Exclusive Mastermind Session'],
  };

  function formatPeso(amount) {
    return '\u20B1' + Number(amount).toLocaleString();
  }

  function getSelectedPrice() {
    const selected = document.querySelector('input[name="ticket_tier"]:checked');
    return selected ? Number(selected.dataset.price) : 1999;
  }

  function updateCheckoutDisplay(tier, price) {
    if (checkoutTierName) checkoutTierName.textContent = tierNames[tier] || tier;
    const total = Number(price) * currentQty;
    if (checkoutTotal) checkoutTotal.textContent = formatPeso(total);
    if (btnPrice) btnPrice.textContent = formatPeso(total);
    if (qtyDisplay) qtyDisplay.textContent = currentQty;
    if (qtyHiddenInput) qtyHiddenInput.value = currentQty;

    // Update includes
    const includes = tierIncludes[tier] || tierIncludes.early_bird;
    for (let i = 0; i < 4; i++) {
      const el = document.getElementById('checkout-include-' + (i + 1));
      if (el) el.textContent = includes[i] || '';
    }
  }

  function getSelectedTier() {
    const selected = document.querySelector('input[name="ticket_tier"]:checked');
    return selected ? selected.value : 'early_bird';
  }

  // Quantity stepper
  if (qtyMinusBtn) {
    qtyMinusBtn.addEventListener('click', () => {
      if (currentQty > 1) {
        currentQty--;
        updateCheckoutDisplay(getSelectedTier(), getSelectedPrice());
      }
    });
  }
  if (qtyPlusBtn) {
    qtyPlusBtn.addEventListener('click', () => {
      if (currentQty < MAX_QTY) {
        currentQty++;
        updateCheckoutDisplay(getSelectedTier(), getSelectedPrice());
      }
    });
  }

  // Tier radio change
  tierRadios.forEach((radio) => {
    radio.addEventListener('change', () => {
      if (radio.checked) {
        updateCheckoutDisplay(radio.value, radio.dataset.price);
      }
    });
  });

  // Pricing card buttons → select tier + scroll to checkout
  const ticketBtns = document.querySelectorAll('.ticket-btn');
  ticketBtns.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      // Don't prevent default — let smooth scroll handle it
      const tier = btn.dataset.tier;
      const price = btn.dataset.price;

      // Select matching radio
      const radio = document.querySelector(`input[name="ticket_tier"][value="${tier}"]`);
      if (radio) {
        radio.checked = true;
        updateCheckoutDisplay(tier, price);
      }

      // Log to Supabase if available
      if (typeof supabase !== 'undefined' && supabase) {
        const utm = typeof getUTMParams === 'function' ? getUTMParams() : {};
        const sessionId = typeof getSessionId === 'function' ? getSessionId() : null;

        supabase.from('clicks').insert({
          utm_source: utm.utm_source || null,
          utm_medium: utm.utm_medium || null,
          utm_campaign: utm.utm_campaign || null,
          ticket_tier: tier,
          session_id: sessionId,
        }).then(({ error }) => {
          if (error) console.warn('Click log failed:', error.message);
        });
      }
    });
  });

  // Checkout links → log click + open in iframe modal
  const checkoutLinks = {
    early_bird: 'https://scaleyourorg.net/checkout/PROD-1775779034209',
    regular: 'https://scaleyourorg.net/checkout/PROD-1775779096693',
    vip: 'https://scaleyourorg.net/checkout/PROD-1775779147241'
  };

  function buildCheckoutURL(baseURL, tier) {
    var tracking = window.NBN_TRACKING || {};
    var sessionId = tracking.getSessionId ? tracking.getSessionId() : '';
    var utm = tracking.getUTMParams ? tracking.getUTMParams() : {};
    var url = new URL(baseURL);
    url.searchParams.set('session_id', sessionId);
    url.searchParams.set('tier', tier);
    if (utm.utm_source) url.searchParams.set('utm_source', utm.utm_source);
    if (utm.utm_medium) url.searchParams.set('utm_medium', utm.utm_medium);
    if (utm.utm_campaign) url.searchParams.set('utm_campaign', utm.utm_campaign);
    if (utm.utm_content) url.searchParams.set('utm_content', utm.utm_content);
    if (utm.utm_term) url.searchParams.set('utm_term', utm.utm_term);
    return url.toString();
  }

  function logClick(tier) {
    if (typeof supabase === 'undefined' || !supabase) return;
    var tracking = window.NBN_TRACKING || {};
    var sessionId = tracking.getSessionId ? tracking.getSessionId() : null;
    var utm = tracking.getUTMParams ? tracking.getUTMParams() : {};
    supabase
      .from(TABLE_CLICKS)
      .insert({
        session_id: sessionId,
        ticket_tier: tier,
        utm_source: utm.utm_source,
        utm_medium: utm.utm_medium,
        utm_campaign: utm.utm_campaign,
        utm_content: utm.utm_content,
        utm_term: utm.utm_term,
      })
      .then(function (res) {
        if (res && res.error) console.warn('Click log failed:', res.error.message);
      });
  }

  function openCheckoutModal(url) {
    var modal = document.getElementById('checkout-modal');
    var iframe = document.getElementById('checkout-iframe');
    if (!modal || !iframe) { window.open(url, '_blank', 'noopener,noreferrer'); return; }
    iframe.src = url;
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeCheckoutModal() {
    var modal = document.getElementById('checkout-modal');
    var iframe = document.getElementById('checkout-iframe');
    if (modal) modal.hidden = true;
    if (iframe) iframe.src = '';
    document.body.style.overflow = '';
  }

  var modalBackdrop = document.querySelector('.checkout-modal-backdrop');
  var modalClose = document.querySelector('.checkout-modal-close');
  var doneBtn = document.getElementById('checkout-done-btn');
  if (modalBackdrop) modalBackdrop.addEventListener('click', closeCheckoutModal);
  if (modalClose) modalClose.addEventListener('click', closeCheckoutModal);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeCheckoutModal();
  });

  // Done-paying handoff: close the modal and send them to /thank-you
  // with the session + UTM in the URL so thank-you.html can log the
  // purchase and Brevo can pick it up later.
  if (doneBtn) {
    doneBtn.addEventListener('click', function () {
      var tracking = window.NBN_TRACKING || {};
      var sessionId = tracking.getSessionId ? tracking.getSessionId() : '';
      var utm = tracking.getUTMParams ? tracking.getUTMParams() : {};
      var params = new URLSearchParams();
      if (sessionId) params.set('session_id', sessionId);
      if (utm.utm_source) params.set('utm_source', utm.utm_source);
      if (utm.utm_medium) params.set('utm_medium', utm.utm_medium);
      if (utm.utm_campaign) params.set('utm_campaign', utm.utm_campaign);
      if (utm.utm_content) params.set('utm_content', utm.utm_content);
      if (utm.utm_term) params.set('utm_term', utm.utm_term);
      params.set('handoff', 'user');
      closeCheckoutModal();
      window.location.href = '/thank-you?' + params.toString();
    });
  }

  document.querySelectorAll('.ticket-btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var tier = btn.dataset.tier || 'early_bird';
      var baseURL = checkoutLinks[tier] || checkoutLinks.early_bird;
      var payURL = buildCheckoutURL(baseURL, tier);
      logClick(tier);
      openCheckoutModal(payURL);
    });
  });
}

// --- 7. Safari/mobile autoplay fix for background video ---

function initBgVideo() {
  const vid = document.querySelector('.bg-video-fixed');
  if (!vid) return;

  function tryPlay() {
    var p = vid.play();
    if (p && typeof p.catch === 'function') {
      p.catch(function () {
        // Autoplay blocked — try again on first user interaction
        var events = ['touchstart', 'click', 'scroll'];
        function playOnInteraction() {
          vid.play();
          events.forEach(function (e) {
            document.removeEventListener(e, playOnInteraction);
          });
        }
        events.forEach(function (e) {
          document.addEventListener(e, playOnInteraction, { once: true, passive: true });
        });
      });
    }
  }

  // Try immediately, and again after load in case Safari deferred it
  tryPlay();
  window.addEventListener('load', tryPlay);
}
