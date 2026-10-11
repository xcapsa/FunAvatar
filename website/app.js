"use strict";

(() => {
  const tabList = document.querySelector(".path-tabs");
  if (!tabList) return;

  const tabs = Array.from(tabList.querySelectorAll("[data-tab]"));
  const panels = Array.from(document.querySelectorAll("[data-panel]"));
  if (tabs.length === 0 || tabs.length !== panels.length) return;

  const activate = (tab, moveFocus = false) => {
    tabs.forEach((item) => {
      const selected = item === tab;
      item.setAttribute("aria-selected", String(selected));
      item.tabIndex = selected ? 0 : -1;
      item.classList.toggle("is-active", selected);
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.panel !== tab.dataset.tab;
    });
    if (moveFocus) tab.focus();
  };

  tabList.setAttribute("role", "tablist");
  tabs.forEach((tab) => {
    const panel = panels.find((item) => item.dataset.panel === tab.dataset.tab);
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", panel.id);
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", tab.id);
    panel.tabIndex = 0;

    tab.addEventListener("click", (event) => {
      event.preventDefault();
      activate(tab);
    });

    tab.addEventListener("keydown", (event) => {
      const current = tabs.indexOf(tab);
      let next;
      if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
      if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      if (next !== undefined) {
        event.preventDefault();
        activate(tabs[next], true);
      }
      if (event.key === " ") {
        event.preventDefault();
        activate(tab);
      }
    });
  });

  document.documentElement.classList.add("js");
  const initialTab = tabs.find((tab) => tab.hash === window.location.hash) || tabs[0];
  activate(initialTab);

  window.addEventListener("hashchange", () => {
    const matchingTab = tabs.find((tab) => tab.hash === window.location.hash);
    if (matchingTab) activate(matchingTab);
  });
})();
