"use strict";
const intakeFields = {
  facility: "Instalación",
  category: "Categoría",
  quantity: "Cantidad",
  unit: "Unidad",
  start: "Inicio",
  end: "Fin",
  supplier: "Proveedor",
  reference: "Referencia",
  note: "Notas",
  document: "Documento PDF",
};

function startImportWizard() {
  if (!S.facilities.some((f) => !f.archived)) {
    toast("Crea una instalación activa antes de importar.");
    location.hash = "instalaciones";
    return;
  }
  modal(
    "Importar consumos",
    "Excel y CSV, con revisión antes de guardar.",
    `${notice("Importa actividades de los tres alcances. En las nuevas categorías añade notas que identifiquen la actividad y selecciona el factor específico desde Revisar después de importar.")}<ol><li>Elige un archivo y una hoja.</li><li>Relaciona sus columnas con los campos de ALgyre.</li><li>Corrige las filas, revisa los avisos y confirma.</li></ol><p class="muted">Hasta 500 filas. Excel .xlsx de hasta 5 MB o CSV UTF-8 de hasta 2 MB. Fechas AAAA-MM-DD o DD/MM/AAAA. La primera fila debe contener las cabeceras.</p><div class="actions"><a class="btn" href="/api/template.xlsx">Plantilla Excel de ALgyre</a><a class="btn" href="/api/template.csv">Plantilla CSV</a><button type="button" id="choose-intake" class="btn primary">Elegir archivo</button></div>`,
    null,
  );
  $("#choose-intake").onclick = () =>
    pickFile(".xlsx,.csv", async (file) => {
      if (file.size > (file.name.toLowerCase().endsWith(".csv") ? 2_000_000 : 5_000_000))
        throw new Error("El archivo supera el límite permitido.");
      const payload = { name: file.name, content: await b64(file) };
      toast("Leyendo las columnas del archivo…");
      const parsed = await api("import/inspect", payload);
      intakeMapping(payload, parsed);
    });
}

