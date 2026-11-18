"use strict";

// Forms and file interactions. No data is saved without review.
function dataForm(form) {
  const d = Object.fromEntries(new FormData(form));
  $$("input[type=checkbox]", form).forEach((i) => (d[i.name] = i.checked));
  return d;
}
async function submit(form, fn) {
  const err = $(".error", form);
  if (err) err.textContent = "";
  const b = $("button[type=submit]", form);
  if (b) b.disabled = true;
  try {
    await fn(dataForm(form));
  } catch (e) {
    if (err) err.textContent = e.message;
    else toast(e.message);
  } finally {
    if (b) b.disabled = false;
  }
}
function modal(title, desc, body, onSave, label = "Guardar") {
  $("#modal-body").innerHTML =
    `<div class="modal-head"><div><h2 id="modal-title">${E(title)}</h2><p class="muted">${E(desc)}</p></div><button class="close" data-action="close" aria-label="Cerrar">×</button></div>${onSave ? '<form id="edit-form">' : ""}${body}${onSave ? `<div class="error" role="alert"></div><div class="form-actions"><button type="button" class="btn" data-action="close">Cancelar</button><button type="submit" class="btn primary">${E(label)}</button></div></form>` : ""}`;
  if (!$("#modal").open) $("#modal").showModal();
  if (onSave)
    $("#edit-form").onsubmit = (e) => {
      e.preventDefault();
      submit(e.currentTarget, async (d) => {
        await onSave(d, e.currentTarget);
        $("#modal").close();
        await refresh();
        toast("Guardado correctamente");
      });
    };
}
function field(label, name, value = "", type = "text", extra = "") {
  return `<label>${E(label)}<input type="${type}" name="${name}" value="${E(value)}" ${extra}></label>`;
}
function select(label, name, options, value = "") {
  return `<label>${E(label)}<select name="${name}">${options.map(([k, v]) => `<option value="${E(k)}" ${k === String(value) ? "selected" : ""}>${E(v)}</option>`).join("")}</select></label>`;
}
function facilityModal(id) {
  const f = S.facilities.find((v) => v.id === id) || {
    country: S.company.country || "",
    categories: '["electricity"]',
    ownership: "rented",
  };
  modal(
    id ? "Editar instalación" : "Nueva instalación",
    "Activa las fuentes cuyos consumos vas a registrar.",
    `<div class="fields">${field("Nombre", "name", f.name, "text", 'required maxlength="160"')}${field("País ISO", "country", f.country, "text", 'required minlength="2" maxlength="2"')}${select(
      "Titularidad",
      "ownership",
      [
        ["rented", "En alquiler"],
        ["owned", "En propiedad"],
      ],
      f.ownership,
    )}<fieldset class="full"><legend>Fuentes esperadas durante el año</legend>${Object.entries(cats)
      .map(
        ([k, v]) =>
          `<label class="check-label"><input type="checkbox" name="cat_${k}" ${JSON.parse(f.categories).includes(k) ? "checked" : ""}>${v}</label>`,
      )
      .join(
        "",
      )}</fieldset>${id ? `<label class="check-label full"><input type="checkbox" name="archived" ${f.archived ? "checked" : ""}>Archivar instalación. Conserva su histórico.</label>` : ""}</div>`,
    async (d) => {
      d.categories = Object.keys(cats).filter((k) => d["cat_" + k]);
      await api("facilities" + (id ? "/" + id : ""), d);
    },
  );
}
function recordModal(id, docId) {
  const old = S.records.find((v) => v.id === id);
  const doc = S.documents.find((v) => v.id === docId);
  const ex = doc?.extracted || {};
  if (!S.facilities.length) {
    toast("Crea una instalación antes de añadir consumos.");
    location.hash = "instalaciones";
    return;
  }
  const r = old || {
    facility_id: S.facilities.find((f) => !f.archived)?.id,
    category: "electricity",
    unit: ex.unit || "kWh",
    quantity: ex.quantity || "",
    start: ex.start || `${year}-01-01`,
    end: ex.end || `${year}-01-31`,
    ...ex,
  };
  modal(
    id ? "Revisar consumo" : "Añadir consumo",
    id
      ? "Los cambios conservan la revisión anterior."
      : "Confirma los valores antes de incorporarlos al cálculo.",
    `${doc ? `<div class="dialog-note"><strong>${E(doc.name)}</strong><p>${E(ex.message)}</p><a href="/api/documents/${doc.id}/file" target="_blank">Abrir factura original</a></div>` : ""}<div class="fields">${select(
      "Instalación",
      "facility_id",
      S.facilities.filter((f) => !f.archived || f.id === r.facility_id).map((f) => [f.id, f.name]),
      r.facility_id,
    )}${select("Tipo de consumo", "category", Object.entries(cats), r.category)}${field("Cantidad", "quantity", r.quantity, "text", 'required inputmode="decimal" maxlength="40"')}${select("Unidad", "unit", Object.entries(unitLabels), r.unit)}${field("Inicio del periodo", "start", r.start, "date", "required")}${field("Fin del periodo", "end", r.end, "date", "required")}${field("Proveedor", "supplier", r.supplier, "text", 'maxlength="160"')}${field("Referencia de factura", "reference", r.reference, "text", 'maxlength="160"')}<label class="full">Documento de origen<select name="document_id"><option value="">Entrada manual, sin documento</option>${S.documents.map((d) => `<option value="${d.id}" ${(docId || r.document_id) === d.id ? "selected" : ""}>${E(d.name)}</option>`).join("")}</select></label><label class="full">Factor de emisión<select name="factor_id"><option value="">Automático si existe una única coincidencia</option>${S.factors.map((f) => `<option value="${f.id}" ${r.factor_id === f.id ? "selected" : ""}>${E(cats[f.category])} · ${E(f.name)} · ${E(f.country)} ${f.year} · ${E(f.value)} / ${E(f.unit)} · ${E(f.version)}</option>`).join("")}</select><span class="field-help">Se exige país, año, actividad y unidad compatibles. En refrigerantes y nuevas actividades debes seleccionar el factor específico; sin él, el registro queda pendiente.</span></label><label class="full">Notas y supuestos<textarea name="note" maxlength="2000">${E(r.note)}</textarea></label>${id ? field("Motivo de la corrección", "reason", "", "text", 'required maxlength="500"') : ""}<label class="check-label full"><input type="checkbox" name="estimated" ${r.estimated ? "checked" : ""}>Este consumo es estimado; he explicado el supuesto en las notas.</label><label class="check-label full"><input type="checkbox" name="allow_overlap">He revisado los periodos solapados y explicado su motivo en las notas.</label><label class="check-label full"><input type="checkbox" name="reviewed" required>He comprobado cantidad, unidad, fechas y origen del dato.</label></div>`,
    async (d) => {
      d.revision = old?.revision;
      await api("consumptions" + (id ? "/" + id : ""), d);
      year = Number(d.start.slice(0, 4));
    },
  );
  bindActivityFields(false);
}
function factorModal() {
  modal(
    "Añadir un factor",
    "Guarda una versión documentada. Los factores anteriores se conservan.",
    `<div class="fields">${field("Nombre descriptivo", "name", "", "text", 'required maxlength="160"')}${select("Actividad", "category", Object.entries(cats), "electricity")}${field("País ISO", "country", S.company.country, "text", 'required minlength="2" maxlength="2"')}${field("Año de aplicación", "year", year, "number", 'required min="2000" max="2100"')}${field("kg CO₂e por unidad", "value", "", "text", 'required inputmode="decimal"')}${select(
      "Unidad de actividad",
      "unit",
      Object.entries(unitLabels).filter(([key]) => !["MWh", "t"].includes(key)),
      "kWh",
    )}${field("Versión o edición de la fuente", "version", "", "text", 'required maxlength="100"')}${field("Licencia o condiciones de uso", "license", "", "text", 'required maxlength="300"')}<label class="full">URL de la fuente<input name="source" type="url" placeholder="https://…" required maxlength="1000"></label><div class="dialog-note full">Electricidad: factor territorial de generación. Combustibles: combustión directa. Para otras actividades, describe en el nombre el producto, gas, modo de transporte o tratamiento y comprueba los límites de la fuente. No mezcles factores de ciclo de vida con combustión directa.</div><label class="check-label full"><input name="validated" type="checkbox" required>He comprobado el valor, su unidad, los límites metodológicos y las condiciones de uso.</label></div>`,
    async (d) => api("factors", d),
  );
  bindActivityFields(true);
}
function pickFile(accept, fn) {
  const el = document.createElement("input");
  el.type = "file";
  el.accept = accept;
  el.onchange = async () => {
    if (el.files[0]) {
      try {
        await fn(el.files[0]);
      } catch (e) {
        toast(e.message);
      }
    }
  };
  el.click();
}
function b64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",")[1]);
    r.onerror = () => reject(new Error("No se pudo leer el archivo."));
    r.readAsDataURL(file);
  });
}
async function uploadFile(file) {
  if (uploadBusy) return;
  if (file.size > 15 * 1024 * 1024) throw new Error("El PDF debe ocupar menos de 15 MB.");
  uploadBusy = true;
  toast("Leyendo el documento…");
  try {
    const r = await api("documents", {
      name: file.name,
      content: await b64(file),
    });
    await refresh();
    recordModal(null, r.id);
  } finally {
    uploadBusy = false;
  }
}
function importCSV() {
  pickFile(".csv,text/csv", async (file) => {
    if (file.size > 2_000_000) throw new Error("El CSV debe ocupar menos de 2 MB.");
    const result = await api("import/preview", { text: await file.text() });
    modal(
      "Revisar importación",
      "No se incorporará ninguna fila hasta confirmar. Corrige los errores en el archivo y vuelve a cargarlo.",
      `<div class="table-wrap"><table><thead><tr><th>Fila</th><th>Instalación</th><th>Cantidad</th><th>Revisión</th></tr></thead><tbody>${result.rows.map((r) => `<tr><td>${r.line}</td><td>${E(r.facility)}</td><td>${E(r.quantity)}</td><td>${r.error ? E(r.error) : badge("Válida", "success")}</td></tr>`).join("")}</tbody></table></div><p class="muted">${result.count} filas válidas de ${result.rows.length}. La importación exige que todas sean válidas.</p><label class="check-label"><input type="checkbox" name="reviewed" required>He revisado las filas y sus periodos.</label>`,
      async (d) => {
        await api("import/confirm", {
          token: result.token,
          reviewed: d.reviewed,
        });
      },
      "Confirmar importación",
    );
  });
}
function coverageModal() {
  const su = S.summary;
  modal(
    "Revisar cobertura",
    "Meses con días sin datos en los suministros continuos declarados.",
    `${notice("Solo se revisa continuidad de combustibles y energía comprada. Viajes, residuos y otras actividades puntuales no requieren datos todos los días. Revisa su integridad con tus registros de origen.")}${
      su.pending
        ? `<h3>${su.pending} registros sin cálculo</h3><ul>${S.records
            .filter((r) => r.kg_co2e === null)
            .map(
              (r) =>
                `<li>${E(r.facility_name)} · ${E(cats[r.category])}: ${E(r.pending_reason)}</li>`,
            )
            .join("")}</ul>`
        : ""
    }<div class="gap-list">${su.gaps.length ? `<table><thead><tr><th>Instalación</th><th>Fuente</th><th>Mes</th></tr></thead><tbody>${su.gaps.map((g) => `<tr><td>${E(g.facility)}</td><td>${E(g.category)}</td><td>${months[g.month - 1]}</td></tr>`).join("")}</tbody></table>` : "<p>Sin huecos detectados en las fuentes declaradas. Comprueba que has creado todas las instalaciones y categorías necesarias.</p>"}</div>`,
    null,
  );
}

function bindActivityFields(factorMode) {
  const form = $("#edit-form"),
    category = $("[name=category]", form),
    unit = $("[name=unit]", form);
  const help = document.createElement("p");
  help.className = "field-help full";
  category.parentElement.after(help);
  const update = () => {
    const activity = activityCatalog[category.value];
    const previous = unit.value;
    const allowed = activity.units.filter((value) => !factorMode || !["MWh", "t"].includes(value));
    unit.innerHTML = allowed
      .map((value) => `<option value="${E(value)}">${E(unitLabels[value])}</option>`)
      .join("");
    if (allowed.includes(previous)) unit.value = previous;
    help.textContent = `Alcance ${activity.scope}${activity.scope3_category ? " · Categoría " + activity.scope3_category : ""}. ${activity.guidance}`;
    if (!factorMode) {
      $("[name=note]", form).required = activity.explicit_factor;
      // A blank factor is intentionally allowed: preserve activity as pending.
    }
  };
  category.addEventListener("change", update);
  update();
}
