/* FunAvatar — cinematic editorial motion, progressively enhanced and finite. */
(() => {
  'use strict';

  const root = document.documentElement;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));
  let current = null;

  function createMotion() {
    if (typeof window.IntersectionObserver !== 'function' || typeof window.requestAnimationFrame !== 'function') return null;
    const fine = window.matchMedia('(hover: hover) and (pointer: fine)');
    const lightweight = window.matchMedia('(max-width: 699px), (pointer: coarse)');
    const removers = [];
    const decorated = [];
    const revealTargets = [];
    const headingProxies = new Map();
    const sections = Array.from(document.querySelectorAll('.method, .evidence, .start, .feedback, .faq'));
    let frame = 0;
    let scrollDirty = true;
    let pendingPointer = null;
    let activePointer = null;
    let destroyed = false;
    let observer = null;
    let progress = null;

    const listen = (element, name, callback, options) => {
      element.addEventListener(name, callback, options);
      removers.push(() => element.removeEventListener(name, callback, options));
    };
    const reveal = target => {
      target.classList.add('is-revealed');
      if (observer) observer.unobserve(target);
    };
    const resetPointer = node => {
      if (!node) return;
      ['--magnetic-x', '--magnetic-y', '--motion-tilt-x', '--motion-tilt-y', '--motion-tilt-angle'].forEach(property => node.style.removeProperty(property));
    };

    const update = () => {
      frame = 0;
      if (destroyed || document.hidden) return;
      let sectionPositions = null;
      let scrollProgress = null;
      let pointerValues = null;
      if (scrollDirty) {
        scrollDirty = false;
        const viewport = window.innerHeight || root.clientHeight;
        const maximum = Math.max(1, root.scrollHeight - viewport);
        scrollProgress = clamp((window.scrollY || root.scrollTop || 0) / maximum, 0, 1);
        sectionPositions = lightweight.matches ? [] : sections.filter(section => section.matches('.method, .start')).map(section => {
          const bounds = section.getBoundingClientRect();
          return {
            section,
            drift: clamp((viewport * 0.5 - (bounds.top + bounds.height * 0.3)) * 0.055, -24, 24),
            rail: clamp((viewport * 0.82 - bounds.top) / Math.max(1, bounds.height * 0.8), 0, 1),
          };
        });
      }
      if (pendingPointer) {
        const pointer = pendingPointer;
        pendingPointer = null;
        const transitioning = pointer.node.closest('.path-slides.is-transitioning');
        if (fine.matches && !lightweight.matches && !transitioning) {
          const bounds = pointer.node.getBoundingClientRect();
          const x = clamp((pointer.x - bounds.left - bounds.width / 2) / Math.max(1, bounds.width / 2), -1, 1);
          const y = clamp((pointer.y - bounds.top - bounds.height / 2) / Math.max(1, bounds.height / 2), -1, 1);
          pointerValues = { ...pointer, x, y };
        } else resetPointer(pointer.node);
      }
      // Read geometry first; all paint-only updates happen together afterwards.
      if (scrollProgress !== null && progress) progress.style.transform = `scaleX(${scrollProgress.toFixed(4)})`;
      if (sectionPositions) sectionPositions.forEach(({ section, drift, rail }) => {
        section.style.setProperty('--motion-drift', `${drift.toFixed(2)}px`);
        if (section.classList.contains('method')) section.style.setProperty('--motion-rail', rail.toFixed(3));
      });
      if (pointerValues) {
        const { node, kind, x, y } = pointerValues;
        if (activePointer && activePointer !== node) resetPointer(activePointer);
        activePointer = node;
        if (kind === 'magnetic') {
          node.style.setProperty('--magnetic-x', `${(x * 6).toFixed(2)}px`);
          node.style.setProperty('--magnetic-y', `${(y * 4).toFixed(2)}px`);
        } else {
          node.style.setProperty('--motion-tilt-x', (-y || 0.001).toFixed(3));
          node.style.setProperty('--motion-tilt-y', (x || 0.001).toFixed(3));
          node.style.setProperty('--motion-tilt-angle', `${(Math.hypot(x, y) * 2.1).toFixed(3)}deg`);
        }
      }
    };
    const requestUpdate = () => {
      if (!frame && !document.hidden && !destroyed) frame = window.requestAnimationFrame(update);
    };
    const onScroll = () => { scrollDirty = true; requestUpdate(); };

    const destroy = () => {
      if (destroyed) return;
      destroyed = true;
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
      if (observer) observer.disconnect();
      headingProxies.clear();
      removers.splice(0).forEach(remove => remove());
      revealTargets.forEach(target => {
        target.classList.remove('reveal-ready', 'is-revealed', 'motion-heading', 'motion-row');
        target.style.removeProperty('--reveal-delay');
      });
      decorated.forEach(({ node, className }) => { node.classList.remove(className); resetPointer(node); });
      sections.forEach(section => {
        section.classList.remove('motion-section', 'is-section-inview');
        section.style.removeProperty('--motion-drift');
        section.style.removeProperty('--motion-rail');
      });
      document.querySelectorAll('[data-site-motion-decoration]').forEach(node => node.remove());
      if (progress) progress.remove();
      root.classList.remove('site-motion-enabled');
    };

    try {
      observer = new window.IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return;
          const headings = headingProxies.get(entry.target);
          if (headings) {
            headings.forEach(reveal);
            headingProxies.delete(entry.target);
          }
          if (entry.target.classList.contains('motion-section')) {
            entry.target.classList.add('is-section-inview');
            observer.unobserve(entry.target);
          } else if (entry.target.classList.contains('reveal-ready')) reveal(entry.target);
          else observer.unobserve(entry.target);
        });
      }, { threshold: 0.08, rootMargin: '0px 0px -5% 0px' });

      const selector = [
        '.section-heading > .eyebrow', '.section-heading > h2', '.section-heading > p:last-child',
        '.method-intro > .eyebrow', '.method-intro > h2', '.method-intro > p:last-child', '.method-steps > li',
        '.evidence-heading > .eyebrow', '.evidence-heading > h2', '.evidence-heading > p:last-child', '.evidence-column', '.evidence-note',
        '.start-layout > div:first-child > .eyebrow', '.start-layout h2', '.start-action',
        '.feedback-intro > .eyebrow', '.feedback-intro > h2', '.feedback-intro > p:not(.eyebrow)',
        '.feedback-detail > h3', '.report-fields > div', '.privacy-note',
        '.faq-layout > div:first-child > .eyebrow', '.faq-layout h2', '.faq-list > details',
      ].join(', ');
      const groupCounts = new Map();
      document.querySelectorAll(selector).forEach(target => {
        if (target.closest('.hero-art, .hero-logo, .path-panel')) return;
        const group = target.closest('.method-steps, .evidence-columns, .report-fields, .faq-list') || target.parentElement;
        const index = groupCounts.get(group) || 0;
        groupCounts.set(group, index + 1);
        target.style.setProperty('--reveal-delay', `${Math.min(index * 65, 195)}ms`);
        target.classList.add('reveal-ready');
        if (target.matches('h2')) target.classList.add('motion-heading');
        if (target.matches('.method-steps > li, .report-fields > div, .faq-list > details')) target.classList.add('motion-row');
        revealTargets.push(target);
        if (target.matches('h2')) {
          // Observing the clipped heading itself yields an empty intersection.
          // Its unchanged parent supplies geometry while the heading keeps its wipe.
          const proxy = target.parentElement;
          if (!headingProxies.has(proxy)) headingProxies.set(proxy, []);
          headingProxies.get(proxy).push(target);
          observer.observe(proxy);
        } else observer.observe(target);
      });

      sections.forEach(section => {
        section.classList.add('motion-section');
        observer.observe(section);
      });
      [['.method', 'IDENTITÀ'], ['.start', 'CREA.']].forEach(([selector, word]) => {
        const section = document.querySelector(selector);
        if (!section) return;
        const ghost = document.createElement('span');
        ghost.className = 'motion-ghost';
        ghost.textContent = word;
        ghost.setAttribute('aria-hidden', 'true');
        ghost.setAttribute('data-site-motion-decoration', '');
        section.prepend(ghost);
      });

      progress = document.createElement('div');
      progress.className = 'site-scroll-progress';
      progress.setAttribute('aria-hidden', 'true');
      document.body.append(progress);

      const addPointer = (node, className, kind) => {
        node.classList.add(className);
        decorated.push({ node, className });
        listen(node, 'pointermove', event => {
          if (!fine.matches || lightweight.matches || event.pointerType === 'touch' || document.hidden) return;
          pendingPointer = { node, kind, x: event.clientX, y: event.clientY };
          requestUpdate();
        }, { passive: true });
        const leave = () => {
          if (pendingPointer && pendingPointer.node === node) pendingPointer = null;
          if (activePointer === node) activePointer = null;
          resetPointer(node);
        };
        listen(node, 'pointerleave', leave, { passive: true });
        listen(node, 'pointercancel', leave, { passive: true });
        listen(node, 'blur', leave);
      };
      document.querySelectorAll('main .button').forEach(node => {
        if (!node.closest('.hero-art, .path-panel')) addPointer(node, 'motion-magnetic', 'magnetic');
      });
      document.querySelectorAll('.panel-outcome').forEach(node => addPointer(node, 'motion-tilt', 'tilt'));

      listen(document, 'focusin', event => {
        const target = event.target.closest && event.target.closest('.reveal-ready');
        if (target) reveal(target);
      });
      listen(window, 'scroll', onScroll, { passive: true });
      listen(window, 'resize', onScroll, { passive: true });
      listen(window, 'load', onScroll, { once: true });
      listen(document, 'visibilitychange', () => {
        if (document.hidden) {
          if (frame) window.cancelAnimationFrame(frame);
          frame = 0;
          pendingPointer = null;
          resetPointer(activePointer);
          activePointer = null;
        } else onScroll();
      });
      const onPointerPreference = () => {
        pendingPointer = null;
        resetPointer(activePointer);
        activePointer = null;
      };
      if (fine.addEventListener) listen(fine, 'change', onPointerPreference);
      else if (fine.addListener) {
        fine.addListener(onPointerPreference);
        removers.push(() => fine.removeListener(onPointerPreference));
      }
      listen(lightweight, 'change', () => { onPointerPreference(); onScroll(); });
      root.classList.add('site-motion-enabled');
      requestUpdate();
      return { destroy };
    } catch (_) {
      // Enhancement failure leaves every original paragraph and control usable.
      destroy();
      return null;
    }
  }

  const refresh = () => {
    if (current) current.destroy();
    current = reduced.matches ? null : createMotion();
  };
  refresh();
  if (reduced.addEventListener) reduced.addEventListener('change', refresh);
  else if (reduced.addListener) reduced.addListener(refresh);

  window.FunAvatarSiteMotion = {
    destroy() {
      if (current) current.destroy();
      current = null;
      if (reduced.removeEventListener) reduced.removeEventListener('change', refresh);
      else if (reduced.removeListener) reduced.removeListener(refresh);
    },
  };
})();
