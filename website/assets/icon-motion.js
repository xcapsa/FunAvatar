/* FunAvatar — finite icon gestures, with no animation loop or scroll capture. */
(() => {
  'use strict';

  if (typeof Element.prototype.animate !== 'function') return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const hover = window.matchMedia('(any-hover: hover)');
  const focusSelector = window.CSS && CSS.supports && CSS.supports('selector(:focus-visible)') ? ':focus-visible' : ':focus';
  const hosts = 'a, button, summary, .panel-outcome, .evidence-column, .evidence-note';
  const active = new Map();
  let touch = null;

  const gestures = {
    'arrow-up-right': ['none', 'translate(3px, -3px) scale(1.12)', 'translate(-1px, 1px)', 'none'],
    'arrow-down': ['none', 'translateY(4px) scale(1.1)', 'translateY(-1px)', 'none'],
    'arrow-left': ['none', 'translateX(-4px) scale(1.1)', 'translateX(1px)', 'none'],
    'arrow-right': ['none', 'translateX(4px) scale(1.1)', 'translateX(-1px)', 'none'],
    replay: ['rotate(0deg)', 'rotate(-35deg)', 'rotate(220deg)', 'rotate(360deg)'],
    spark: ['none', 'rotate(-18deg) scale(.88)', 'rotate(22deg) scale(1.16)', 'none'],
    cube: ['none', 'translateY(-3px) rotate(-10deg) scale(1.06)', 'rotate(6deg)', 'none'],
    inspect: ['none', 'translate(3px, -2px) rotate(8deg)', 'translate(-2px, 1px) rotate(-5deg)', 'none'],
    target: ['none', 'scale(.85) rotate(-15deg)', 'scale(1.12) rotate(8deg)', 'none'],
    plus: ['none', 'scale(.8)', 'scale(1.16)', 'none'],
  };
  const pop = ['none', 'scale(.84)', 'scale(1.12)', 'none'];
  const hostFor = target => target instanceof Element ? target.closest(hosts) : null;

  function react(host) {
    if (!host || reduced.matches || document.hidden || host.closest('[inert], [hidden]')) return;
    host.querySelectorAll('.site-icon').forEach(icon => {
      const use = icon.querySelector('use');
      const symbol = use && (use.getAttribute('href') || '').split('#').pop();
      const previous = active.get(icon);
      if (previous) previous.cancel();
      const animation = icon.animate((gestures[symbol] || pop).map(transform => ({ transform })), {
        duration: symbol === 'replay' ? 650 : 520,
        easing: 'cubic-bezier(.22,.8,.3,1)',
        iterations: 1,
      });
      active.set(icon, animation);
      const clear = () => { if (active.get(icon) === animation) active.delete(icon); };
      animation.onfinish = clear;
      animation.oncancel = clear;
    });
  }

  function clear() {
    touch = null;
    active.forEach(animation => animation.cancel());
    active.clear();
  }

  document.addEventListener('pointerover', event => {
    if (event.pointerType === 'touch' || !hover.matches) return;
    const host = hostFor(event.target);
    if (host && !host.contains(event.relatedTarget)) react(host);
  }, { passive: true });
  document.addEventListener('focusin', event => {
    const host = hostFor(event.target);
    if (host && event.target.matches(focusSelector)) react(host);
  });
  document.addEventListener('pointerdown', event => {
    if (event.pointerType !== 'touch') return;
    touch = null;
    if (!event.isPrimary || reduced.matches || document.hidden) return;
    const host = hostFor(event.target);
    if (host) touch = { host, id: event.pointerId, x: event.clientX, y: event.clientY, at: event.timeStamp };
  }, { passive: true });
  document.addEventListener('pointermove', event => {
    if (touch && event.pointerId === touch.id && Math.hypot(event.clientX - touch.x, event.clientY - touch.y) > 12) touch = null;
  }, { passive: true });
  document.addEventListener('pointerup', event => {
    if (!touch || event.pointerId !== touch.id) return;
    const tap = touch;
    touch = null;
    if (event.timeStamp - tap.at < 700 && Math.hypot(event.clientX - tap.x, event.clientY - tap.y) <= 12 && hostFor(event.target) === tap.host) react(tap.host);
  }, { passive: true });
  document.addEventListener('pointercancel', () => { touch = null; }, { passive: true });
  document.addEventListener('scroll', () => { touch = null; }, { passive: true, capture: true });
  document.addEventListener('visibilitychange', () => { if (document.hidden) clear(); });
  window.addEventListener('pagehide', clear);
  if (reduced.addEventListener) reduced.addEventListener('change', clear);
  else if (reduced.addListener) reduced.addListener(clear);
})();
