/* Optional location cues. Static menus and article links work without JS. */
(() => {
  'use strict';

  const initialize = () => {
    const root = document.querySelector('body.unified-ui');
    if (!root || root.dataset.unifiedInitialized) return;
    root.dataset.unifiedInitialized = 'true';

    const decode = (value) => {
      try { return decodeURIComponent(value); } catch { return value; }
    };
    const pathname = (value) => {
      try {
        const path = decode(new URL(value, window.location.href).pathname);
        return path.replace(/\/index\.html$/, '/').replace(/\/+$/, '') || '/';
      } catch { return ''; }
    };

    // The renderer owns the active menu. This fallback helps older cached HTML.
    const navigation = root.querySelector('[data-unified-nav]');
    if (navigation && !navigation.querySelector('a[aria-current="page"]')) {
      const current = pathname(window.location.href);
      const links = Array.from(navigation.querySelectorAll('a[href]'));
      let best = null;
      let longest = -1;
      for (const link of links) {
        const path = pathname(link.href);
        const matches = path && (path === current || (path !== '/' && current.startsWith(path + '/')));
        if (matches && path.length > longest) {
          best = link;
          longest = path.length;
        }
      }
      if (best) {
        for (const link of links) link.classList.toggle('active', link === best);
        best.setAttribute('aria-current', 'page');
      }
    }

    for (const toc of root.querySelectorAll('[data-ui-toc]')) {
      const entries = Array.from(toc.querySelectorAll('a[href^="#"]')).map((link) => ({
        link,
        target: document.getElementById(decode(link.getAttribute('href').slice(1))),
      })).filter((entry) => entry.target);
      if (!entries.length) continue;

      const setCurrent = (selected) => {
        for (const entry of entries) {
          if (entry === selected) entry.link.setAttribute('aria-current', 'location');
          else entry.link.removeAttribute('aria-current');
        }
      };
      const fromHash = () => {
        const id = decode(window.location.hash.slice(1));
        const selected = entries.find((entry) => entry.target.id === id);
        if (selected) setCurrent(selected);
      };
      fromHash();
      window.addEventListener('hashchange', fromHash);

      if (!('IntersectionObserver' in window)) continue;
      const visible = new Set();
      const observer = new IntersectionObserver((changes) => {
        for (const change of changes) {
          if (change.isIntersecting) visible.add(change.target);
          else visible.delete(change.target);
        }
        const selected = entries.find((entry) => visible.has(entry.target));
        if (selected) setCurrent(selected);
      }, { rootMargin: '-18% 0px -62% 0px', threshold: 0 });
      for (const entry of entries) observer.observe(entry.target);
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, { once: true });
  else initialize();
})();
