document.addEventListener('DOMContentLoaded', () => {
  // Scroll reveal animation
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('active');
      }
    });
  }, { threshold: 0.15 });

  document.querySelectorAll('.reveal-up').forEach(el => observer.observe(el));

  // Nav shrink on scroll
  const nav = document.getElementById('global-nav');
  const backToTop = document.getElementById('back-to-top');

  if (nav) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 50) {
        nav.classList.add('shadow-sm', 'py-2');
        nav.classList.remove('py-4');
      } else {
        nav.classList.remove('shadow-sm', 'py-2');
        nav.classList.add('py-4');
      }

      // Back to top button
      if (backToTop) {
        if (window.scrollY > 400) {
          backToTop.classList.remove('opacity-0', 'translate-y-4', 'pointer-events-none');
          backToTop.classList.add('opacity-100', 'translate-y-0');
        } else {
          backToTop.classList.add('opacity-0', 'translate-y-4', 'pointer-events-none');
          backToTop.classList.remove('opacity-100', 'translate-y-0');
        }
      }
    });
  }
});
