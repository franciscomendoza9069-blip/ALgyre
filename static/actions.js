"use strict";

// Ledger actions. Account actions are dispatched explicitly in accounts.js.
async function ledgerAction(name, id) {
  if (name === "close") return $("#modal").close();
  if (name === "demo") {
    const r = await api("demo", {});
    csrf = r.csrf;
    year = 2026;
    location.hash = "resumen";
    await refresh();
    return;
  }
  if (name === "logout") {
    await api("logout", {});
    S = null;
    $("#modal").close();
    await init();
    return;
  }
  if (name === "facility" || name === "edit-facility") return facilityModal(id);
  if (name === "record" || name === "edit-record") return recordModal(id);
  if (name === "factor") return factorModal();
  if (name === "upload") return pickFile(".pdf,application/pdf", uploadFile);
  if (name === "review-doc") return recordModal(null, id);
  if (name === "coverage") return coverageModal();
  if (name === "import") return startImportWizard();
  if (name === "history-record") return consumptionHistory(id);
  if (name === "pick-csv") return importCSV();
  if (name === "report") {
    modal(
      "Generar informe interno",
      `Se guardará una instantánea de los datos de ${year}.`,
      `${notice("El documento incluirá las exclusiones, los huecos y las fuentes sin factor. No es una certificación.")}<p><strong>${S.records.length} consumos</strong> · ${fmt(S.summary.total)} kg CO₂e calculados · ${S.summary.pending} pendientes.</p><p class="muted">Perímetro: ${E(S.company.boundary || "Todavía no definido. Complétalo en Configuración.")}</p><label class="check-label"><input type="checkbox" name="reviewed" required>He revisado las limitaciones y quiero generar esta versión.</label>`,
      async () => {
        await api("reports", { year });
        location.hash = "informes";
      },
      "Generar PDF",
    );
    return;
  }
  if (name === "event") {
    const ev = S.events.find((v) => v.id === id);
    modal(
      "Historial del registro",
      new Date(ev.created_at).toLocaleString("es-ES"),
      `<p>Motivo: ${E(ev.reason || "Registro de operación")}</p><details open><summary>Valor anterior</summary><pre class="definition">${E(JSON.stringify(JSON.parse(ev.before_json), null, 2))}</pre></details><details open><summary>Valor guardado</summary><pre class="definition">${E(JSON.stringify(JSON.parse(ev.after_json), null, 2))}</pre></details>`,
      null,
    );
    return;
  }
  if (name === "restore")
    return pickFile(".zip,application/zip", async (file) => {
      if (file.size > 17 * 1024 * 1024)
        throw new Error(
          "Esta interfaz admite copias de hasta 17 MB. Consulta el manual para bases mayores.",
        );
      const content = await b64(file);
      modal(
        "Restaurar una copia",
        "Sustituirá los datos del espacio actual; la contraseña se conserva.",
        `<p>Archivo: <strong>${E(file.name)}</strong>. Se conservará una copia previa en la carpeta data.</p>${field("Escribe RESTAURAR para continuar", "confirmation", "", "text", 'required autocomplete="off" pattern="RESTAURAR"')}`,
        async (d) => api("restore", { content, confirmation: d.confirmation }),
        "Restaurar datos",
      );
    });
}
