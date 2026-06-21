// Dark mode toggle
function toggleDarkMode() {
  const html = document.documentElement;
  const isDark = html.classList.toggle('dark');
  localStorage.theme = isDark ? 'dark' : 'light';
  updateDarkIcon(isDark);
}

function updateDarkIcon(isDark) {
  const icon = document.getElementById('dark-icon');
  if (icon) icon.textContent = isDark ? 'light_mode' : 'dark_mode';
}

document.addEventListener('DOMContentLoaded', () => {
  updateDarkIcon(document.documentElement.classList.contains('dark'));

  const darkToggle = document.getElementById('dark-toggle');
  if (darkToggle) darkToggle.addEventListener('click', toggleDarkMode);
  // Scroll reveal animation
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('active');
      }
    });
  }, { threshold: 0.15 });

  document.querySelectorAll('.reveal-up').forEach(el => observer.observe(el));

  // Image skeleton: fade-in on load
  document.querySelectorAll('.img-skeleton img').forEach(img => {
    if (img.complete) {
      img.classList.add('loaded');
    } else {
      img.addEventListener('load', () => img.classList.add('loaded'));
      img.addEventListener('error', () => img.classList.add('loaded'));
    }
  });

  // Nav shrink on scroll + back-to-top（用 requestAnimationFrame 节流，避免每个
  // scroll 事件都同步读写样式造成卡顿）
  const nav = document.getElementById('global-nav');
  const navInner = document.getElementById('nav-inner');
  const backToTop = document.getElementById('back-to-top');
  let ticking = false;

  function onScroll() {
    const y = window.scrollY;
    const scrolled = y > 50;

    if (nav) nav.classList.toggle('shadow-sm', scrolled);
    // 内边距收缩作用在内层容器（padding 写在 nav-inner 上，不是 nav 本身）
    if (navInner) {
      navInner.classList.toggle('py-2', scrolled);
      navInner.classList.toggle('py-3', !scrolled);
    }

    if (backToTop) {
      const show = y > 400;
      backToTop.classList.toggle('opacity-0', !show);
      backToTop.classList.toggle('translate-y-4', !show);
      backToTop.classList.toggle('pointer-events-none', !show);
      backToTop.classList.toggle('opacity-100', show);
      backToTop.classList.toggle('translate-y-0', show);
    }
    ticking = false;
  }

  window.addEventListener('scroll', () => {
    if (!ticking) {
      ticking = true;
      window.requestAnimationFrame(onScroll);
    }
  }, { passive: true });
});
