(function () {
  'use strict';

  // Sticky header background swap
  const header = document.querySelector('.site-header');
  const onScroll = () => {
    if (window.scrollY > 80) header.classList.add('is-scrolled');
    else header.classList.remove('is-scrolled');
  };
  document.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // Scroll reveal — disabled if user prefers reduced motion
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const reveals = document.querySelectorAll('.reveal');
  if (!reduced && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 });
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add('is-visible'));
  }

  // Copy-to-clipboard for code blocks
  document.querySelectorAll('.code-block').forEach((block) => {
    const btn = block.querySelector('.copy');
    const code = block.querySelector('pre');
    if (!btn || !code) return;
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(code.textContent.trim());
        btn.classList.add('is-copied');
        const original = btn.textContent;
        btn.textContent = 'Copied';
        setTimeout(() => {
          btn.classList.remove('is-copied');
          btn.textContent = original;
        }, 1200);
      } catch (err) {
        btn.textContent = 'Copy failed';
      }
    });
  });
})();
