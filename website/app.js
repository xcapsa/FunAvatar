"use strict";

(() => {
  const tabList = document.querySelector(".path-tabs");
  if (!tabList) return;
  const tabs = Array.from(tabList.querySelectorAll("[data-tab]"));
  const panels = tabs.map(tab => document.querySelector(`[data-panel="${tab.dataset.tab}"]`));
  if (!tabs.length || panels.some(panel => !panel)) return;

  const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
  const viewport = document.createElement("div");
  viewport.className = "path-slides";
  tabList.after(viewport);
  panels.forEach(panel => viewport.append(panel));
  const controls = document.createElement("div");
  controls.className = "path-slide-controls";
  controls.innerHTML = '<div class="path-slide-counter" role="status" aria-live="polite" aria-atomic="true"></div><div class="path-slide-nav"><button class="path-slide-button path-slide-previous" type="button" aria-label="Percorso precedente"><span aria-hidden="true"><svg class="site-icon" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false"><use href="./assets/icons.svg#arrow-left"></use></svg></span></button><button class="path-slide-button path-slide-next" type="button" aria-label="Percorso successivo"><span aria-hidden="true"><svg class="site-icon" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false"><use href="./assets/icons.svg#arrow-right"></use></svg></span></button></div><div class="path-slide-progress" aria-hidden="true"><span></span></div>';
  viewport.after(controls);
  const counter = controls.querySelector(".path-slide-counter");
  const indicator = document.createElement("span");
  indicator.className = "path-tab-indicator";
  indicator.setAttribute("aria-hidden", "true");
  tabList.append(indicator);
  tabList.classList.add("path-tabs-enhanced");
  let active = -1;
  let revision = 0;
  let animations = [];
  let swipe = null;

  function updateIndicator() {
    if (active < 0) return;
    const listBounds = tabList.getBoundingClientRect();
    const tabBounds = tabs[active].getBoundingClientRect();
    indicator.style.width = `${tabBounds.width}px`;
    indicator.style.transform = `translateX(${tabBounds.left - listBounds.left}px)`;
  }

  function settle() {
    animations.forEach(animation => animation.cancel());
    animations = [];
    viewport.classList.remove("is-transitioning");
    viewport.style.height = "";
    panels.forEach((panel, index) => {
      panel.hidden = index !== active;
      panel.inert = index !== active;
      panel.classList.remove("is-exiting-slide");
      panel.classList.toggle("is-active-slide", index === active);
      if (index === active) panel.removeAttribute("aria-hidden");
      else panel.setAttribute("aria-hidden", "true");
    });
  }

  function activate(index, options = {}) {
    index = (index + tabs.length) % tabs.length;
    if (index === active) {
      if (options.focus) tabs[index].focus({ preventScroll: true });
      if (options.hash && window.location.hash !== tabs[index].hash) window.history.replaceState(window.history.state, "", tabs[index].hash);
      return;
    }
    const oldIndex = active;
    const outgoing = panels[oldIndex];
    const incoming = panels[index];
    const fromHeight = viewport.getBoundingClientRect().height;
    const token = ++revision;
    settle();
    // Move focus before any outgoing panel becomes inert or hidden.
    if (options.focus || outgoing?.contains(document.activeElement) || tabList.contains(document.activeElement)) tabs[index].focus({ preventScroll: true });
    active = index;
    tabs.forEach((item, itemIndex) => {
      const selected = itemIndex === index;
      item.setAttribute("aria-selected", String(selected));
      item.tabIndex = selected ? 0 : -1;
      item.classList.toggle("is-active", selected);
    });
    panels.forEach((panel, itemIndex) => {
      const selected = itemIndex === index;
      panel.hidden = !selected;
      panel.inert = !selected;
      panel.classList.toggle("is-active-slide", selected);
      if (selected) panel.removeAttribute("aria-hidden");
      else panel.setAttribute("aria-hidden", "true");
    });
    const name = Array.from(tabs[index].childNodes).filter(node => node.nodeType === 3).map(node => node.textContent).join(" ").trim();
    counter.textContent = `${String(index + 1).padStart(2, "0")} / ${String(tabs.length).padStart(2, "0")} · ${name}`;
    controls.style.setProperty("--path-progress", (index + 1) / tabs.length);
    viewport.dataset.currentSlide = String(index + 1);
    updateIndicator();
    if (options.hash && window.location.hash !== tabs[index].hash) {
      window.history.replaceState(window.history.state, "", tabs[index].hash);
    }
    if (oldIndex < 0 || preference.matches || typeof incoming.animate !== "function") return;

    const direction = options.direction || (index > oldIndex ? 1 : -1);
    // The outgoing slide remains visible for its exit, but is already absent
    // from the accessibility tree and cannot receive keyboard focus.
    outgoing.hidden = false;
    outgoing.classList.add("is-exiting-slide");
    viewport.style.height = `${fromHeight}px`;
    viewport.classList.add("is-transitioning");
    const toHeight = incoming.getBoundingClientRect().height;
    const duration = 520;
    const easing = "cubic-bezier(.22, 1, .36, 1)";
    const leaving = outgoing.animate([
      { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
      { opacity: 0, transform: `translate3d(${-direction * 52}px,0,0) scale(.985)` }
    ], { duration: 360, easing: "cubic-bezier(.4, 0, .2, 1)", fill: "both" });
    const arriving = incoming.animate([
      { opacity: 0, transform: `translate3d(${direction * 68}px,7px,0) scale(.985)` },
      { opacity: 1, transform: "translate3d(0,0,0) scale(1)" }
    ], { duration, easing, fill: "both" });
    const resizing = viewport.animate([
      { height: `${fromHeight}px` }, { height: `${toHeight}px` }
    ], { duration, easing, fill: "both" });
    animations = [leaving, arriving, resizing];
    Promise.allSettled(animations.map(animation => animation.finished)).then(() => {
      if (token === revision) settle();
    });
  }

  tabList.setAttribute("role", "tablist");
  tabs.forEach((tab, index) => {
    const panel = panels[index];
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", panel.id);
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", tab.id);
    panel.tabIndex = 0;
    tab.addEventListener("click", event => {
      event.preventDefault();
      activate(index, { hash: true });
    });
    tab.addEventListener("keydown", event => {
      let next;
      let direction;
      if (event.key === "ArrowRight") { next = index + 1; direction = 1; }
      if (event.key === "ArrowLeft") { next = index - 1; direction = -1; }
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      if (next !== undefined) {
        event.preventDefault();
        activate(next, { focus: true, hash: true, direction });
      }
      if (event.key === " ") {
        event.preventDefault();
        activate(index, { hash: true });
      }
    });
  });
  controls.querySelector(".path-slide-previous").addEventListener("click", () => activate(active - 1, { hash: true, direction: -1 }));
  controls.querySelector(".path-slide-next").addEventListener("click", () => activate(active + 1, { hash: true, direction: 1 }));
  viewport.addEventListener("pointerdown", event => {
    if (event.pointerType !== "touch") return;
    if (!event.isPrimary) { swipe = null; return; }
    if (event.target.closest("a, button, input, textarea, select, summary")) return;
    swipe = { id: event.pointerId, x: event.clientX, y: event.clientY, time: performance.now() };
  }, { passive: true });
  viewport.addEventListener("pointermove", event => {
    if (!swipe || event.pointerId !== swipe.id) return;
    const x = Math.abs(event.clientX - swipe.x);
    const y = Math.abs(event.clientY - swipe.y);
    if (y > 14 && y > x) swipe = null;
  }, { passive: true });
  window.addEventListener("pointerup", event => {
    if (!swipe || event.pointerId !== swipe.id) return;
    const gesture = swipe;
    swipe = null;
    const x = event.clientX - gesture.x;
    const y = event.clientY - gesture.y;
    if (Math.abs(x) < 52 || Math.abs(x) < Math.abs(y) * 1.35 || performance.now() - gesture.time > 900) return;
    const direction = x < 0 ? 1 : -1;
    activate(active + direction, { hash: true, direction });
  }, { passive: true });
  window.addEventListener("pointercancel", () => { swipe = null; }, { passive: true });
  window.addEventListener("resize", () => { ++revision; settle(); updateIndicator(); }, { passive: true });
  preference.addEventListener("change", () => { ++revision; settle(); });
  document.documentElement.classList.add("js");
  const initial = tabs.findIndex(tab => tab.hash === window.location.hash);
  activate(initial < 0 ? 0 : initial);
  window.addEventListener("hashchange", () => {
    const matching = tabs.findIndex(tab => tab.hash === window.location.hash);
    if (matching >= 0) activate(matching);
  });
})();

// The studio is an independent enhancement: navigation works if it cannot mount.
(() => {
  const hero = document.querySelector(".hero-art");
  const stage = hero?.querySelector(".avatar-stage");
  const canvas = hero?.querySelector(".avatar-build-canvas");
  const fallback = hero?.querySelector(".hero-logo");
  const controls = hero?.querySelector(".avatar-controls");
  const replay = hero?.querySelector(".avatar-replay");
  const pause = hero?.querySelector(".avatar-pause");
  const status = hero?.querySelector(".avatar-build-status");
  if (!stage || !canvas || !fallback || !controls || !replay || !pause ||
      !window.FunAvatarConstruction || !window.FunAvatarLife) return;

  const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
  let reduced = preference.matches;
  let inView = false;
  let userPaused = false;
  let built = false;
  let building = false;
  let disposed = false;
  let failed = false;
  let construction;
  let life;
  let observer;
  const canMove = () => !disposed && !failed && !reduced && !userPaused && inView && !document.hidden;
  const labels = { vertices: "01 / VERTICI", mesh: "02 / WIREFRAME", material: "03 / MATERIALI", complete: "04 / È VIVO" };

  function updateControls() {
    replay.disabled = reduced || failed;
    pause.disabled = reduced || failed;
    pause.setAttribute("aria-pressed", String(userPaused || reduced));
    pause.setAttribute("aria-label", userPaused ? "Riprendi le animazioni" : "Metti in pausa le animazioni");
    pause.querySelector("use").setAttribute("href", "./assets/icons.svg#" + (userPaused ? "play" : "pause"));
    pause.querySelector(".control-label").textContent = userPaused ? "Riprendi" : "Pausa";
    if (reduced && status) status.textContent = "MOVIMENTO RIDOTTO";
  }

  function staticFallback() {
    failed = true;
    building = false;
    construction?.stop();
    life?.pause();
    stage.classList.remove("avatar-has-life", "avatar-is-building", "avatar-is-complete", "avatar-is-living");
    hero.dataset.avatarState = "static";
    controls.hidden = true;
    stage.hidden = true;
    if (status) status.textContent = "IDENTITÀ IN MOVIMENTO";
  }

  function finish(result = {}) {
    if (disposed) return;
    if (result.fallback) return staticFallback();
    building = false;
    built = true;
    stage.classList.remove("avatar-is-building");
    stage.classList.add("avatar-is-complete", "avatar-is-living");
    hero.dataset.avatarState = reduced ? "reduced" : "alive";
    if (status) status.textContent = reduced ? "MOVIMENTO RIDOTTO" : labels.complete;
    life.complete();
    if (canMove()) life.resume(); else life.pause();
    updateControls();
  }

  function startBuild() {
    if (building || !canMove()) return;
    building = true;
    life.pause();
    stage.classList.remove("avatar-is-complete", "avatar-is-living");
    hero.dataset.avatarState = "building";
    try {
      const pending = construction.play();
      if (pending && typeof pending.catch === "function") pending.catch(staticFallback);
    } catch { staticFallback(); }
  }

  function sync() {
    if (disposed || failed) return;
    if (reduced) {
      construction.stop();
      building = false;
      life.setReducedMotion(true);
      if (!built) finish();
      hero.dataset.avatarState = "reduced";
      life.pause();
      updateControls();
      return;
    }
    life.setReducedMotion(false);
    if (!canMove()) {
      if (building) { construction.stop(); building = false; }
      life.pause();
      hero.dataset.avatarState = userPaused ? "paused" : built ? "resting" : "waiting";
      if (userPaused && status) status.textContent = "IN PAUSA";
    } else if (built) {
      hero.dataset.avatarState = "alive";
      if (status) status.textContent = labels.complete;
      life.resume();
    } else startBuild();
    updateControls();
  }

  function togglePause() { userPaused = !userPaused; sync(); }
  function replayBuild() {
    if (reduced || failed) return;
    userPaused = false;
    built = false;
    building = false;
    construction.stop();
    life.pause();
    sync();
  }
  function changePreference(event) { reduced = event.matches; sync(); }
  function pageShow() { sync(); }
  function pageHide(event) {
    construction.stop();
    building = false;
    life.pause();
    if (event.persisted) return;
    disposed = true;
    observer?.disconnect();
    life.destroy();
    construction.destroy();
    document.removeEventListener("visibilitychange", sync);
    window.removeEventListener("pageshow", pageShow);
    window.removeEventListener("pagehide", pageHide);
    preference.removeEventListener?.("change", changePreference);
  }

  try {
    life = window.FunAvatarLife.mount(stage, { imageSrc: fallback.currentSrc || fallback.src });
    construction = window.FunAvatarConstruction.mount(canvas, {
      imageSrc: fallback.currentSrc || fallback.src,
      onComplete: finish,
      onStage(name) {
        if (disposed || reduced || failed) return;
        stage.classList.add("avatar-has-life", "avatar-is-building");
        stage.classList.remove("avatar-is-complete", "avatar-is-living");
        hero.dataset.avatarPhase = name;
        if (status && labels[name]) status.textContent = labels[name];
      }
    });
    stage.classList.add("avatar-has-life");
    controls.hidden = false;
    replay.addEventListener("click", replayBuild);
    pause.addEventListener("click", togglePause);
    preference.addEventListener?.("change", changePreference);
    document.addEventListener("visibilitychange", sync);
    window.addEventListener("pageshow", pageShow);
    window.addEventListener("pagehide", pageHide);
    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver(entries => { inView = entries[0].isIntersecting; sync(); }, { threshold: 0.08 });
      observer.observe(hero);
    } else { inView = true; sync(); }
    updateControls();
  } catch { staticFallback(); }
})();
