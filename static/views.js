"use strict";

// Ledger screens and local authentication.
function localAuthView(configured) {
  $("#app").innerHTML =
    `<div class="auth"><section class="auth-story"><div><div class="brand">${logo}ALgyre</div><h1>Tu impacto, con fundamento.</h1><p>De la factura al dato. Del dato a una decisión que puedes explicar.</p><div class="auth-art" aria-hidden="true"><span style="height:90%"></span><span style="height:70%"></span><span style="height:80%"></span><span style="height:55%"></span><span style="height:40%"></span></div></div><footer>${icon("shield")} Tus archivos y datos permanecen en este ordenador.</footer></section><section class="auth-form"><div class="auth-box"><h2>${configured ? "Abre tu espacio" : "Tu empresa, en un solo lugar"}</h2><p class="muted">${configured ? "Introduce tu contraseña para continuar." : "Crea una contraseña para proteger el espacio privado de tu empresa."}</p><form id="auth-form"><label>Contraseña<input id="password" name="password" type="password" autocomplete="${configured ? "current-password" : "new-password"}" required minlength="10" maxlength="200"></label>${!configured ? '<label>Repite la contraseña<input name="repeat" type="password" autocomplete="new-password" required minlength="10"></label>' : ""}<button type="submit" class="btn primary">${configured ? "Entrar" : "Crear mi espacio"}</button><div class="error" role="alert"></div></form><div class="auth-foot"><p class="muted small">¿Quieres conocerlo primero?</p>${btn("Explorar con datos de ejemplo", "demo", "")}<p class="privacy-note">El ejemplo utiliza una base separada. No necesitas cuentas, servicios externos ni claves de IA.</p></div></div></section></div>`;
  $("#auth-form").onsubmit = async (e) => {
    e.preventDefault();
    await submit(e.currentTarget, async (d) => {
      if (!configured && d.password !== d.repeat) throw new Error("Las contraseñas no coinciden.");
      const a = await api(configured ? "login" : "setup", d);
      csrf = a.csrf;
      await refresh();
    });
  };
}
async function refreshLedger() {
  S = await api("state?year=" + year);
  activityCatalog = S.catalog;
  cats = Object.fromEntries(
    Object.entries(activityCatalog).map(([key, value]) => [key, value.label]),
  );
  unitLabels = S.units;
  render();
}
function renderLedger() {
  current = location.hash.slice(1) || "resumen";
  if (!routes.some((r) => r[0] === current)) current = "resumen";
  $("#app").innerHTML =
    `<div class="shell"><aside class="sidebar"><div><a class="brand" href="#resumen" aria-label="ALgyre, resumen">${logo}ALgyre</a><div class="brand-sub">Tu espacio de sostenibilidad</div></div><nav aria-label="Principal">${routes.map(([r, label, i]) => `<a href="#${r}" class="nav-link ${r === current ? "active" : ""}" ${r === current ? 'aria-current="page"' : ""}>${icon(i)}${label}</a>`).join("")}</nav><div class="sidebar-bottom"><div class="local-status"><strong>${icon("shield")} Espacio local</strong>Los datos se guardan en tu equipo.</div><button class="ghost" data-action="logout">${icon("logout")} ${S.demo ? "Salir del ejemplo" : "Cerrar sesión"}</button></div></aside><div class="workarea"><header class="topbar"><div class="company-label">${E(S.company.name)}</div><div class="topbar-right"><label class="small">Ejercicio <select id="year" class="year-select" aria-label="Ejercicio">${Array.from(
      { length: 11 },
      (_, i) => 2021 + i,
    )
      .concat(year >= 2021 && year <= 2031 ? [] : [year])
      .sort((a, b) => a - b)
      .map((y) => `<option ${y === year ? "selected" : ""}>${y}</option>`)
      .join(
        "",
      )}</select></label><div class="avatar" aria-label="Espacio individual">${S.demo ? "E" : "T"}</div><button class="ghost small" data-action="logout">Salir</button></div></header>${S.demo ? `<div class="demo-bar"><span>Estás en el ejemplo. Todos los datos y factores son ficticios.</span><button data-action="logout">Abrir mi espacio</button></div>` : ""}<main id="main" class="content" tabindex="-1">${views[current]()}</main></div></div>`;
  $("#year").onchange = async (e) => {
    year = Number(e.target.value);
    try {
      await refresh();
    } catch (err) {
      toast(err.message);
    }
  };
  bindView();
}
function head(title, desc, actions = "") {
  return `<div class="page-head"><div><h1>${title}</h1><p>${desc}</p></div><div class="actions">${actions}</div></div>`;
}
function recentTable(records = S.records, all = false) {
  if (!records.length)
    return empty(
      "Tu primer dato empieza aquí",
      "Añade un consumo o sube una factura. Cuando valides un factor compatible, verás sus emisiones.",
      "Añadir consumo",
    );
  return `<div class="table-wrap"><table><thead><tr><th>Fuente / instalación</th><th>Periodo</th><th>Consumo</th><th>Emisiones</th><th>Estado</th><th><span class="small">Acciones</span></th></tr></thead><tbody>${records.map((r) => `<tr data-record="${r.id}" data-search="${E([r.facility_name, r.supplier, r.reference, cats[r.category]].join(" ").toLowerCase())}" data-facility="${r.facility_id}" data-category="${r.category}"><td><strong>${E(cats[r.category])}</strong><small>${E(r.facility_name)}</small>${r.reference ? `<small>${E(r.reference)}</small>` : ""}</td><td>${E(r.start)}<small>hasta ${E(r.end)}</small></td><td>${fmt(r.quantity, 2)} ${E(r.unit)}</td><td>${r.kg_co2e === null ? "—" : fmt(r.kg_co2e) + " <small>kg CO₂e</small>"}</td><td>${r.kg_co2e === null ? badge("Sin factor", "warning") : badge(r.estimated ? "Estimado" : "Calculado", r.estimated ? "warning" : "success")}</td><td><button class="ghost" data-action="edit-record" data-id="${E(r.id)}">Revisar</button><button class="ghost" data-action="history-record" data-id="${E(r.id)}">Historial</button></td></tr>`).join("")}</tbody></table></div>`;
}
const views = {
  resumen() {
    const su = S.summary,
      pct = su.expected ? Math.round((su.covered / su.expected) * 100) : 0,
      max = Math.max(1, ...su.monthly.map(Number));
    return (
      head(
        "Una visión clara de tu impacto",
        "Consumos y emisiones de las fuentes que has incorporado.",
        `${btn("Subir factura", "upload", "")}${btn("Añadir consumo", "record")}`,
      ) +
      (!S.demo && !S.facilities.length
        ? notice(
            "Empieza por configurar tu empresa y crear una instalación. Después podrás registrar sus consumos.",
          )
        : "") +
      `<div class="metrics scope-metrics"><section class="metric"><div class="metric-label">${icon("chart")} Emisiones calculadas</div><div class="metric-value">${fmt(Number(su.total) / 1000, 2)}<small>t CO₂e</small></div><div class="metric-note">Suma parcial de las fuentes incluidas</div></section><section class="metric"><div class="metric-label">Emisiones directas incluidas</div><div class="metric-value">${fmt(Number(su.scope1) / 1000, 2)}<small>t CO₂e</small></div><div class="metric-note">Alcance 1 · Fuentes registradas</div></section><section class="metric"><div class="metric-label">Energía comprada incluida</div><div class="metric-value">${fmt(Number(su.scope2) / 1000, 2)}<small>t CO₂e</small></div><div class="metric-note">Alcance 2 · Electricidad territorial</div></section><section class="metric"><div class="metric-label">Actividades indirectas incluidas</div><div class="metric-value">${fmt(Number(su.scope3) / 1000, 2)}<small>t CO₂e</small></div><div class="metric-note">Alcance 3 · Categorías registradas</div></section></div>
    <div class="dashboard-grid"><section class="panel"><div class="panel-head"><div><h2>El año, mes a mes</h2><p>Emisiones calculadas en kg CO₂e</p></div>${badge(String(year))}</div>${S.records.length ? `<div class="chart" role="img" aria-label="Emisiones mensuales; cifras disponibles en el detalle inferior">${su.monthly.map((v, i) => `<div class="chart-col" title="${months[i]}: ${fmt(v)} kg CO₂e"><span class="bar-value">${Number(v) > 0 ? fmt(v, 0) : ""}</span><div class="bar" style="height:${(Number(v) / max) * 75}%"></div><span class="month">${months[i]}</span></div>`).join("")}</div><p class="chart-caption">Reparto estimado por días del periodo de cada consumo. Un mes sin barras puede tener datos pendientes.</p><details><summary>Ver cifras mensuales</summary><table><thead><tr><th>Mes</th><th>kg CO₂e calculados</th></tr></thead><tbody>${su.monthly.map((v, i) => `<tr><td>${months[i]}</td><td>${fmt(v, 3)}</td></tr>`).join("")}</tbody></table></details>` : empty("Todavía no hay una serie", "Los datos aparecerán al registrar consumos y aplicar sus factores.")}</section>
    <section class="panel"><div class="panel-head"><div><h2>¿Qué datos faltan?</h2><p>Continuidad de tus suministros declarados</p></div>${badge("Revisar", "warning")}</div><div class="coverage-number">${su.expected ? pct : "—"}<small> % de suministros continuos cubiertos</small></div><div class="progress" role="progressbar" aria-label="Meses y categorías con todos sus días cubiertos" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><span style="width:${pct}%"></span></div><div class="check-row">${icon("document")}<div><strong>${S.records.length} consumos registrados</strong><p>${su.covered} de ${su.expected} meses-categoría con todos sus días cubiertos.</p></div></div><div class="check-row">${icon("factor")}<div><strong>${su.pending} pendientes de cálculo</strong><p>${su.pending ? "Añade o selecciona factores compatibles." : "Los registros actuales tienen un cálculo disponible."}</p></div></div><div class="check-row">${icon("shield")}<div><strong>Tu perímetro importa</strong><p>La cobertura temporal no comprueba compras, viajes ni otras actividades puntuales. Revisa también las fuentes excluidas.</p></div></div><button class="ghost" data-action="coverage">Revisar cobertura ${icon("arrow")}</button></section></div>
    <section class="panel table-panel"><div class="panel-head"><div><h2>Últimos consumos</h2><p>Cada cifra, con su origen y su método</p></div><a href="#consumos">Ver todos</a></div>${recentTable(S.records.slice(0, 5))}</section><p class="privacy-note">Este panel muestra emisiones parciales. No acredita por sí solo la huella completa de tu empresa.</p>`
    );
  },
  consumos() {
    return (
      head(
        "Tus consumos",
        "Registra, revisa y sigue el origen de cada dato.",
        `${btn("Importar Excel o CSV", "import", "")}${btn("Añadir consumo", "record")}`,
      ) +
      `<section class="panel table-panel"><div class="panel-head"><div><h2>Registro de actividad</h2><p>${S.records.length} registros en ${year}</p></div><a class="btn" href="/api/export.csv?year=${year}">${icon("download")} Exportar CSV</a></div><div class="toolbar"><input id="search-records" type="search" placeholder="Buscar instalación, proveedor o referencia" aria-label="Buscar consumos"><select id="facility-filter" aria-label="Filtrar por instalación"><option value="">Todas las instalaciones</option>${S.facilities.map((f) => `<option value="${f.id}">${E(f.name)}</option>`).join("")}</select><select id="category-filter" aria-label="Filtrar por categoría"><option value="">Todas las fuentes</option>${Object.entries(
        cats,
      )
        .map(([k, v]) => `<option value="${k}">${v}</option>`)
        .join(
          "",
        )}</select></div><div id="records-table">${recentTable()}</div><p id="search-count" class="search-count toolbar"></p></section>`
    );
  },
  documentos() {
    return (
      head(
        "El origen de tus datos",
        "Guarda tus facturas y revisa los consumos antes de incorporarlos.",
      ) +
      `<section class="dropzone">${icon("upload")}<h2>Una factura, un dato trazable</h2><p>PDF de hasta 15 MB. La lectura de texto propone campos; tú los confirmas.</p>${btn("Seleccionar PDF", "upload")}<p class="privacy-note">¿Es un escaneo? Guarda el documento y registra los valores manualmente. No se envía a ninguna IA externa.</p></section><section class="panel"><div class="panel-head"><div><h2>Archivo de evidencias</h2><p>${S.documents.length} documentos guardados</p></div></div>${S.documents.length ? S.documents.map((d) => `<div class="list-row"><div><h3>${icon("document")} ${E(d.name)}</h3><p>${new Date(d.created_at).toLocaleDateString("es-ES")} · ${d.linked} consumos vinculados</p></div><div class="actions">${badge(d.linked ? "Vinculado" : "Por revisar", d.linked ? "success" : "warning")}<a class="ghost" href="/api/documents/${d.id}/file">Descargar</a><button class="btn" data-action="review-doc" data-id="${d.id}">Revisar</button></div></div>`).join("") : empty("Tu archivo está vacío", "Sube tu primera factura para conservarla junto a sus consumos.")}</section>`
    );
  },
  instalaciones() {
    return (
      head(
        "Dónde ocurre tu actividad",
        "Define las ubicaciones y las fuentes que quieres medir.",
        btn("Nueva instalación", "facility"),
      ) +
      `<section class="panel">${
        S.facilities.length
          ? S.facilities
              .map(
                (f) =>
                  `<div class="list-row"><div><h3>${icon("building")} ${E(f.name)} ${f.archived ? badge("Archivada") : ""}</h3><p>${E(f.country)} · ${f.ownership === "owned" ? "En propiedad" : "En alquiler"} · ${JSON.parse(
                    f.categories,
                  )
                    .map((c) => cats[c])
                    .join(
                      ", ",
                    )}</p></div><button class="btn" data-action="edit-facility" data-id="${f.id}">Editar</button></div>`,
              )
              .join("")
          : empty(
              "Añade tu primera instalación",
              "Puede ser tu oficina, taller o almacén. El país determina qué factores son compatibles.",
              "Crear instalación",
              "facility",
            )
      }</section>`
    );
  },
  factores() {
    return (
      head(
        "Factores con fundamento",
        "El vínculo entre una actividad y sus emisiones.",
        btn("Añadir factor", "factor"),
      ) +
      notice(
        "Usa factores contrastados para el año, país y unidad de tus consumos. Un factor ausente deja el cálculo pendiente; nunca se sustituye por cero.",
      ) +
      `<section class="panel table-panel"><div class="panel-head"><div><h2>Tu catálogo</h2><p>Valores en kg CO₂e por unidad de actividad · Límites documentados</p></div></div>${S.factors.length ? `<div class="table-wrap"><table><thead><tr><th>Factor / versión</th><th>Aplicación</th><th>Valor</th><th>Fuente</th></tr></thead><tbody>${S.factors.map((f) => `<tr><td><strong>${E(f.name)}</strong><small>${E(f.version)}</small></td><td>${E(cats[f.category])}<small>${E(f.country)} · ${f.year}</small></td><td>${fmt(f.value, 6)}<small>kg CO₂e/${E(f.unit)}</small></td><td><a href="${E(f.source)}" target="_blank" rel="noopener noreferrer">Consultar fuente</a><small>${E(f.license)}</small></td></tr>`).join("")}</tbody></table></div>` : empty("Todavía no hay factores", "Añade un factor de una fuente documentada y comprueba su metodología. Los consumos pueden guardarse mientras tanto.", "Añadir factor", "factor")}</section>`
    );
  },
  informes() {
    return (
      head(
        "Resultados que puedes explicar",
        "Crea una instantánea del periodo con cifras, factores y exclusiones.",
        btn("Generar informe PDF", "report"),
      ) +
      notice(
        "El informe es interno y parcial. Incluye las fuentes registradas, los datos pendientes y el perímetro declarado.",
      ) +
      `<section class="panel"><div class="panel-head"><div><h2>Informes de ${year}</h2><p>Las versiones guardadas no cambian al corregir los datos.</p></div><a class="btn" href="/api/export.csv?year=${year}">Exportar detalle CSV</a></div>${S.reports.length ? S.reports.map((r) => `<div class="list-row"><div><h3>${E(r.name)}</h3><p>${new Date(r.created_at).toLocaleString("es-ES")} ${r.stale ? "· Hay cambios posteriores" : ""}</p></div><div class="actions">${badge(r.stale ? "Versión anterior" : "Actual", r.stale ? "warning" : "success")}<a class="btn" href="/api/reports/${r.id}/pdf">${icon("download")} Descargar PDF</a></div></div>`).join("") : empty("Tu primer informe está por escribir", "Puedes generar un borrador incluso si faltan datos. Las limitaciones quedarán visibles.")}</section><section class="panel" style="margin-top:var(--s6)"><h2>Actividad reciente</h2>${
        S.events.length
          ? `<div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Registro</th><th>Acción</th><th>Detalle</th></tr></thead><tbody>${S.events
              .slice(0, 25)
              .map(
                (v) =>
                  `<tr><td>${new Date(v.created_at).toLocaleString("es-ES")}</td><td>${E({ consumption: "Consumo", factor: "Factor", document: "Documento", report: "Informe", company: "Empresa", facility: "Instalación", backup: "Copia", import: "Importación" }[v.entity] || v.entity)}</td><td>${E({ created: "Creado", corrected: "Corregido", updated: "Actualizado", uploaded: "Guardado", restored: "Restaurado", imported: "Importado" }[v.action] || v.action)}</td><td><button class="ghost" data-action="event" data-id="${v.id}">Ver historial</button></td></tr>`,
              )
              .join("")}</tbody></table></div>`
          : '<p class="muted">Aquí aparecerán los cambios que hagas.</p>'
      }</section>`
    );
  },
  configuracion() {
    return accountConfiguration(companyConfiguration());
  },
};
function companyConfiguration() {
  const c = S.company;
  return (
    head(
      "Tu empresa y tus datos",
      "Delimita qué estás midiendo y conserva una copia recuperable.",
    ) +
    `<div class="two-col"><section class="panel"><h2>Contexto del informe</h2><form id="company-form" class="stack"><label>Nombre de la empresa<input name="name" value="${E(c.name)}" required maxlength="160"></label><div class="fields"><label>País (código ISO)<input name="country" value="${E(c.country)}" placeholder="ES, FR, PT…" minlength="2" maxlength="2" required></label><label>Ejercicio habitual<input name="year" type="number" value="${c.year}" min="2000" max="2100" required></label></div><label>Perímetro de medición<textarea name="boundary" maxlength="4000" placeholder="Qué instalaciones y actividades incluyes">${E(c.boundary)}</textarea></label><label>Exclusiones y limitaciones<textarea name="exclusions" maxlength="4000" placeholder="Fuentes no evaluadas, datos que faltan y motivos">${E(c.exclusions)}</textarea></label><button class="btn primary" type="submit">Guardar configuración</button><div class="error" role="alert"></div></form></section><div class="stack"><section class="panel"><h2>Una copia, por si acaso</h2><p class="muted">Exporta consumos, factores, documentos e informes. La contraseña y las sesiones quedan fuera.</p><a class="btn" href="/api/backup">${icon("download")} Descargar copia ZIP</a><hr><h3>Recuperar desde una copia</h3><p class="muted">Sustituye los datos del espacio actual. Antes de restaurar se guarda una copia automática en la carpeta de datos.</p>${btn("Seleccionar copia para restaurar", "restore", "")}</section><section class="panel"><h2>Cómo se calcula</h2><p class="definition">Cantidad normalizada × factor compatible = kg CO₂e</p><p class="muted">El año y país deben coincidir. Se convierte MWh a kWh y toneladas a kg; el resto de unidades debe coincidir con el factor.</p><p class="small muted">Los registros entre años deben dividirse. El reparto entre meses es una estimación proporcional a los días del periodo.</p></section><section class="panel"><h2>Privacidad</h2><p class="muted">ALgyre no llama a servicios externos. Los archivos se guardan en la carpeta <strong>data</strong> del proyecto. Si esa carpeta está en OneDrive, se aplicará la sincronización que tengas configurada.</p></section></div></div>`
  );
}
function bindView() {
  if (current === "configuracion")
    $("#company-form").onsubmit = (e) => {
      e.preventDefault();
      submit(e.currentTarget, async (d) => {
        await api("company", d);
        year = Number(d.year);
        await refresh();
        toast("Configuración guardada");
      });
    };
  if (current === "consumos") {
    const filter = () => {
      let count = 0;
      const q = $("#search-records").value.toLowerCase(),
        f = $("#facility-filter").value,
        c = $("#category-filter").value;
      $$("#records-table tr[data-record]").forEach((row) => {
        row.hidden = !(
          row.dataset.search.includes(q) &&
          (!f || row.dataset.facility === f) &&
          (!c || row.dataset.category === c)
        );
        if (!row.hidden) count++;
      });
      $("#search-count").textContent = `${count} registros visibles`;
    };
    $("#search-records").oninput = filter;
    $("#facility-filter").onchange = filter;
    $("#category-filter").onchange = filter;
  }
}
