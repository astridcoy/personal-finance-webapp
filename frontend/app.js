// ── URL DE LA API: se detecta automáticamente desde el host actual ───────────
// Esto permite que la app funcione desde cualquier IP o dominio sin tocar el código.
// Ej: si accedes desde http://192.168.1.50, la API apunta a http://192.168.1.50:5000
// Ej: si accedes desde http://localhost, la API apunta a http://localhost:5000
const API = `${window.location.protocol}//${window.location.hostname}:5000`;

let CATEGORIAS = {};
let graficoInstance = null;
let idEditando = null;

const COLORES = [
  "#8A9DB1", "#ECC5C6", "#837D68", "#C1C0C2",
  "#7ab59e", "#d46a6a", "#b5a77a", "#9db18a",
];

// ── AUTH HEADER ──────────────────────────────────────
function authHeaders() {
  const token = localStorage.getItem("token");
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`
  };
}

// Si el token expiró o es inválido, redirige al login
function manejarRespuesta(res) {
  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "login.html";
    return null;
  }
  return res.json();
}

// ── CATEGORÍAS DINÁMICAS ─────────────────────────────
async function cargarCategorias() {
  try {
    const res  = await fetch(`${API}/categorias`, { headers: authHeaders() });
    const data = await manejarRespuesta(res);
    if (!data || !data.ok) return;

    const selectRegistro = document.getElementById("categoria");
    const selectFiltro   = document.getElementById("filtroCategoria");
    const selectEditar   = document.getElementById("editCategoria");

    selectRegistro.innerHTML = `<option value="">Selecciona una categoría</option>`;
    selectFiltro.innerHTML   = `<option value="">Todas</option>`;
    selectEditar.innerHTML   = "";

    CATEGORIAS = {};

    data.categorias.forEach((cat) => {
      CATEGORIAS[cat.id_categoria] = cat.tipo;
      const option = `<option value="${cat.id_categoria}">${cat.nombre}</option>`;
      selectRegistro.innerHTML += option;
      selectFiltro.innerHTML   += option;
      selectEditar.innerHTML   += option;
    });
  } catch (e) {
    console.error("No se pudieron cargar categorías", e);
  }
}

// ── FORMATO CLP ──────────────────────────────────────
function formatCLP(value) {
  const abs = Math.abs(value);
  const f = abs.toLocaleString("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  });
  return value < 0 ? `−${f}` : f;
}

// ── TOAST ────────────────────────────────────────────
function mostrarToast(msg, tipo = "success") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = `toast ${tipo} show`;
  setTimeout(() => { t.className = "toast"; }, 3000);
}

// ── SIGNO MONTO ──────────────────────────────────────
function calcularMontoFinal(categoria, monto) {
  const tipo = CATEGORIAS[categoria];
  if (tipo === "Gasto"   && monto > 0) return monto * -1;
  if (tipo === "Ingreso" && monto < 0) return Math.abs(monto);
  return monto;
}

// ── RESUMEN KPIS ─────────────────────────────────────
async function cargarResumen() {
  try {
    const res  = await fetch(`${API}/resumen`, { headers: authHeaders() });
    const data = await manejarRespuesta(res);
    if (data && data.ok) {
      document.getElementById("kpiBalance").textContent  = formatCLP(data.balance);
      document.getElementById("kpiIngresos").textContent = formatCLP(data.ingresos);
      document.getElementById("kpiGastos").textContent   = formatCLP(data.gastos);
    }
  } catch (e) {
    console.warn("Sin conexión a API:", e.message);
  }
}

// ── TABS (solo mobile) ───────────────────────────────
function esDesktop() {
  return window.innerWidth >= 768;
}

function mostrarTabMobile(tab) {
  const registrar = document.getElementById("tab-registrar");
  const historial = document.getElementById("tab-historial");

  if (tab === "registrar") {
    registrar.classList.remove("hidden");
    historial.classList.remove("active-mobile");
    historial.classList.add("hidden");
  } else {
    registrar.classList.add("hidden");
    historial.classList.remove("hidden");
    historial.classList.add("active-mobile");
    cargarHistorial();
  }
}

function sincronizarLayout() {
  const registrar = document.getElementById("tab-registrar");
  const historial = document.getElementById("tab-historial");

  if (esDesktop()) {
    registrar.classList.remove("hidden");
    historial.classList.remove("hidden");
    historial.classList.add("active-mobile");
  } else {
    const tabActivo = document.querySelector(".tab.active")?.dataset.tab || "registrar";
    mostrarTabMobile(tabActivo);
  }
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    if (!esDesktop()) mostrarTabMobile(btn.dataset.tab);
  });
});

window.addEventListener("resize", sincronizarLayout);

// ── HISTORIAL ────────────────────────────────────────
async function cargarHistorial() {
  const fechaFiltro = document.getElementById("filtroMes").value;
  const mes         = fechaFiltro ? fechaFiltro.substring(0, 7) : "";
  const categoria   = document.getElementById("filtroCategoria").value;

  const params = new URLSearchParams();
  if (mes)       params.append("mes", mes);
  if (categoria) params.append("categoria", categoria);

  try {
    const resM = await fetch(`${API}/movimientos?${params}`, { headers: authHeaders() });
    const datM = await manejarRespuesta(resM);
    const tbody = document.getElementById("tablaBody");

    if (!datM || !datM.ok || datM.movimientos.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="tabla-vacia">Sin movimientos</td></tr>`;
    } else {
      tbody.innerHTML = datM.movimientos.map((m) => {
        const montoClass = m.monto >= 0 ? "monto-pos" : "monto-neg";
        const badgeClass = m.tipo === "Ingreso" ? "badge-ingreso" : "badge-gasto";
        const descripcionSegura = String(m.descripcion || "")
          .replace(/\\/g, "\\\\")
          .replace(/'/g, "\\'")
          .replace(/"/g, "&quot;");

        return `
          <tr>
            <td>${m.fecha}</td>
            <td><span class="tipo-badge ${badgeClass}">${m.categoria}</span></td>
            <td>${m.descripcion}</td>
            <td class="${montoClass}">${formatCLP(m.monto)}</td>
            <td>
              <button class="btn-tabla btn-editar"
                onclick="abrirEditar(${m.id_movimiento}, '${m.fecha}', ${m.id_categoria}, '${descripcionSegura}', ${m.monto})">
                ✏️
              </button>
              <button class="btn-tabla btn-eliminar"
                onclick="eliminar(${m.id_movimiento})">
                🗑️
              </button>
            </td>
          </tr>`;
      }).join("");
    }

    const resC = await fetch(`${API}/resumen-categorias?${params}`, { headers: authHeaders() });
    const datC = await manejarRespuesta(resC);
    renderGrafico(datC && datC.ok ? datC.categorias : []);

  } catch (e) {
    document.getElementById("tablaBody").innerHTML =
      `<tr><td colspan="5" class="tabla-vacia">No se pudo conectar con la API</td></tr>`;
  }
}

