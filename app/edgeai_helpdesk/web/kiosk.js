"use strict";

const $ = (id) => document.getElementById(id);
let dominio = { categorias: {}, urgencia: [], estados: {} };
let pollTimer = null;

async function api(method, path, body) {
  const resp = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || `Error ${resp.status}`);
  return data;
}

function urgencyBadge(el, nivel) {
  const n = Math.max(0, Math.min(nivel || 0, dominio.urgencia.length - 1));
  el.className = `badge u${Math.min(n, 3)}`;
  el.textContent = `Urgencia: ${dominio.urgencia[n] || n}`;
}

function showAnswer(t) {
  const box = $("r-respuesta");
  if (t.respuesta_estado === "pendiente" || t.respuesta_estado === "generando") {
    box.innerHTML = '<span class="spinner"></span>Redactando una respuesta con el asistente local...';
    return false;
  }
  box.textContent = t.respuesta || "Su consulta quedó registrada.";
  const lat = [];
  if (t.lat_decision_ms) lat.push(`clasificación ${(t.lat_decision_ms / 1000).toFixed(1)} s`);
  if (t.lat_llm_ms) lat.push(`respuesta ${(t.lat_llm_ms / 1000).toFixed(1)} s`);
  $("r-lat").textContent = lat.join(" · ");
  return true;
}

function render(t) {
  $("form-card").hidden = true;
  $("resultado").hidden = false;
  $("r-titulo").textContent = `Tiquete #${t.id}`;
  urgencyBadge($("r-urgencia"), t.urgencia_nivel);
  $("r-categoria").textContent = dominio.categorias[t.categoria] || t.categoria;
  $("r-estado").textContent = dominio.estados[t.estado] || t.estado;
  return showAnswer(t);
}

function poll(t) {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => {
    try {
      const c = await api("GET", `/api/consulta/${t.id}?clave=${encodeURIComponent(t.clave)}`);
      if (!showAnswer(c)) poll(t);
    } catch (e) {
      poll(t);
    }
  }, 1500);
}

$("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const btn = $("enviar");
  $("form-error").hidden = true;
  btn.disabled = true;
  btn.textContent = "Analizando...";
  try {
    const t = await api("POST", "/api/tickets", {
      texto: $("texto").value,
      nombre: $("nombre").value,
      contacto: $("contacto").value,
    });
    if (!render(t)) poll(t);
  } catch (e) {
    $("form-error").textContent = e.message;
    $("form-error").hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = "Enviar consulta";
  }
});

$("nueva").addEventListener("click", () => {
  clearTimeout(pollTimer);
  $("form").reset();
  $("r-lat").textContent = "";
  $("resultado").hidden = true;
  $("form-card").hidden = false;
  $("texto").focus();
});

api("GET", "/api/dominio").then((d) => {
  dominio = d;
  $("servicio").textContent = d.servicio.nombre;
  document.title = d.servicio.nombre;
}).catch(() => {});
