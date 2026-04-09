// Main interactive features for Crisis-Proof Business Summit v2

document.addEventListener('DOMContentLoaded', () => {
  initCountdown();
  initFAQ();
  initSmoothScroll();
  initNavbar();
  initScrollAnimations();
  initCheckout();
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
    early_bird: ['Full-day access (9AM-6PM)', 'Event kit & materials', 'Crisis-Proof Blueprint', 'Networking opportunities'],
    regular: ['Full-day access (9AM-6PM)', 'Event kit & materials', 'Crisis-Proof Blueprint', 'Networking opportunities'],
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

  // Checkout form submit → redirect to Paymongo
  const form = document.getElementById('checkout-form');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();

      const submitBtn = document.getElementById('checkout-submit');
      if (submitBtn.disabled) return;
      submitBtn.disabled = true;

      const selectedTier = form.querySelector('input[name="ticket_tier"]:checked');
      const tier = selectedTier ? selectedTier.value : 'early_bird';
      const price = selectedTier ? Number(selectedTier.dataset.price) : 1999;
      const totalAmount = price * currentQty;

      // Placeholder redirect — replace with real Paymongo link
      const payURL = `https://example.com/pay?tier=${encodeURIComponent(tier)}&qty=${currentQty}&amount=${totalAmount}`;

      setTimeout(() => {
        window.location.href = payURL;
      }, 500);
    });
  }
}
