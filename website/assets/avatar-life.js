/* FunAvatar's original logo, animated in independent facial layers. */
(function () {
  'use strict';

  var instanceCount = 0;
  var clamp = function (value, min, max) { return Math.max(min, Math.min(max, value)); };
  var ease = function (value) { return value * value * (3 - 2 * value); };

  function mount(stage, options) {
    if (!stage || !stage.querySelector) throw new TypeError('FunAvatarLife needs an avatar stage.');
    options = options || {};
    var container = stage.querySelector('.avatar-living-face');
    if (!container) throw new Error('The avatar living-face layer is missing.');
    var source = options.imageSrc || 'assets/funavatar-logo.png';
    var prefix = 'fa-face-' + (++instanceCount) + '-';
    var ns = 'http://www.w3.org/2000/svg';
    // Both eye silhouettes are traced in the original 1254 px artwork.
    // Eyebrows, hair, headphones and mouth retain the untouched raster.
    var leftEye = 'M309 653 L346 672 Q381 650 429 670 L443 686 Q476 698 488 727 L511 748 Q531 774 543 814 L542 830 Q495 853 438 847 Q366 829 352 766 Q342 716 309 653Z';
    var rightEye = 'M929 657 L900 672 Q868 650 823 672 L812 685 Q781 699 764 728 L735 748 Q717 779 706 816 L710 831 Q760 853 811 846 Q885 825 898 765 Q904 718 929 657Z';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 1254 1254');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    svg.classList.add('avatar-face-art');
    svg.innerHTML =
      '<defs>' +
        '<linearGradient id="' + prefix + 'skin" x1="0" y1="0" x2="0" y2="1">' +
          '<stop offset="0" stop-color="#0d1220"/><stop offset="1" stop-color="#0f1423"/>' +
        '</linearGradient>' +
        '<mask id="' + prefix + 'face" maskUnits="userSpaceOnUse" x="0" y="0" width="1254" height="1254" style="mask-type:luminance">' +
          '<rect width="1254" height="1254" fill="white"/>' +
          '<path d="' + leftEye + '" fill="black"/><path d="' + rightEye + '" fill="black"/>' +
        '</mask>' +
        '<clipPath id="' + prefix + 'left"><path d="' + leftEye + '"/></clipPath>' +
        '<clipPath id="' + prefix + 'right"><path d="' + rightEye + '"/></clipPath>' +
      '</defs>' +
      '<image class="avatar-face-base" width="1254" height="1254" mask="url(#' + prefix + 'face)"/>' +
      '<path d="' + leftEye + '" fill="url(#' + prefix + 'skin)"/>' +
      '<path d="' + rightEye + '" fill="url(#' + prefix + 'skin)"/>' +
      '<g class="avatar-eye avatar-eye-left"><image width="1254" height="1254" clip-path="url(#' + prefix + 'left)"/></g>' +
      '<g class="avatar-eye avatar-eye-right"><image width="1254" height="1254" clip-path="url(#' + prefix + 'right)"/></g>' +
      '<path class="avatar-eyelid avatar-eyelid-left" d="M337 743 Q417 806 527 773" fill="none" stroke="#c7f73f" stroke-width="18" stroke-linecap="round" opacity="0"/>' +
      '<path class="avatar-eyelid avatar-eyelid-right" d="M720 774 Q810 806 910 739" fill="none" stroke="#ff5b57" stroke-width="18" stroke-linecap="round" opacity="0"/>';
    Array.prototype.forEach.call(svg.querySelectorAll('image'), function (node) {
      node.setAttribute('href', source);
    });
    container.replaceChildren(svg);

    var left = svg.querySelector('.avatar-eye-left');
    var right = svg.querySelector('.avatar-eye-right');
    var leftLid = svg.querySelector('.avatar-eyelid-left');
    var rightLid = svg.querySelector('.avatar-eyelid-right');
    var motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    var reduced = motionQuery.matches;
    var ready = false;
    var completed = false;
    var paused = false;
    var destroyed = false;
    var visible = true;
    var frame = 0;
    var lastFrame = 0;
    var blinkTimer = 0;
    var welcomeTimer = 0;
    var welcomePending = false;
    var expression = null;
    var lastTouch = -Infinity;
    var touch = null;
    var target = { x: 0, y: 0 };
    var current = { x: 0, y: 0 };
    var observer = null;
    var probe = new Image();
    var bounds = null;
    var boundsDirty = true;

    stage.dataset.avatarExpression = 'neutral';

    function active() {
      return ready && completed && !paused && !destroyed && !reduced && visible && !document.hidden;
    }

    function eyeTransform(x, y, openness, cx) {
      return 'translate(' + x.toFixed(2) + ' ' + y.toFixed(2) + ') translate(' + cx + ' 754) scale(1 ' + Math.max(0.035, openness).toFixed(4) + ') translate(' + (-cx) + ' -754)';
    }

    function paint(leftOpen, rightOpen, nod) {
      leftOpen = leftOpen === undefined ? 1 : leftOpen;
      rightOpen = rightOpen === undefined ? 1 : rightOpen;
      nod = nod || 0;
      var gazeX = current.x * 7;
      var gazeY = current.y * 4.5;
      left.setAttribute('transform', eyeTransform(gazeX, gazeY, leftOpen, 426));
      right.setAttribute('transform', eyeTransform(gazeX, gazeY, rightOpen, 816));
      leftLid.setAttribute('opacity', clamp((1 - leftOpen - 0.38) / 0.62, 0, 1).toFixed(3));
      rightLid.setAttribute('opacity', clamp((1 - rightOpen - 0.38) / 0.62, 0, 1).toFixed(3));
      // Only the eyes compress; the whole character gets a small rigid head tilt.
      svg.style.transform = 'perspective(900px) translate3d(' + (current.x * 5).toFixed(2) + 'px,' + (current.y * 3 - nod * 4).toFixed(2) + 'px,0) rotateX(' + (-current.y * 5).toFixed(2) + 'deg) rotateY(' + (current.x * 6).toFixed(2) + 'deg) rotateZ(' + (current.x * 1.3 - nod * 2.2).toFixed(2) + 'deg)';
    }

    function neutral() {
      expression = null;
      stage.dataset.avatarExpression = 'neutral';
      paint();
    }

    function clearTimers() {
      window.clearTimeout(blinkTimer);
      window.clearTimeout(welcomeTimer);
      blinkTimer = welcomeTimer = 0;
    }

    function stop() {
      clearTimers();
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
      lastFrame = 0;
      touch = null;
      boundsDirty = true;
      target.x = target.y = current.x = current.y = 0;
      neutral();
    }

    function requestFrame() {
      if (active() && !frame) frame = window.requestAnimationFrame(tick);
    }

    function scheduleBlink() {
      window.clearTimeout(blinkTimer);
      if (!active()) return;
      blinkTimer = window.setTimeout(function () {
        blinkTimer = 0;
        if (!expression) beginExpression('blink');
      }, 3900 + Math.random() * 3600);
    }

    function beginExpression(kind) {
      if (!active()) return;
      window.clearTimeout(blinkTimer);
      expression = { kind: kind, start: performance.now(), duration: kind === 'wink' ? 1050 : 205 };
      stage.dataset.avatarExpression = kind;
      requestFrame();
    }

    function tick(time) {
      frame = 0;
      if (!active()) return;
      var dt = lastFrame ? clamp(time - lastFrame, 1, 48) : 16;
      lastFrame = time;
      var damping = 1 - Math.exp(-dt / 105);
      current.x += (target.x - current.x) * damping;
      current.y += (target.y - current.y) * damping;
      var leftOpen = 1;
      var rightOpen = 1;
      var nod = 0;
      if (expression) {
        var progress = clamp((time - expression.start) / expression.duration, 0, 1);
        var closure;
        if (expression.kind === 'wink') {
          closure = progress < 0.24 ? ease(progress / 0.24) : progress < 0.48 ? 1 : 1 - ease(clamp((progress - 0.48) / 0.36, 0, 1));
          rightOpen = 1 - closure;
          nod = Math.sin(progress * Math.PI);
        } else {
          closure = progress < 0.42 ? ease(progress / 0.42) : 1 - ease((progress - 0.42) / 0.58);
          leftOpen = rightOpen = 1 - closure;
        }
        if (progress >= 1) {
          expression = null;
          stage.dataset.avatarExpression = 'neutral';
          leftOpen = rightOpen = 1;
          nod = 0;
          scheduleBlink();
        }
      }
      var moving = Math.abs(target.x - current.x) > 0.001 || Math.abs(target.y - current.y) > 0.001;
      if (!moving) { current.x = target.x; current.y = target.y; }
      paint(leftOpen, rightOpen, nod);
      if (moving || expression) requestFrame();
      else lastFrame = 0;
    }

    function wake() {
      if (!active()) return;
      requestFrame();
      if (welcomePending && !welcomeTimer) {
        // Loading may finish after complete(); retain the welcome until the
        // original artwork is actually ready to reveal.
        welcomeTimer = window.setTimeout(function () {
          welcomeTimer = 0;
          if (!active()) return;
          welcomePending = false;
          beginExpression('wink');
        }, 250);
      }
      if (!expression && !welcomeTimer) scheduleBlink();
    }

    function markReady() {
      if (destroyed || ready) return;
      ready = true;
      stage.classList.add('avatar-life-ready');
      paint();
      if (completed) wake();
    }
    probe.addEventListener('load', markReady, { once: true });
    probe.src = source;
    if (probe.complete && probe.naturalWidth) markReady();

    function pointerMove(event) {
      if (event.pointerType === 'touch') {
        if (touch && event.pointerId === touch.id && Math.hypot(event.clientX - touch.x, event.clientY - touch.y) > 12) touch = null;
        return;
      }
      if (!active()) return;
      if (boundsDirty || !bounds) {
        bounds = stage.getBoundingClientRect();
        boundsDirty = false;
      }
      target.x = clamp((event.clientX - bounds.left - bounds.width / 2) / Math.max(window.innerWidth * 0.42, bounds.width), -1, 1);
      target.y = clamp((event.clientY - bounds.top - bounds.height / 2) / Math.max(window.innerHeight * 0.46, bounds.height), -1, 1);
      requestFrame();
    }
    function pointerLeave(event) {
      if (event && event.type === 'pointerout' && event.relatedTarget) return;
      target.x = target.y = 0;
      requestFrame();
    }
    function touchStart(event) {
      if (event.pointerType !== 'touch') return;
      touch = null;
      if (!event.isPrimary || !active() || !touchTarget.contains(event.target)) return;
      if (event.target.closest && event.target.closest('button, a')) return;
      touch = { id: event.pointerId, x: event.clientX, y: event.clientY, at: event.timeStamp };
    }
    function cancelTouch() { touch = null; }
    function touchReaction(event) {
      if (!touch || event.pointerId !== touch.id) return;
      var tap = touch;
      touch = null;
      if (!event.isPrimary || !active() || !touchTarget.contains(event.target)) return;
      if (event.target.closest && event.target.closest('button, a')) return;
      if (event.timeStamp - tap.at >= 700 || Math.hypot(event.clientX - tap.x, event.clientY - tap.y) > 12) return;
      if (performance.now() - lastTouch < 1400) return;
      lastTouch = performance.now();
      beginExpression('wink');
    }
    function visibilityChange() {
      if (document.hidden) stop();
      else wake();
    }
    function motionChange(event) { setReducedMotion(event.matches); }
    function invalidateBounds() { boundsDirty = true; touch = null; }

    document.addEventListener('pointermove', pointerMove, { passive: true });
    document.addEventListener('pointerout', pointerLeave, { passive: true });
    window.addEventListener('blur', pointerLeave);
    window.addEventListener('resize', invalidateBounds, { passive: true });
    document.addEventListener('scroll', invalidateBounds, { passive: true, capture: true });
    // The stage is decorative and transparent to pointer events; its parent is
    // the touch target, so the page continues to scroll and links still work.
    var touchTarget = stage.closest('.hero-art') || stage;
    document.addEventListener('pointerdown', touchStart, { passive: true });
    document.addEventListener('pointerup', touchReaction, { passive: true });
    document.addEventListener('pointercancel', cancelTouch, { passive: true });
    document.addEventListener('visibilitychange', visibilityChange);
    motionQuery.addEventListener('change', motionChange);
    if ('IntersectionObserver' in window) {
      observer = new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        if (visible) wake(); else stop();
      }, { threshold: 0.08 });
      observer.observe(stage);
    }

    function setReducedMotion(value) {
      reduced = Boolean(value);
      stage.classList.toggle('avatar-reduced-motion', reduced);
      if (reduced) { welcomePending = false; stop(); } else wake();
    }
    if (reduced) stage.classList.add('avatar-reduced-motion');

    return {
      complete: function () {
        if (destroyed) return;
        stop();
        completed = true;
        stage.classList.add('avatar-has-life', 'avatar-is-complete', 'avatar-is-living');
        stage.classList.remove('avatar-is-building');
        welcomePending = !reduced;
        wake();
      },
      pause: function () { paused = true; stop(); },
      resume: function () { paused = false; wake(); },
      setReducedMotion: setReducedMotion,
      destroy: function () {
        if (destroyed) return;
        stop();
        destroyed = true;
        if (observer) observer.disconnect();
        document.removeEventListener('pointermove', pointerMove);
        document.removeEventListener('pointerout', pointerLeave);
        window.removeEventListener('blur', pointerLeave);
        window.removeEventListener('resize', invalidateBounds);
        document.removeEventListener('scroll', invalidateBounds, true);
        document.removeEventListener('pointerdown', touchStart);
        document.removeEventListener('pointerup', touchReaction);
        document.removeEventListener('pointercancel', cancelTouch);
        document.removeEventListener('visibilitychange', visibilityChange);
        motionQuery.removeEventListener('change', motionChange);
        probe.removeEventListener('load', markReady);
        container.replaceChildren();
        stage.classList.remove('avatar-life-ready', 'avatar-is-living', 'avatar-has-life');
        delete stage.dataset.avatarExpression;
      }
    };
  }

  window.FunAvatarLife = { mount: mount };
})();
