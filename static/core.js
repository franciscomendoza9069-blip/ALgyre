// Shared state, UI primitives and HTTP client. Loaded first.
"use strict";
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const E = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
const fmt = (n, d = 1) =>
  new Intl.NumberFormat("es-ES", {
    maximumFractionDigits: d,
    minimumFractionDigits: d,
  }).format(Number(n));
let cats = {},
  activityCatalog = {},
  unitLabels = {};
const months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
const paths = {
  home: "M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z",
  document: "M14 2H5v20h14V7ZM14 2v6h5M8 12h8M8 16h6",
  chart: "M4 3v17h17M8 16v-4m5 4V8m5 8V4",
  building: "M4 21V3h12v18M16 10h4v11M8 7h4M8 11h4M8 15h4M9 21v-3h3v3",
  factor: "M4 7h16M4 17h16M8 3v8m8 2v8",
  report: "M4 3h16v18H4ZM8 7h8M8 11h8M8 15h5",
  settings: "M4 7h16M4 17h16M8 3v8m8 2v8",
  plus: "M12 5v14M5 12h14",
  upload: "M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6",
  check: "m5 12 4 4L20 5",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  shield: "m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6Z",
  logout: "M9 3H4v18h5m5-14 5 5-5 5M8 12h12",
  info: "M12 11v6m0-10v1M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  download: "M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4",
};
const icon = (n) =>
  `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[n] || paths.info}"/></svg>`;
const logo = `<svg viewBox="0 0 40 40" fill="none" aria-hidden="true"><path d="M4 32 17 7h6l13 25h-8l-3-6H15l-3 6H4Zm14-12h4l-2-5-2 5Z" fill="currentColor"/></svg>`;
const btn = (label, action, type = "primary", extra = "") =>
  `<button class="btn ${type}" data-action="${action}" ${extra}>${E(label)}</button>`;
const badge = (label, type = "") => `<span class="badge ${type}">${E(label)}</span>`;
const empty = (title, desc, label = "", action = "record") =>
  `<div class="empty">${icon("document")}<h3>${E(title)}</h3><p>${E(desc)}</p>${label ? btn(label, action) : ""}</div>`;
const notice = (t, warning = false) =>
  `<div class="notice ${warning ? "warning" : ""}">${icon("info")}<p>${E(t)}</p></div>`;
let S = null,
  csrf = "",
  year = 2026,
  current = "resumen",
  filterFacility = "",
  uploadBusy = false;
const routes = [
  ["resumen", "Resumen", "chart"],
  ["consumos", "Consumos", "document"],
  ["documentos", "Documentos", "upload"],
  ["calidad", "Calidad de datos", "shield"],
  ["instalaciones", "Instalaciones", "building"],
  ["factores", "Factores", "factor"],
  ["informes", "Informes", "report"],
  ["configuracion", "Configuración", "settings"],
];
async function api(path, data) {
  const r = await fetch("/api/" + path, {
    method: data ? "POST" : "GET",
    headers: data ? { "Content-Type": "application/json", "X-CSRF-Token": csrf } : {},
    body: data ? JSON.stringify(data) : undefined,
  });
  const result = await r.json();
  if (!r.ok) {
    if (r.status === 401 && !path.startsWith("login")) {
      await init();
    }
    throw new Error(result.error || "No se pudo completar la operación.");
  }
  return result;
}
function toast(t) {
  const el = $("#toast");
  el.textContent = t;
  el.classList.add("visible");
  setTimeout(() => el.classList.remove("visible"), 5000);
}