function intakeMapping(payload, parsed, previous = {}) {
  const mapping = previous.mapping || parsed.mapping,
    defaults = previous.defaults || {};
  modal(
    "Relacionar columnas",
    `${payload.name} · ${parsed.count} filas · Paso 1 de 2`,
    `<form id="intake-map" class="stack"><div class="fields">${select(
      "Hoja de Excel",
      "sheet",
      parsed.sheets.map((s) => [s, s]),
      parsed.sheet,
    )}<div class="actions"><button id="load-sheet" class="btn" type="button">Leer esta hoja</button></div></div><div class="table-wrap"><table><caption>Primeras filas del archivo</caption><thead><tr>${parsed.headers.map((h) => `<th>${E(h)}</th>`).join("")}</tr></thead><tbody>${parsed.sample.map((r) => `<tr>${r.cells.map((c) => `<td>${E(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div><div class="fields">${Object.entries(
      intakeFields,
    )
      .map(([key, label]) =>
        select(
          label + (["quantity", "start", "end"].includes(key) ? " · obligatoria" : ""),
          "map_" + key,
          [["", "Sin columna"], ...parsed.headers.map((h, i) => [String(i), h])],
          mapping[key],
        ),
      )
      .join(
        "",
      )}</div><fieldset><legend>Valores para campos sin columna</legend><div class="fields">${select("Instalación común", "default_facility", [["", "Elegir si no hay columna"], ...S.facilities.filter((f) => !f.archived).map((f) => [f.name, f.name])], defaults.facility)}${select("Categoría común", "default_category", [["", "Elegir si no hay columna"], ...Object.entries(cats)], defaults.category)}${select("Unidad común", "default_unit", [["", "Elegir si no hay columna"], ...Object.entries(unitLabels)], defaults.unit)}</div><p class="field-help">Si hay una columna, se utilizará su valor en cada fila. En electricidad, una unidad ausente se propone como kWh y se muestra un aviso. Fechas con barras se interpretan como día/mes/año.</p></fieldset><div class="error" role="alert"></div><div class="form-actions"><button type="submit" class="btn primary">Validar filas</button></div></form>`,
    null,
  );
  $("#load-sheet").onclick = async (e) => {
    e.preventDefault();
    const b = e.currentTarget;
    b.disabled = true;
    try {
      intakeMapping(
        payload,
        await api("import/inspect", {
          ...payload,
          sheet: $("#intake-map [name=sheet]").value,
        }),
      );
    } catch (err) {
      $("#intake-map .error").textContent = err.message;
    } finally {
      b.disabled = false;
    }
  };
  $("#intake-map").onsubmit = async (e) => {
    e.preventDefault();
    await submit(e.currentTarget, async (data) => {
      if (data.sheet !== parsed.sheet)
        throw new Error("Pulsa «Leer esta hoja» para cargar la hoja elegida.");
      const config = {
        token: parsed.token,
        mapping: Object.fromEntries(Object.keys(intakeFields).map((k) => [k, data["map_" + k]])),
        defaults: {
          facility: data.default_facility,
          category: data.default_category,
          unit: data.default_unit,
        },
        edits: {},
      };
      intakePreview(payload, parsed, config, await api("import/validate", config));
    });
  };
}

function intakePreview(payload, parsed, config, result) {
  const warnings = result.rows.filter((r) => r.warnings.length).length;
  modal(
    "Revisar antes de incorporar",
    `${payload.name} · Paso 2 de 2`,
    `<form id="intake-review" class="stack"><div class="actions">${badge(`${result.count} válidas`, "success")}${badge(`${result.errors} con errores`, result.errors ? "danger" : "success")}${badge(`${warnings} con avisos`, warnings ? "warning" : "success")}</div>${result.ignored.length ? notice("Columnas que no se guardarán: " + result.ignored.join(", ") + ". Comprueba que no contienen información necesaria para interpretar el consumo.", true) : ""}<p class="muted">No se ha guardado ningún consumo. Puedes corregir una fila aquí y volver a validarla. Si cambia el archivo de origen, vuelve a seleccionarlo.</p><div class="intake-rows">${result.rows
      .map(
        (row) =>
          `<details class="intake-row" ${row.error ? "open" : ""}><summary><strong>Fila ${row.line} · ${E(row.values.facility || "Sin instalación")}</strong><span>${E(row.values.quantity || "—")} ${E(row.values.unit || "")} · ${E(row.values.start || "—")} → ${E(row.values.end || "—")}</span>${badge(row.error ? "Corregir" : row.warnings.length ? "Revisar avisos" : "Válida", row.error ? "danger" : row.warnings.length ? "warning" : "success")}</summary>${row.error ? `<p class="error" role="alert">${E(row.error)}</p>` : ""}${row.warnings.length ? `<ul class="muted">${row.warnings.map((w) => `<li>${E(w)}</li>`).join("")}</ul>` : ""}<div class="fields">${Object.entries(
            intakeFields,
          )
            .map(([key, label]) =>
              field(
                label,
                `${row.line}:${key}`,
                row.values[key] || "",
                "text",
                `data-line="${row.line}" data-key="${key}" maxlength="${key === "note" ? 2000 : 160}"`,
              ),
            )
            .join("")}</div></details>`,
      )
      .join(
        "",
      )}</div><p id="intake-dirty" class="muted" role="status"></p><label class="check-label"><input type="checkbox" id="intake-reviewed" required>He revisado cantidades, unidades, periodos, avisos y columnas descartadas. Quiero guardar estas filas.</label><div class="error" role="alert"></div><div class="form-actions"><button type="button" id="intake-back" class="btn">Revisar columnas</button><button type="button" id="intake-revalidate" class="btn">Volver a validar</button><button type="submit" id="intake-confirm" class="btn primary" ${result.errors ? "disabled" : ""}>Guardar ${result.count} consumos</button></div></form>`,
    null,
  );
  const form = $("#intake-review");
  let dirty = false,
    busy = false;
  form.addEventListener("input", (e) => {
    if (e.target.dataset.line) {
      dirty = true;
      $("#intake-confirm").disabled = true;
      $("#intake-reviewed").checked = false;
      $("#intake-dirty").textContent = "Hay cambios sin validar. Pulsa «Volver a validar».";
    }
  });
  $("#intake-back").onclick = () => intakeMapping(payload, parsed, config);
  $("#intake-revalidate").onclick = async () => {
    if (busy) return;
    busy = true;
    $("#intake-revalidate").disabled = true;
    $("#intake-confirm").disabled = true;
    const edits = {};
    $$("[data-line]", form).forEach((input) => {
      (edits[input.dataset.line] ??= {})[input.dataset.key] = input.value;
    });
    try {
      const next = { ...config, edits };
      intakePreview(payload, parsed, next, await api("import/validate", next));
    } catch (e) {
      $(".error", form).textContent = e.message;
    } finally {
      busy = false;
      const b = $("#intake-revalidate");
      if (b) b.disabled = false;
    }
  };
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (busy || dirty || result.errors) return;
    busy = true;
    $("#intake-confirm").disabled = true;
    try {
      const saved = await api("import/confirm", {
        token: result.token,
        reviewed: $("#intake-reviewed").checked,
      });
      if (saved.years.length === 1) year = saved.years[0];
      $("#modal").close();
      location.hash = "consumos";
      await refresh();
      toast(
        `${saved.count} consumos incorporados. El lote y las filas de origen constan en su historial.`,
      );
    } catch (err) {
      $(".error", form).textContent = err.message;
      $("#intake-confirm").disabled = false;
    } finally {
      busy = false;
    }
  };
}

async function consumptionHistory(id) {
  const data = await api("consumptions/" + encodeURIComponent(id) + "/history");
  const origin = data.imports
    .map((v) => {
      const s = JSON.parse(v.after_json);
      return `<div class="dialog-note"><strong>Archivo de origen: ${E(s.name)}</strong><p>Hoja: ${E(s.sheet)} · Fila: ${E(s.lines[s.record_ids.indexOf(id)])}</p><p class="definition">SHA-256: ${E(s.sha256)}</p><p class="field-help">La huella identifica el archivo leído; las correcciones posteriores se conservan en este historial. El archivo de importación no sustituye a la evidencia PDF.</p></div>`;
    })
    .join("");
  modal(
    "Origen e historial del consumo",
    `Referencia: ${data.record.reference || "Sin referencia"} · Revisión ${data.record.revision}`,
    `${origin}${data.record.document_id ? `<p><a class="btn" href="/api/documents/${encodeURIComponent(data.record.document_id)}/file">Descargar PDF vinculado</a></p>` : notice("Este consumo no tiene un PDF vinculado. Puedes adjuntarlo desde «Revisar».", true)}${data.events.map((ev) => `<section class="history-entry"><h3>${ev.action === "corrected" ? "Corrección" : "Alta del consumo"}</h3><p class="muted">${new Date(ev.created_at).toLocaleString("es-ES")}</p><p>${E(ev.reason || "Entrada manual")}</p><details><summary>Ver los valores guardados</summary><pre class="definition">${E(JSON.stringify(JSON.parse(ev.after_json), null, 2))}</pre></details>${ev.before_json !== "null" ? `<details><summary>Ver los valores anteriores</summary><pre class="definition">${E(JSON.stringify(JSON.parse(ev.before_json), null, 2))}</pre></details>` : ""}</section>`).join("") || "<p>Sin eventos disponibles para este registro.</p>"}`,
    null,
  );
}

views.calidad = () => {
  const pending = S.records.filter((r) => r.kg_co2e === null),
    unlinked = S.records.filter((r) => !r.document_id),
    unreviewed = S.documents.filter((d) => !d.linked);
  return (
    head("Calidad de tus datos", "Resuelve pendientes antes de utilizar los resultados.") +
    `<div class="metrics"><section class="metric"><h2>Sin cálculo</h2><div class="metric-value">${pending.length}</div><p class="muted">Consumos sin un factor único compatible.</p></section><section class="metric"><h2>Sin evidencia PDF</h2><div class="metric-value">${unlinked.length}</div><p class="muted">Registros que conviene respaldar.</p></section><section class="metric"><h2>Documentos por revisar</h2><div class="metric-value">${unreviewed.length}</div><p class="muted">PDF sin consumos vinculados; todos los ejercicios.</p></section></div><section class="panel"><div class="panel-head"><div><h2>Consumos por completar · ${year}</h2><p>Los avisos no sustituyen la revisión de tu perímetro.</p></div>${btn("Ver huecos del año", "coverage", "")}</div>${
      S.records
        .filter((r) => r.kg_co2e === null || !r.document_id)
        .map(
          (r) =>
            `<div class="list-row"><div><h3>${E(r.facility_name)} · ${E(r.reference || cats[r.category])}</h3><p>${E(r.start)} → ${E(r.end)}</p><p>${E([r.kg_co2e === null ? r.pending_reason : "", !r.document_id ? "Sin PDF vinculado" : ""].filter(Boolean).join(" · "))}</p></div><div class="actions"><button class="ghost" data-action="history-record" data-id="${E(r.id)}">Historial</button><button class="btn" data-action="edit-record" data-id="${E(r.id)}">Revisar</button></div></div>`,
        )
        .join("") ||
      '<p class="muted">No hay avisos de cálculo o evidencia para los consumos registrados en este ejercicio.</p>'
    }</section><section class="panel quality-docs"><h2>Documentos sin revisar</h2>${unreviewed.map((d) => `<div class="list-row"><h3>${E(d.name)}</h3><button class="btn" data-action="review-doc" data-id="${E(d.id)}">Vincular consumo</button></div>`).join("") || '<p class="muted">Todos los documentos tienen al menos un consumo vinculado.</p>'}</section>`
  );
};