// ── GRÁFICO ──────────────────────────────────────────
function renderGrafico(categorias) {
  const canvas = document.getElementById("graficoGastos");
  const empty  = document.getElementById("graficoEmpty");

  if (graficoInstance) { graficoInstance.destroy(); graficoInstance = null; }

  if (!categorias || categorias.length === 0) {
    canvas.classList.add("hidden");
    empty.classList.remove("hidden");
    return;
  }

  canvas.classList.remove("hidden");
  empty.classList.add("hidden");

  const labels = categorias.map((c) => c.nombre);
  const values = categorias.map((c) => Math.abs(parseFloat(c.total)));

  graficoInstance = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: COLORES.slice(0, labels.length),
        borderWidth: 2,
        borderColor: "#fff",
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: "bottom",
          labels: { font: { size: 11 }, color: "#837D68", boxWidth: 12, padding: 10 },
        },
        tooltip: {
          callbacks: { label: (ctx) => ` ${formatCLP(-ctx.parsed)}` },
        },
      },
    },
  });
}

// ── FILTRAR ──────────────────────────────────────────
document.getElementById("btnFiltrar").addEventListener("click", cargarHistorial);

// ── ELIMINAR ─────────────────────────────────────────
async function eliminar(id) {
  if (!confirm("¿Eliminar este movimiento?")) return;
  try {
    const res  = await fetch(`${API}/movimientos/${id}`, {
      method: "DELETE",
      headers: authHeaders()
    });
    const data = await manejarRespuesta(res);
    if (data && data.ok) {
      mostrarToast("🗑️ Movimiento eliminado");
      await cargarHistorial();
      await cargarResumen();
    } else if (data) {
      mostrarToast("❌ Error: " + data.error, "error");
    }
  } catch (e) {
    mostrarToast("❌ No se pudo conectar con la API", "error");
  }
}

