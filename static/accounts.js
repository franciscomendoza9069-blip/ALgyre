"use strict";
let AccountState = null,
  adminPanel = false;

function accountAuth(mode = "login", token = "") {
  const registering = mode === "register",
    installing = mode === "setup",
    forgot = mode === "forgot",
    resetting = mode === "reset",
    verifying = mode === "verify";
  const title = installing
    ? "Crea tu cuenta de administrador"
    : registering
      ? "Crea el espacio de tu empresa"
      : forgot
        ? "Recupera el acceso"
        : resetting
          ? "Elige una nueva contraseña"
          : verifying
            ? "Confirma tu correo"
            : "Entra en ALgyre";
  $("#app").innerHTML =
    `<div class="auth"><section class="auth-story"><div><div class="brand">${logo}ALgyre</div><h1>Tu impacto, con fundamento.</h1><p>Los datos de tu empresa, conectados con sus evidencias.</p></div><footer>${icon("shield")} Cada empresa tiene su propio espacio privado.</footer></section><section class="auth-form"><div class="auth-box"><h2>${title}</h2><p class="muted">${registering ? "Una cuenta para compartir con las personas autorizadas de tu empresa." : verifying ? "Pulsa el botón para activar tu cuenta." : forgot ? "Recibirás un enlace si existe una cuenta con ese correo." : "Accede al espacio de tu empresa."}</p>
  <form id="company-auth">${registering ? field("Nombre de la empresa", "company", "", "text", 'required maxlength="160" autocomplete="organization"') : ""}
  ${!resetting && !verifying ? field("Correo electrónico", "email", "", "email", 'required maxlength="254" autocomplete="username"') : ""}
  ${installing ? field("Responsable del servicio (aparecerá en Privacidad)", "operator_name", "", "text", 'required maxlength="160" autocomplete="organization"') + field("Correo público de contacto", "operator_email", "", "email", 'required maxlength="254"') : ""}
  ${!forgot && !verifying ? field("Contraseña", "password", "", "password", `required minlength="12" maxlength="200" autocomplete="${registering || resetting || installing ? "new-password" : "current-password"}"`) : ""}
  ${registering || resetting || installing ? field("Repite la contraseña", "repeat", "", "password", 'required minlength="12" maxlength="200" autocomplete="new-password"') : ""}
  ${registering ? '<label class="check-label"><input type="checkbox" name="terms" required>He leído las <a href="/terms" target="_blank" rel="noopener">condiciones</a> y la <a href="/privacy" target="_blank" rel="noopener">información de privacidad</a>.</label>' : ""}
  <button type="submit" class="btn primary">${installing ? "Crear administrador" : registering ? "Crear cuenta" : forgot ? "Enviar enlace" : resetting ? "Guardar contraseña" : verifying ? "Confirmar correo" : "Entrar"}</button><div class="error" role="alert"></div></form>
  <div class="auth-foot">${mode !== "login" ? btn("Volver al inicio de sesión", "account-login", "") : ""}${mode === "login" ? (AccountState.registration ? btn("Registrar mi empresa", "account-register", "") : '<p class="small muted">Para dar de alta tu empresa, contacta con el administrador.</p>') + btn("Recuperar contraseña o reenviar confirmación", "account-forgot", "ghost") : ""}<p class="privacy-note"><a href="/privacy">Privacidad</a> · <a href="/terms">Condiciones de uso</a></p></div></div></section></div>`;
  $("#company-auth").onsubmit = async (e) => {
    e.preventDefault();
    await submit(e.currentTarget, async (d) => {
      if ((registering || resetting || installing) && d.password !== d.repeat)
        throw new Error("Las contraseñas no coinciden.");
      if (installing) {
        const result = await api("bootstrap", {
          token,
          email: d.email,
          password: d.password,
          operator_name: d.operator_name,
          operator_email: d.operator_email,
        });
        csrf = result.csrf;
        await init();
        return;
      }
      if (verifying) {
        await api("verify", { token });
        accountAuth();
        toast("Correo confirmado. Ya puedes entrar.");
        return;
      }
      if (resetting) {
        await api("reset-password", { token, password: d.password });
        await init();
        toast("Contraseña actualizada. Vuelve a entrar.");
        return;
      }
      if (registering || forgot) {
        const result = await api(registering ? "register" : "forgot-password", d);
        accountAuth();
        toast(result.message);
        return;
      }
      const result = await api("login", d);
      csrf = result.csrf;
      await init();
    });
  };
}

