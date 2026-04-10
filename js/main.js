// Main interactive features for Crisis-Proof Business Summit v2

document.addEventListener('DOMContentLoaded', () => {
  initCountdown();
  initFAQ();
  initSmoothScroll();
  initNavbar();
  initScrollAnimations();
  initCheckout();
  initBgVideo();
});

// --- 1. Countdown Timer ---

function initCountdown() {
  const targetDate = new Date('2026-05-10T09:00:00+08:00');

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
      document.body.style.overflow = '';
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
        document.body.style.overflow = '';
      } else {
        navLinks.classList.add('mobile-open');
        navToggle.classList.add('open');
        navToggle.setAttribute('aria-expanded', 'true');
        document.body.style.overflow = 'hidden';
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

  // Checkout form submit → open modal with iframe (fallback: redirect)
  const checkoutLinks = {
    early_bird: 'https://scaleyourorg.net/checkout/PROD-1775779034209',
    regular: 'https://scaleyourorg.net/checkout/PROD-1775779096693',
    vip: 'https://scaleyourorg.net/checkout/PROD-1775779147241'
  };

  function openCheckoutModal(url) {
    const modal = document.getElementById('checkout-modal');
    const iframe = document.getElementById('checkout-iframe');
    if (!modal || !iframe) { window.location.href = url; return; }

    iframe.src = '';
    modal.hidden = false;
    document.body.style.overflow = 'hidden';

    // If iframe fails to load (X-Frame-Options block), fall back to redirect
    iframe.onerror = function () { window.location.href = url; };
    iframe.src = url;

    // Also detect blank iframe after timeout (onerror doesn't always fire)
    setTimeout(() => {
      try {
        // Accessing cross-origin iframe throws — that's fine, means it loaded
        iframe.contentWindow.document;
        // If we can access it and it's blank, the site blocked framing
        if (!iframe.contentWindow.document.body.innerHTML) {
          closeCheckoutModal();
          window.location.href = url;
        }
      } catch (e) {
        // Cross-origin = iframe loaded the external page — all good
      }
    }, 3000);
  }

  function closeCheckoutModal() {
    const modal = document.getElementById('checkout-modal');
    const iframe = document.getElementById('checkout-iframe');
    if (modal) modal.hidden = true;
    if (iframe) iframe.src = '';
    document.body.style.overflow = '';
  }

  // Close modal on backdrop click or close button
  var modalBackdrop = document.querySelector('.checkout-modal-backdrop');
  var modalClose = document.querySelector('.checkout-modal-close');
  if (modalBackdrop) modalBackdrop.addEventListener('click', closeCheckoutModal);
  if (modalClose) modalClose.addEventListener('click', closeCheckoutModal);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeCheckoutModal();
  });

  // Pricing card buttons → open checkout modal
  document.querySelectorAll('.ticket-btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var tier = btn.dataset.tier || 'early_bird';
      var payURL = checkoutLinks[tier] || checkoutLinks.early_bird;
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