// ── ABRIR MODAL EDITAR ───────────────────────────────
function abrirEditar(id, fecha, categoria, descripcion, monto) {
  idEditando = id;
  document.getElementById("editFecha").value       = fecha;
  document.getElementById("editCategoria").value   = categoria;
  document.getElementById("editDescripcion").value = descripcion;
  document.getElementById("editMonto").value       = monto;
  document.getElementById("modalOverlay").classList.remove("hidden");
}

// ── GUARDAR EDICIÓN ──────────────────────────────────
document.getElementById("btnGuardarEdicion").addEventListener("click", async () => {
  const categoria = document.getElementById("editCategoria").value;
  let monto = parseFloat(document.getElementById("editMonto").value);

  if (!categoria) { mostrarToast("Selecciona una categoría", "error"); return; }
  if (!monto || monto === 0) { mostrarToast("Ingresa un monto válido", "error"); return; }

  monto = calcularMontoFinal(categoria, monto);

  const payload = {
    fecha:       document.getElementById("editFecha").value,
    categoria:   parseInt(categoria),
    descripcion: document.getElementById("editDescripcion").value.trim(),
    monto,
  };

  try {
    const res  = await fetch(`${API}/movimientos/${idEditando}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await manejarRespuesta(res);
    if (data && data.ok) {
      document.getElementById("modalOverlay").classList.add("hidden");
      mostrarToast("✅ Movimiento actualizado");
      await cargarHistorial();
      await cargarResumen();
    } else if (data) {
      mostrarToast("❌ Error: " + data.error, "error");
    }
  } catch (e) {
    mostrarToast("❌ No se pudo conectar con la API", "error");
  }
});

// ── CERRAR MODAL ─────────────────────────────────────
document.getElementById("btnCancelarEdicion").addEventListener("click", () => {
  document.getElementById("modalOverlay").classList.add("hidden");
});

document.getElementById("modalOverlay").addEventListener("click", (e) => {
  if (e.target === document.getElementById("modalOverlay")) {
    document.getElementById("modalOverlay").classList.add("hidden");
  }
});

// ── PREVIEW CATEGORÍA ────────────────────────────────
document.getElementById("categoria").addEventListener("change", function () {
  const tipo    = CATEGORIAS[this.value];
  const preview = document.getElementById("tipoPreview");

  if (!tipo) {
    preview.textContent = "Selecciona una categoría para detectar el tipo";
    preview.className   = "tipo-preview";
  } else if (tipo === "Ingreso") {
    preview.textContent = "📈 Tipo: Ingreso";
    preview.className   = "tipo-preview tipo-ingreso";
  } else {
    preview.textContent = "📉 Tipo: Gasto";
    preview.className   = "tipo-preview tipo-gasto";
  }
  actualizarMontoPreview();
});

// ── PREVIEW MONTO ────────────────────────────────────
document.getElementById("monto").addEventListener("input", actualizarMontoPreview);

function actualizarMontoPreview() {
  const preview   = document.getElementById("montoPreview");
  const categoria = document.getElementById("categoria").value;
  let val = parseFloat(document.getElementById("monto").value);

  if (!categoria || isNaN(val)) {
    preview.textContent = "Ingresa un monto para previsualizarlo";
    preview.style.color = "";
    return;
  }

  val = calcularMontoFinal(categoria, val);
  preview.textContent = `Se guardará como: ${formatCLP(val)}`;
  preview.style.color = val < 0 ? "#d46a6a" : "#5a9e85";
}

// ── GUARDAR NUEVO MOVIMIENTO ─────────────────────────
document.getElementById("financeForm").addEventListener("submit", async function (e) {
  e.preventDefault();

  const btn         = document.getElementById("btnGuardar");
  const categoria   = document.getElementById("categoria").value;
  const fecha       = document.getElementById("fecha").value;
  const descripcion = document.getElementById("descripcion").value.trim();
  let monto = parseFloat(document.getElementById("monto").value);

  if (!categoria)   { mostrarToast("Selecciona una categoría", "error"); return; }
  if (!fecha)       { mostrarToast("Selecciona una fecha", "error"); return; }
  if (!descripcion) { mostrarToast("Ingresa una descripción", "error"); return; }
  if (!monto || monto === 0) { mostrarToast("Ingresa un monto válido", "error"); return; }

  monto = calcularMontoFinal(categoria, monto);

  const payload = { fecha, categoria: parseInt(categoria), descripcion, monto };

  try {
    btn.disabled    = true;
    btn.textContent = "Guardando...";

    const res  = await fetch(`${API}/guardar`, {
      method:  "POST",
      headers: authHeaders(),
      body:    JSON.stringify(payload),
    });
    const data = await manejarRespuesta(res);

    if (data && data.ok) {
      mostrarToast("✅ Movimiento guardado");
      this.reset();
      document.getElementById("fecha").value              = new Date().toISOString().split("T")[0];
      document.getElementById("tipoPreview").textContent  = "Selecciona una categoría para detectar el tipo";
      document.getElementById("tipoPreview").className    = "tipo-preview";
      document.getElementById("montoPreview").textContent = "Ingresa un monto para previsualizarlo";
      document.getElementById("montoPreview").style.color = "";
      await cargarResumen();
      if (esDesktop()) await cargarHistorial();
    } else if (data) {
      mostrarToast("❌ Error: " + data.error, "error");
    }
  } catch (err) {
    mostrarToast("❌ No se pudo conectar con la API", "error");
  } finally {
    btn.disabled    = false;
    btn.textContent = "Guardar movimiento";
  }
});

// ── LIMPIAR FORMULARIO ───────────────────────────────
document.getElementById("btnLimpiar").addEventListener("click", function () {
  document.getElementById("financeForm").reset();
  document.getElementById("fecha").value              = new Date().toISOString().split("T")[0];
  document.getElementById("tipoPreview").textContent  = "Selecciona una categoría para detectar el tipo";
  document.getElementById("tipoPreview").className    = "tipo-preview";
  document.getElementById("montoPreview").textContent = "Ingresa un monto para previsualizarlo";
  document.getElementById("montoPreview").style.color = "";
});

// ── LOGOUT ───────────────────────────────────────────
function logout() {
  localStorage.removeItem("token");
  window.location.href = "login.html";
}

// ── MODO OSCURO ──────────────────────────────────────
function toggleDark() {
  const isDark = document.body.classList.toggle("dark");
  localStorage.setItem("darkMode", isDark ? "1" : "0");
  document.getElementById("btnDark").textContent = isDark ? "☀️" : "🌙";
}

(function () {
  if (localStorage.getItem("darkMode") === "1") {
    document.body.classList.add("dark");
    const btn = document.getElementById("btnDark");
    if (btn) btn.textContent = "☀️";
  }
})();

// ── INIT ─────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("fecha").value = new Date().toISOString().split("T")[0];
  await cargarCategorias();
  await cargarResumen();
  sincronizarLayout();
  cargarHistorial();
});