async function init() {
  try {
    const st = await api("status");
    csrf = st.csrf || "";
    AccountState = st.multi ? st : null;
    if (AccountState) {
      const link = location.hash.match(/^#(verify|reset|setup)=([A-Za-z0-9_-]{20,100})$/);
      if (link) {
        history.replaceState(null, "", location.pathname);
        S = null;
        return accountAuth(link[1], link[2]);
      }
      if (st.authenticated) {
        if (st.role === "admin" && (!st.organization || location.hash === "#administracion")) {
          S = null;
          return adminView();
        }
        adminPanel = false;
        await refresh();
      } else {
        S = null;
        accountAuth();
      }
    } else if (st.authenticated) await refresh();
    else {
      S = null;
      localAuthView(st.configured);
    }
  } catch (e) {
    $("#app").innerHTML =
      `<main class="error-page"><h1>No se pudo abrir ALgyre</h1><p>${E(e.message)}</p><p>Recarga la página. Si continúa, contacta con el administrador.</p></main>`;
  }
}

function render() {
  renderLedger();
  if (!AccountState) return;
  const status = $(".local-status");
  if (status)
    status.innerHTML = `<strong>${icon("shield")} Espacio de empresa</strong>Los datos se guardan en el servidor de ALgyre.`;
  if (AccountState.role === "admin") {
    $(".sidebar nav").insertAdjacentHTML(
      "beforeend",
      `<button class="ghost nav-link" data-action="account-admin">${icon("settings")} Administración</button>`,
    );
    $(".company-label").insertAdjacentHTML(
      "beforeend",
      ' <span class="badge">Administrador</span>',
    );
  }
}

function accountConfiguration(content) {
  if (!AccountState) return content;
  content = content.replace(
    "ALgyre no llama a servicios externos. Los archivos se guardan en la carpeta <strong>data</strong> del proyecto. Si esa carpeta está en OneDrive, se aplicará la sincronización que tengas configurada.",
    "Los datos y archivos se guardan en el servidor de ALgyre, en el espacio de tu empresa. No se envían facturas a servicios de IA. Si se configura el correo, solo se utiliza para mensajes de acceso y recuperación.",
  );
  return (
    content +
    `<section class="panel quality-docs"><h2>Acceso a la cuenta</h2><p>${E(AccountState.email)}</p><div class="actions">${btn("Cambiar contraseña y cerrar las demás sesiones", "account-password", "")}${AccountState.role === "company" ? btn("Eliminar cuenta y datos", "account-delete", "ghost") : ""}</div><p class="privacy-note"><a href="/privacy">Privacidad</a> · <a href="/terms">Condiciones de uso</a></p></section>`
  );
}

let adminCompanies = [];
async function adminView() {
  const result = await api("admin/organizations");
  adminCompanies = result.organizations;
  S = null;
  adminPanel = true;
  location.hash = "administracion";
  $("#app").innerHTML =
    `<header class="topbar"><a class="brand" href="/">${logo}ALgyre</a><div class="actions"><span>Administración</span>${btn("Mi contraseña", "account-password", "")}${btn("Cerrar sesión", "logout", "")}</div></header><main id="main" class="content">${head("Empresas de ALgyre", "Gestiona las cuentas y abre el espacio de cada empresa.", btn("Crear empresa", "admin-create"))}<section class="panel table-panel">${adminCompanies.length ? `<div class="table-wrap"><table><thead><tr><th>Empresa</th><th>Cuenta</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>${adminCompanies.map((o) => `<tr><td><strong>${E(o.name)}</strong></td><td>${E(o.email)}<small>${o.verified ? "Acceso aprobado" : "Pendiente de aprobación"}</small></td><td>${badge(o.active ? "Activa" : "Suspendida", o.active ? "success" : "warning")}</td><td><div class="actions">${!o.verified ? btn("Aprobar", "admin-approve", "", 'data-id="' + E(o.id) + '"') : ""}${o.active ? btn("Abrir", "admin-open", "", 'data-id="' + E(o.id) + '"') : ""}${btn(o.active ? "Suspender" : "Activar", "admin-toggle", "ghost", 'data-id="' + E(o.id) + '"')}${btn("Contraseña", "admin-password", "ghost", 'data-id="' + E(o.id) + '"')}${btn("Eliminar", "admin-delete", "ghost", 'data-id="' + E(o.id) + '"')}</div></td></tr>`).join("")}</tbody></table></div>` : empty("Todavía no hay empresas", "Crea la primera cuenta para empezar.", "Crear empresa", "admin-create")}</section><p class="privacy-note">Las empresas pueden solicitar su cuenta. Sin correo configurado, aprueba las solicitudes aquí. Las cuentas que crees tú pueden entrar directamente.</p></main>`;
}

async function action(name, id) {
  if (!AccountState) return ledgerAction(name, id);
  if (name === "account-login") return accountAuth();
  if (name === "account-register") return accountAuth("register");
  if (name === "account-forgot") {
    if (!AccountState.email_confirmation)
      return toast("Contacta con el administrador para restablecer tu contraseña.");
    return accountAuth("forgot");
  }
  if (name === "account-admin") return adminView();
  if (name === "admin-open") {
    const r = await api("admin/organizations/" + id + "/open", {});
    csrf = r.csrf;
    location.hash = "resumen";
    return init();
  }
  if (name === "admin-toggle") {
    const org = adminCompanies.find((o) => o.id === id);
    await api("admin/organizations/" + id + "/status", { active: !org.active });
    return adminView();
  }
  if (name === "admin-approve") {
    await api("admin/organizations/" + id + "/approve", {});
    return adminView();
  }
  if (name === "admin-create")
    return modal(
      "Crear empresa",
      "Una cuenta compartida por las personas autorizadas de esa empresa.",
      `${field("Empresa", "company", "", "text", 'required maxlength="160"')}${field("Correo de acceso", "email", "", "email", 'required autocomplete="off"')}${field("Contraseña inicial", "password", "", "password", 'required minlength="12" maxlength="200" autocomplete="new-password"')}`,
      async (d) => {
        await api("admin/organizations", d);
      },
      "Crear empresa",
    );
  if (name === "admin-password")
    return modal(
      "Restablecer contraseña",
      "Se cerrarán todas las sesiones de la empresa.",
      field(
        "Nueva contraseña",
        "password",
        "",
        "password",
        'required minlength="12" maxlength="200" autocomplete="new-password"',
      ),
      async (d) => api("admin/organizations/" + id + "/password", d),
    );
  if (name === "account-password")
    return modal(
      "Cambiar tu contraseña",
      "Se cerrarán todas tus sesiones. Después tendrás que entrar de nuevo.",
      `${field("Contraseña actual", "current", "", "password", 'required autocomplete="current-password"')}${field("Nueva contraseña", "password", "", "password", 'required minlength="12" maxlength="200" autocomplete="new-password"')}`,
      async (d) => {
        await api("account/password", d);
      },
    );
  if (name === "admin-delete" || name === "account-delete")
    return modal(
      "Eliminar empresa y cuenta",
      "Se eliminarán los datos activos y sus copias de restauración. Las copias generales del servidor caducan según su retención.",
      `${field("Tu contraseña", "password", "", "password", 'required autocomplete="current-password"')}${field("Escribe ELIMINAR", "confirmation", "", "text", 'required pattern="ELIMINAR" autocomplete="off"')}`,
      async (d) =>
        api(
          name === "admin-delete" ? "admin/organizations/" + id + "/delete" : "account/delete",
          d,
        ),
      "Eliminar definitivamente",
    );
  return ledgerAction(name, id);
}

// Existing dialogs call refresh after saving. Admins without an open ledger stay on their panel.
async function refresh() {
  if (AccountState) {
    const st = await api("status");
    csrf = st.csrf || "";
    AccountState = st;
    if (!st.authenticated) {
      S = null;
      return accountAuth();
    }
    if (st.role === "admin" && (!st.organization || adminPanel)) return adminView();
  }
  return refreshLedger();
}
