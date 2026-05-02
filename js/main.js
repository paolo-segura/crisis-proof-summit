// Main interactive features for Crisis-Proof Business Summit v2

document.addEventListener('DOMContentLoaded', () => {
  initCountdown();
  initEarlyBird();
  initFAQ();
  initSmoothScroll();
  initNavbar();
  initScrollAnimations();
  initBgVideo();
});

// --- 1. Countdown Timer ---
// Hero countdown targets Early Bird deadline (May 2), then auto-switches
// to the event countdown (May 9) once early bird ends. Bottom countdown
// always targets the event date.

function initCountdown() {
  const eventDate = new Date('2026-05-09T09:00:00+08:00');
  const earlyBirdEnd = new Date('2026-05-02T00:00:00+08:00');

  const heroTimer = document.getElementById('countdown');
  const bottomTimer = document.getElementById('countdown-bottom');
  const heroLabel = document.getElementById('hero-countdown-label');

  if (!heroTimer && !bottomTimer) return;

  function pad(n) { return String(n).padStart(2, '0'); }

  function renderTimer(timer, target, endedMsg) {
    if (!timer) return;
    const diff = target - new Date();

    if (diff <= 0) {
      timer.innerHTML = '<span class="countdown-message">' + endedMsg + '</span>';
      return;
    }

    const totalSeconds = Math.floor(diff / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    const d = timer.querySelector('[data-unit="days"]');
    const h = timer.querySelector('[data-unit="hours"]');
    const m = timer.querySelector('[data-unit="minutes"]');
    const s = timer.querySelector('[data-unit="seconds"]');
    if (d) d.textContent = pad(days);
    if (h) h.textContent = pad(hours);
    if (m) m.textContent = pad(minutes);
    if (s) s.textContent = pad(seconds);
  }

  function tick() {
    const now = new Date();

    if (heroTimer) {
      // Early bird ended May 2, 2026 — hero countdown now always targets the event date
      if (heroLabel) heroLabel.textContent = 'Event starts in';
      renderTimer(heroTimer, eventDate, 'EVENT DAY IS HERE!');
    }

    if (bottomTimer) {
      renderTimer(bottomTimer, eventDate, 'EVENT DAY IS HERE!');
    }
  }

  tick();
  setInterval(tick, 1000);
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

  // threshold:0 + rootMargin bottom:-10% => fires as soon as the top of the
  // section enters the viewport. A threshold like 0.1 BREAKS sections that are
  // taller than ~10x the viewport height (e.g. #speakers on mobile, ~8000px
  // tall on an iPhone SE) because 10% of the target can never be on screen
  // at once, so .visible is never added and opacity stays at 0.
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0, rootMargin: '0px 0px -10% 0px' }
  );

  animatedEls.forEach((el) => observer.observe(el));

  // Safety net: if a section is already above the fold on load (or if the
  // observer never fires for any reason), reveal it on first scroll/touch.
  const fallback = () => {
    animatedEls.forEach((el) => el.classList.add('visible'));
    window.removeEventListener('scroll', fallback);
    window.removeEventListener('touchstart', fallback);
  };
  window.addEventListener('scroll', fallback, { once: true, passive: true });
  window.addEventListener('touchstart', fallback, { once: true, passive: true });
}


// --- 7. Safari/mobile autoplay fix for background video + hero video ---

function initBgVideo() {
  const vids = document.querySelectorAll('.bg-video-fixed, .hero-poster-video');
  if (!vids.length) return;

  function tryPlayAll() {
    vids.forEach(function (vid) {
      // Ensure attributes are set (some Safari versions ignore HTML attrs)
      vid.muted = true;
      vid.playsInline = true;
      var p = vid.play();
      if (p && typeof p.catch === 'function') {
        p.catch(function () {
          // Autoplay blocked — try again on first user interaction
          var events = ['touchstart', 'click', 'scroll'];
          function playOnInteraction() {
            vids.forEach(function (v) { v.play(); });
            events.forEach(function (e) {
              document.removeEventListener(e, playOnInteraction);
            });
          }
          events.forEach(function (e) {
            document.addEventListener(e, playOnInteraction, { once: true, passive: true });
          });
        });
      }
    });
  }

  // Try immediately, and again after load in case Safari deferred it
  tryPlayAll();
  window.addEventListener('load', tryPlayAll);
}
