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
  if (nav) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 50) {
        nav.classList.add('shadow-sm', 'py-2');
        nav.classList.remove('py-4');
      } else {
        nav.classList.remove('shadow-sm', 'py-2');
        nav.classList.add('py-4');
      }
    });
  }
});
