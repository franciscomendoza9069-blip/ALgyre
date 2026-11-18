// Unit tests for script composition and routing; no browser or live server.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "static/index.html"), "utf8");
const scripts = [...html.matchAll(/src="\/static\/(.+?\.js)"/g)].map((match) => match[1]);

async function appContext(status, hash = "") {
  const nodes = new Map();
  const node = (selector) => {
    if (!nodes.has(selector))
      nodes.set(selector, {
        innerHTML: "",
        textContent: "",
        value: "",
        dataset: {},
        classList: { add() {}, remove() {} },
        insertAdjacentHTML(_position, text) {
          this.innerHTML += text;
        },
        querySelector: node,
        querySelectorAll: () => [],
      });
    return nodes.get(selector);
  };
  const responses = {
    status,
    "admin/organizations": { organizations: [] },
    "state?year=2026": {
      company: { name: "Empresa de prueba", country: "ES" },
      catalog: {
        waste: { label: "Residuos", scope: 3, units: ["kg", "t"], explicit_factor: true },
      },
      units: { kg: "kg", t: "Toneladas" },
      summary: {
        total: "100",
        scope1: "0",
        scope2: "0",
        scope3: "100",
        pending: 0,
        monthly: Array(12).fill("0"),
        covered: 0,
        expected: 0,
        gaps: [],
      },
      records: [],
      facilities: [],
      factors: [],
      documents: [],
      reports: [],
      events: [],
    },
  };
  const context = vm.createContext({
    console,
    Intl,
    URL,
    setTimeout: () => 0,
    document: { querySelector: node, querySelectorAll: () => [], addEventListener() {} },
    window: { addEventListener() {} },
    location: { hash, pathname: "/" },
    history: { replaceState() {} },
    fetch: async (url) => ({ ok: true, json: async () => responses[url.replace("/api/", "")] }),
  });
  const source = scripts
    .map((name) => fs.readFileSync(path.join(root, "static", name), "utf8"))
    .join("\n");
  vm.runInContext(source, context);
  // Drain startup promises from the entry point without touching a browser.
  await new Promise((resolve) => setImmediate(resolve));
  return { context, node };
}

test("one startup entry and no reassignment of core functions", () => {
  assert.equal(scripts.at(-1), "app.js");
  assert.equal(new Set(scripts).size, scripts.length);
  for (const name of scripts) {
    const source = fs.readFileSync(path.join(root, "static", name), "utf8");
    assert.doesNotMatch(source, /\b(?:init|refresh|render|action)\s*=\s*(?:async\s+)?function/);
    new vm.Script(source, { filename: name });
  }
});

test("local startup renders local registration", async () => {
  const { node } = await appContext({ configured: false, authenticated: false });
  assert.match(node("#app").innerHTML, /Crear mi espacio/);
});

test("public setup link renders administrator setup", async () => {
  const { node } = await appContext(
    { multi: true, configured: false, authenticated: false },
    "#setup=" + "x".repeat(32),
  );
  assert.match(node("#app").innerHTML, /Crea tu cuenta de administrador/);
});

test("administrator without selected company opens administration", async () => {
  const { node } = await appContext({
    multi: true,
    authenticated: true,
    role: "admin",
    organization: null,
  });
  assert.match(node("#app").innerHTML, /Empresas de ALgyre/);
});

test("company renders scope three from server taxonomy", async () => {
  const { context, node } = await appContext({
    multi: true,
    authenticated: true,
    role: "company",
    organization: "fixture",
  });
  assert.match(node("#app").innerHTML, /Alcance 3/);
  assert.equal(vm.runInContext("cats.waste", context), "Residuos");
  assert.equal(vm.runInContext("unitLabels.t", context), "Toneladas");
});

test("recovery without email explains administrator assistance", async () => {
  const { context, node } = await appContext({
    multi: true,
    authenticated: false,
    email_confirmation: false,
  });
  await vm.runInContext("action('account-forgot')", context);
  assert.match(node("#toast").textContent, /administrador/);
});
