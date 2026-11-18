"use strict";

// Single entry point after every feature file has loaded.
document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-action]");
  if (!b) return;
  e.preventDefault();
  if (b.disabled) return;
  b.disabled = true;
  try {
    await action(b.dataset.action, b.dataset.id);
  } catch (err) {
    toast(err.message);
  } finally {
    b.disabled = false;
  }
});
window.addEventListener("hashchange", () => {
  if (S) render();
});

init();
