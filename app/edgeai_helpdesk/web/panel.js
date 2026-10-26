"use strict";

const $ = (id) => document.getElementById(id);
let dominio = { categorias: {}, urgencia: [], estados: {} };
let vista = "cola";
let abierto = null;
let token = "";
try { token = localStorage.getItem("edgeai-token") || ""; } catch (e) { /* sin almacenamiento */ }

async function api(method, path) {
  const headers = token ? { "X-Panel-Token": token } : {};
  const resp = await fetch(path, { method, headers });
  if (resp.status === 401) {
    $("token-box").hidden = false;
    throw new Error("token");
  }
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || `Error ${resp.status}`);
  return data;
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const secs = (ms) => (ms ? `${(ms / 1000).toFixed(1)} s` : "-");
const hora = (iso) => new Date(iso).toLocaleTimeString("es-CR", { hour: "2-digit", minute: "2-digit" });

function urgencyBadge(t) {
  const n = Math.max(0, Math.min(t.urgencia_nivel || 0, dominio.urgencia.length - 1));
  return `<span class="badge u${Math.min(n, 3)}">${esc(dominio.urgencia[n] || n)} · ${(t.urgencia_score ?? 0).toFixed(2)}</span>`;
}

function bar(label, p) {
  const v = Math.round((p || 0) * 100);
  return `<div><div class="small">${esc(label)} <span class="muted">${v}%</span></div><div class="bar"><span style="width:${v}%"></span></div></div>`;
}

function detail(t) {
  const probs = Object.entries(t.categoria_probs || {}).sort((a, b) => b[1] - a[1])
    .map(([k, p]) => bar(dominio.categorias[k] || k, p)).join("");
  const acciones = (t.estado === "en_cola" || t.estado === "autoservicio")
    ? `<button data-accion="atender" data-id="${t.id}">Marcar atendido</button>`
    : (t.estado === "atendido" ? `<button class="ghost" data-accion="reabrir" data-id="${t.id}">Reabrir</button>` : "");
  return `<tr class="detail"><td colspan="6">
    <p><strong>Mensaje${t.nombre ? " de " + esc(t.nombre) : ""}:</strong> ${esc(t.texto)}
      ${t.contacto ? `<br><span class="muted">Contacto: ${esc(t.contacto)}</span>` : ""}</p>
    <div class="meta">
      <span class="badge">${esc(dominio.estados[t.estado] || t.estado)}</span>
      ${t.revision_manual ? '<span class="badge u2">Revisión manual</span>' : ""}
      ${t.datos_sensibles >= 0.5 ? '<span class="badge u2">Datos sensibles</span>' : ""}
      ${t.motivo ? `<span class="badge muted">${esc(t.motivo)}</span>` : ""}
    </div>
    <h4>Modelo de decisión <span class="muted small">(${esc(t.modelo_decision || "-")}, ${secs(t.lat_decision_ms)})</span></h4>
    <div class="probs">
      ${probs}
      ${bar("En alcance", t.en_alcance)}
      ${bar("Apropiado", t.apropiado)}
      ${bar("Datos sensibles", t.datos_sensibles)}
      ${bar("Autoservicio", t.autoservicio)}
    </div>
    <h4>Respuesta <span class="muted small">(${esc(t.modelo_llm || "-")}, ${secs(t.lat_llm_ms)}, ${esc(t.respuesta_estado)})</span></h4>
    <div class="answer">${esc(t.respuesta || "(pendiente)")}</div>
    <div class="actions">${acciones}</div>
  </td></tr>`;
}

function rows(list) {
  if (!list.length) return '<tr><td colspan="6" class="muted">Sin tiquetes en esta vista.</td></tr>';
  return list.map((t) => `
    <tr data-id="${t.id}" style="cursor:pointer">
      <td class="num">${t.id}</td>
      <td>${urgencyBadge(t)}</td>
      <td>${esc(dominio.categorias[t.categoria] || t.categoria)}</td>
      <td>${esc(t.resumen || t.texto).slice(0, 140)}
        ${t.respuesta_estado === "generando" ? '<span class="spinner" title="Redactando"></span>' : ""}</td>
      <td class="num hide-sm">${hora(t.creado)}</td>
      <td class="muted small">${t.revision_manual ? "revisar" : ""}</td>
    </tr>${abierto === t.id ? detail(t) : ""}`).join("");
}

async function refresh() {
  try {
    const h = await api("GET", "/api/health");
    const e = h.estadisticas;
    $("s-cola").textContent = e.en_cola;
    $("s-urg").textContent = e.urgentes;
    $("s-red").textContent = h.en_redaccion;
    $("s-dec").textContent = secs(e.decision_ms_promedio);
    $("s-llm").textContent = secs(e.llm_ms_promedio);
    $("s-total").textContent = e.total;
    const o = h.ollama;
    $("sistema").textContent = o.ok
      ? `Ollama ${o.version} · decisión ${o.modelo_decision} · LLM ${o.modelo_llm}` +
        (o.modelos_faltantes.length ? ` · FALTAN: ${o.modelos_faltantes.join(", ")}` : "")
      : `Ollama no responde (${o.error || "sin detalle"})`;
    for (const [k, on] of Object.entries(h.indicadores.estado)) {
      $(`led-${k}`)?.classList.toggle("on", on);
    }
    $("leds-modo").textContent = h.indicadores.modo === "simulado" ? "LEDs simulados" : "";

    let list;
    if (vista === "cola") list = await api("GET", "/api/cola");
    else if (vista === "todos") list = await api("GET", "/api/tickets?limit=200");
    else list = await api("GET", `/api/tickets?estado=${vista}&limit=200`);
    $("filas").innerHTML = rows(list);
  } catch (err) {
    if (err.message !== "token") $("sistema").textContent = `Sin conexión con la API: ${err.message}`;
  }
}

$("filas").addEventListener("click", async (ev) => {
  const btn = ev.target.closest("button[data-accion]");
  if (btn) {
    ev.stopPropagation();
    await api("POST", `/api/tickets/${btn.dataset.id}/${btn.dataset.accion}`).catch((e) => alert(e.message));
    return refresh();
  }
  const tr = ev.target.closest("tr[data-id]");
  if (!tr) return;
  const id = Number(tr.dataset.id);
  abierto = abierto === id ? null : id;
  refresh();
});

$("tabs").addEventListener("click", (ev) => {
  const b = ev.target.closest("button[data-vista]");
  if (!b) return;
  vista = b.dataset.vista;
  document.querySelectorAll("#tabs button[data-vista]").forEach((x) => x.classList.toggle("active", x === b));
  refresh();
});

$("siguiente").addEventListener("click", async () => {
  const r = await api("POST", "/api/atender-siguiente").catch((e) => ({ mensaje: e.message }));
  if (r.mensaje) alert(r.mensaje);
  refresh();
});

$("token-ok").addEventListener("click", () => {
  token = $("token").value.trim();
  try { localStorage.setItem("edgeai-token", token); } catch (e) { /* sin almacenamiento */ }
  $("token-box").hidden = true;
  refresh();
});

fetch("/api/dominio").then((r) => r.json()).then((d) => {
  dominio = d;
  $("servicio").textContent = d.servicio.nombre;
  refresh();
});
setInterval(refresh, 3000);
