/* FunAvatar — a finite, original-logo construction sequence. No external runtime. */
(() => {
  'use strict';

  const DURATION = 4.8;
  const TAU = Math.PI * 2;
  const clamp = (n, a = 0, b = 1) => Math.max(a, Math.min(b, n));
  const smooth = (a, b, n) => {
    const p = clamp((n - a) / (b - a));
    return p * p * (3 - 2 * p);
  };
  const random = n => {
    const value = Math.sin(n * 127.1 + 311.7) * 43758.5453123;
    return value - Math.floor(value);
  };

  function circle(a, b, c) {
    const denominator = 2 * (a.u * (b.v - c.v) + b.u * (c.v - a.v) + c.u * (a.v - b.v));
    if (Math.abs(denominator) < 0.0000001) return null;
    const aa = a.u * a.u + a.v * a.v;
    const bb = b.u * b.u + b.v * b.v;
    const cc = c.u * c.u + c.v * c.v;
    const u = (aa * (b.v - c.v) + bb * (c.v - a.v) + cc * (a.v - b.v)) / denominator;
    const v = (aa * (c.u - b.u) + bb * (a.u - c.u) + cc * (b.u - a.u)) / denominator;
    return { u, v, radius: (u - a.u) ** 2 + (v - a.v) ** 2 };
  }

  function triangulate(vertices) {
    const count = vertices.length;
    const points = vertices.concat([{ u: -2, v: -2 }, { u: 3, v: -2 }, { u: 0.5, v: 4 }]);
    const make = (a, b, c) => ({ a, b, c, circle: circle(points[a], points[b], points[c]) });
    let triangles = [make(count, count + 1, count + 2)];
    for (let index = 0; index < count; index += 1) {
      const point = points[index];
      const edges = new Map();
      triangles = triangles.filter(triangle => {
        const circum = triangle.circle;
        if (!circum || (point.u - circum.u) ** 2 + (point.v - circum.v) ** 2 > circum.radius + 0.0000001) return true;
        [[triangle.a, triangle.b], [triangle.b, triangle.c], [triangle.c, triangle.a]].forEach(([a, b]) => {
          const key = a < b ? `${a}:${b}` : `${b}:${a}`;
          const edge = edges.get(key);
          if (edge) edge.count += 1;
          else edges.set(key, { a, b, count: 1 });
        });
        return false;
      });
      edges.forEach(edge => {
        if (edge.count === 1) {
          const triangle = make(edge.a, edge.b, index);
          if (triangle.circle) triangles.push(triangle);
        }
      });
    }
    return triangles.filter(triangle => triangle.a < count && triangle.b < count && triangle.c < count);
  }

  function buildMesh(image) {
    let alpha;
    try {
      const sample = document.createElement('canvas');
      sample.width = sample.height = 192;
      const context = sample.getContext('2d', { willReadFrequently: true });
      if (!context) throw new Error('Sampling unavailable');
      context.drawImage(image, 0, 0, 192, 192);
      const pixels = context.getImageData(0, 0, 192, 192).data;
      alpha = (u, v) => {
        if (u < 0 || v < 0 || u > 1 || v > 1) return 0;
        return pixels[(Math.min(191, Math.floor(v * 192)) * 192 + Math.min(191, Math.floor(u * 192))) * 4 + 3];
      };
    } catch (_) {
      // A cross-origin image may be drawable without allowing pixel inspection.
      alpha = (u, v) => ((u - 0.5) / 0.39) ** 2 + ((v - 0.54) / 0.39) ** 2 < 1 ? 255 : 0;
    }

    const points = [];
    const add = (u, v) => {
      if (points.some(point => Math.hypot(point.u - u, point.v - v) < 0.017)) return;
      const index = points.length;
      points.push({ u, v, delay: (1 - v) * 0.96 + Math.abs(u - 0.5) * 0.18 + random(index) * 0.075, seed: random(index + 90) });
    };
    for (let row = 0; row < 13; row += 1) {
      const v = 0.11 + row * 0.066;
      for (let column = 0; column < 13; column += 1) {
        const u = 0.07 + column * 0.071 + (row % 2) * 0.0355;
        if (alpha(u, v) > 100) add(u, v);
      }
    }
    // Silhouette samples keep the topology tied to the actual original artwork.
    for (let ray = 0; ray < 60; ray += 1) {
      const angle = ray / 60 * TAU;
      let last = 0;
      let run = 0;
      for (let radius = 0; radius < 0.6; radius += 1 / 192) {
        const u = 0.5 + Math.cos(angle) * radius;
        const v = 0.56 + Math.sin(angle) * radius;
        if (alpha(u, v) > 100) {
          run += 1;
          if (run >= 3) last = radius;
        } else run = 0;
      }
      if (last) add(0.5 + Math.cos(angle) * last, 0.56 + Math.sin(angle) * last);
    }
    // Landmark vertices let the eyes, mouth and hair read even in wireframe.
    [[0.27, 0.54], [0.32, 0.515], [0.38, 0.55], [0.42, 0.61], [0.35, 0.66], [0.29, 0.63],
      [0.73, 0.54], [0.68, 0.515], [0.62, 0.55], [0.58, 0.61], [0.65, 0.66], [0.71, 0.63],
      [0.45, 0.69], [0.5, 0.72], [0.55, 0.69], [0.5, 0.82], [0.5, 0.49], [0.47, 0.32],
      [0.72, 0.28], [0.59, 0.18], [0.83, 0.1]].forEach(([u, v]) => { if (alpha(u, v) > 50) add(u, v); });

    const triangles = triangulate(points).filter(triangle => {
      const a = points[triangle.a], b = points[triangle.b], c = points[triangle.c];
      return alpha((a.u + b.u + c.u) / 3, (a.v + b.v + c.v) / 3) > 90;
    }).map(triangle => {
      const vertices = [points[triangle.a], points[triangle.b], points[triangle.c]];
      return { ...triangle, delay: vertices.reduce((sum, point) => sum + point.delay, 0) / 3, side: vertices.reduce((sum, point) => sum + point.u, 0) / 3 };
    });
    triangles.sort((a, b) => b.delay - a.delay);
    return { points, triangles };
  }

  function mount(canvas, options = {}) {
    const context = canvas && typeof canvas.getContext === 'function' ? canvas.getContext('2d', { alpha: true }) : null;
    let image = null;
    let mesh = null;
    let imageState = 'loading';
    let playing = false;
    let destroyed = false;
    let token = 0;
    let frame = 0;
    let start = null;
    let width = 1;
    let height = 1;
    let ratio = 1;
    let stage = '';
    let observer = null;

    const notify = (callback, value) => {
      if (typeof callback === 'function') {
        try { callback(value); } catch (_) { /* A UI callback must not strand the renderer. */ }
      }
    };
    const setStage = next => {
      if (stage === next) return;
      stage = next;
      notify(options.onStage, next);
    };
    const resize = () => {
      if (!context || destroyed) return;
      const bounds = canvas.getBoundingClientRect();
      width = Math.max(1, bounds.width || canvas.clientWidth || 1);
      height = Math.max(1, bounds.height || canvas.clientHeight || width);
      ratio = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
      const nextWidth = Math.round(width * ratio), nextHeight = Math.round(height * ratio);
      if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
        canvas.width = nextWidth;
        canvas.height = nextHeight;
      }
    };
    const complete = (run, fallback) => {
      if (destroyed || !playing || run !== token) return;
      playing = false;
      frame = 0;
      setStage('complete');
      notify(options.onComplete, { fallback: !!fallback, duration: fallback ? 0 : DURATION });
    };

    function drawGuides(time, x, y, size) {
      const opacity = (1 - smooth(2.7, 4.15, time)) * smooth(0, 0.35, time);
      if (opacity < 0.005) return;
      context.save();
      context.globalAlpha = opacity;
      context.strokeStyle = 'rgba(185, 203, 221, .13)';
      context.lineWidth = 0.7;
      context.setLineDash([3, 7]);
      for (let i = 1; i < 6; i += 1) {
        const offset = 0.13 + i * 0.125;
        context.beginPath();
        context.moveTo(x + 0.1 * size, y + offset * size);
        context.lineTo(x + 0.9 * size, y + offset * size);
        context.moveTo(x + offset * size, y + 0.1 * size);
        context.lineTo(x + offset * size, y + 0.9 * size);
        context.stroke();
      }
      context.setLineDash([]);
      context.strokeStyle = 'rgba(161, 145, 255, .32)';
      context.beginPath();
      context.ellipse(x + size * 0.5, y + size * 0.82, size * 0.37, size * 0.085, 0, 0, TAU);
      context.stroke();
      context.strokeStyle = 'rgba(195, 255, 65, .55)';
      context.beginPath();
      context.ellipse(x + size * 0.5, y + size * 0.82, size * 0.37, size * 0.085, 0, time * 0.6, time * 0.6 + 0.7);
      context.stroke();
      const axisX = x + size * 0.12, axisY = y + size * 0.85, length = Math.max(15, size * 0.045);
      [[length, 0, '#ff705f'], [0, -length, '#c3ff41'], [-length * 0.6, length * 0.4, '#a191ff']].forEach(([dx, dy, color]) => {
        context.strokeStyle = color;
        context.lineWidth = 1.3;
        context.beginPath();
        context.moveTo(axisX, axisY);
        context.lineTo(axisX + dx, axisY + dy);
        context.stroke();
        context.fillStyle = color;
        context.beginPath();
        context.arc(axisX + dx, axisY + dy, 1.8, 0, TAU);
        context.fill();
      });
      context.restore();
    }

    function textureTriangle(triangle, positions, opacity) {
      if (opacity < 0.005) return;
      const source = [mesh.points[triangle.a], mesh.points[triangle.b], mesh.points[triangle.c]];
      const destination = [positions[triangle.a], positions[triangle.b], positions[triangle.c]];
      const sx0 = source[0].u * image.naturalWidth, sy0 = source[0].v * image.naturalHeight;
      const sx1 = (source[1].u - source[0].u) * image.naturalWidth;
      const sy1 = (source[1].v - source[0].v) * image.naturalHeight;
      const sx2 = (source[2].u - source[0].u) * image.naturalWidth;
      const sy2 = (source[2].v - source[0].v) * image.naturalHeight;
      const dx1 = destination[1].x - destination[0].x, dy1 = destination[1].y - destination[0].y;
      const dx2 = destination[2].x - destination[0].x, dy2 = destination[2].y - destination[0].y;
      const denominator = sx1 * sy2 - sx2 * sy1;
      if (Math.abs(denominator) < 0.01) return;
      const a = (dx1 * sy2 - dx2 * sy1) / denominator;
      const b = (dy1 * sy2 - dy2 * sy1) / denominator;
      const c = (dx2 * sx1 - dx1 * sx2) / denominator;
      const d = (dy2 * sx1 - dy1 * sx2) / denominator;
      const centerX = destination.reduce((sum, point) => sum + point.x, 0) / 3;
      const centerY = destination.reduce((sum, point) => sum + point.y, 0) / 3;
      context.save();
      context.globalAlpha = opacity;
      context.beginPath();
      destination.forEach((point, index) => {
        const distance = Math.max(1, Math.hypot(point.x - centerX, point.y - centerY));
        const x = point.x + (point.x - centerX) / distance * 0.45;
        const y = point.y + (point.y - centerY) / distance * 0.45;
        if (!index) context.moveTo(x, y); else context.lineTo(x, y);
      });
      context.closePath();
      context.clip();
      context.transform(a, b, c, d, destination[0].x - a * sx0 - c * sy0, destination[0].y - b * sx0 - d * sy0);
      context.drawImage(image, 0, 0);
      context.restore();
    }

    function render(time) {
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      const size = Math.min(width, height);
      const x = (width - size) / 2, y = (height - size) / 2;
      drawGuides(time, x, y, size);
      const positions = mesh.points.map(point => {
        const progress = clamp((time - 0.12 - point.delay) / 1.95);
        const eased = 1 - (1 - progress) ** 4;
        const remaining = 1 - eased;
        const angle = point.seed * TAU + time * 0.22;
        const dx = (point.u - 0.5) * size;
        const dy = (point.v - 0.5) * size;
        const depth = (0.15 + point.seed * 0.28) * size * remaining;
        const yaw = remaining * 0.85;
        const perspective = 1 + depth / (size * 3);
        return {
          x: x + size * 0.5 + (dx * Math.cos(yaw) + depth * Math.sin(yaw) + Math.sin(angle) * size * 0.16 * remaining) * perspective,
          y: y + size * 0.5 + (dy * (1 + 0.35 * remaining) - size * 0.14 * remaining + Math.cos(angle) * size * 0.09 * remaining) * perspective,
          progress,
        };
      });
      const wireFade = 1 - smooth(3.5, 4.65, time);
      const fullImage = smooth(3.55, 4.25, time);
      mesh.triangles.forEach(triangle => {
        const vertices = [positions[triangle.a], positions[triangle.b], positions[triangle.c]];
        const arrival = Math.min(...vertices.map(point => point.progress));
        const appearance = smooth(0.05, 0.36, arrival);
        if (appearance < 0.005) return;
        const material = smooth(2.05 + triangle.delay * 0.85, 2.95 + triangle.delay * 0.85, time) * smooth(0.65, 0.95, arrival);
        context.beginPath();
        vertices.forEach((point, index) => { if (!index) context.moveTo(point.x, point.y); else context.lineTo(point.x, point.y); });
        context.closePath();
        context.fillStyle = triangle.side < 0.5 ? 'rgba(160, 231, 56, .08)' : 'rgba(255, 104, 87, .08)';
        context.globalAlpha = appearance * wireFade;
        context.fill();
        context.globalAlpha = 1;
        if (fullImage < 0.999) textureTriangle(triangle, positions, material);
      });
      if (fullImage > 0.001) {
        context.globalAlpha = fullImage;
        context.drawImage(image, x, y, size, size);
        context.globalAlpha = 1;
      }
      // Topology remains visible over the growing material, like an edit-mode viewport.
      if (wireFade > 0.005) {
        context.lineWidth = Math.max(0.65, size / 650);
        mesh.triangles.forEach(triangle => {
          const vertices = [positions[triangle.a], positions[triangle.b], positions[triangle.c]];
          const arrival = Math.min(...vertices.map(point => point.progress));
          const appearance = smooth(0.025, 0.3, arrival);
          if (appearance < 0.005) return;
          context.globalAlpha = appearance * wireFade * (0.22 + 0.32 * (1 - fullImage));
          context.strokeStyle = triangle.side < 0.5 ? '#c5ff4c' : '#ff8879';
          context.beginPath();
          vertices.forEach((point, index) => { if (!index) context.moveTo(point.x, point.y); else context.lineTo(point.x, point.y); });
          context.closePath();
          context.stroke();
        });
        positions.forEach((point, index) => {
          const opacity = smooth(0, 0.13, point.progress) * wireFade;
          if (opacity < 0.005) return;
          context.globalAlpha = opacity * 0.85;
          context.fillStyle = mesh.points[index].u < 0.5 ? '#dbff91' : '#ffbaad';
          context.beginPath();
          context.arc(point.x, point.y, Math.max(1, size / 350), 0, TAU);
          context.fill();
        });
      }
      context.globalAlpha = 1;
      const scan = smooth(2.8, 3.05, time) * (1 - smooth(3.8, 4.15, time));
      if (scan > 0.005) {
        const scanY = y + size * (0.12 + clamp((time - 2.8) / 1.35) * 0.8);
        const gradient = context.createLinearGradient(0, scanY - size * 0.05, 0, scanY + size * 0.05);
        gradient.addColorStop(0, 'rgba(255,255,255,0)');
        gradient.addColorStop(0.5, `rgba(228,255,216,${0.2 * scan})`);
        gradient.addColorStop(1, 'rgba(255,255,255,0)');
        context.save();
        context.globalCompositeOperation = 'source-atop';
        context.fillStyle = gradient;
        context.fillRect(x, scanY - size * 0.05, size, size * 0.1);
        context.restore();
      }
    }

    const begin = run => {
      if (destroyed || !playing || run !== token) return;
      if (!context || imageState === 'failed') {
        Promise.resolve().then(() => complete(run, true));
        return;
      }
      if (imageState !== 'ready') return;
      resize();
      start = null;
      const tick = timestamp => {
        if (destroyed || !playing || run !== token) return;
        if (start === null) start = timestamp;
        const time = Math.min(DURATION, (timestamp - start) / 1000);
        setStage(time < 0.75 ? 'vertices' : time < 2.3 ? 'mesh' : 'material');
        try { render(time); } catch (_) { complete(run, true); return; }
        if (time >= DURATION) complete(run, false);
        else frame = window.requestAnimationFrame(tick);
      };
      frame = window.requestAnimationFrame(tick);
    };
    const stop = () => {
      playing = false;
      token += 1;
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
    };
    const play = () => {
      if (destroyed) return;
      stop();
      playing = true;
      stage = '';
      begin(token);
    };
    const destroy = () => {
      if (destroyed) return;
      stop();
      destroyed = true;
      if (observer) observer.disconnect();
      window.removeEventListener('resize', resize);
      if (image) image.onload = image.onerror = null;
      if (context) {
        context.setTransform(1, 0, 0, 1, 0, 0);
        context.clearRect(0, 0, canvas.width, canvas.height);
      }
      image = mesh = null;
    };

    if (context && typeof window.ResizeObserver === 'function') {
      observer = new window.ResizeObserver(resize);
      observer.observe(canvas);
    } else if (context) window.addEventListener('resize', resize, { passive: true });
    if (!context || typeof window.Image !== 'function') imageState = 'failed';
    else {
      image = new window.Image();
      image.decoding = 'async';
      image.onload = () => {
        if (destroyed) return;
        try {
          if (!image.naturalWidth || !image.naturalHeight) throw new Error('Empty image');
          mesh = buildMesh(image);
          if (!mesh.points.length || !mesh.triangles.length) throw new Error('Empty mesh');
          imageState = 'ready';
        } catch (_) { imageState = 'failed'; }
        if (playing) begin(token);
      };
      image.onerror = () => {
        if (destroyed) return;
        imageState = 'failed';
        if (playing) begin(token);
      };
      if (options.imageSrc) image.src = options.imageSrc;
      else imageState = 'failed';
    }
    return { play, stop, destroy };
  }

  window.FunAvatarConstruction = Object.freeze({ mount });
})();
