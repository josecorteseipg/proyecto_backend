// ===== VARIABLES GLOBALES =====
let documentosActuales = [];
let paginaActual = 1;
let totalPaginas = 1;
let cargandoDocumentos = false;
let accionPendienteOTP = null;

// ===== CONFIGURACIÓN =====
const CONFIGURACION = {
	DOCUMENTOS_POR_PAGINA: 10,
	TAMANO_MAXIMO_ARCHIVO: 16 * 1024 * 1024, // 16MB
	TIPOS_PERMITIDOS: [
		"application/pdf",
		"application/msword",
		"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
		"text/plain",
		"image/jpeg",
		"image/jpg",
		"image/png",
		"application/vnd.ms-excel",
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
		"application/vnd.ms-powerpoint",
		"application/vnd.openxmlformats-officedocument.presentationml.presentation",
	],
	EXTENSIONES_PERMITIDAS: [".pdf", ".doc", ".docx", ".txt", ".jpg", ".jpeg", ".png", ".xlsx", ".pptx"],
};

// ===== FUNCIONES DE CARGA DE DOCUMENTOS =====

/**
 * Cargar documentos desde la API
 */
async function cargarDocumentos(resetearPagina = false) {
	if (cargandoDocumentos) return;

	try {
		cargandoDocumentos = true;
		mostrarEstadoCarga(true);

		if (resetearPagina) {
			paginaActual = 1;
		}

		const parametros = obtenerParametrosFiltros();
		parametros.pagina = paginaActual;
		parametros.por_pagina = CONFIGURACION.DOCUMENTOS_POR_PAGINA;

		const respuesta = await API.obtenerDocumentos(parametros);

		documentosActuales = respuesta.documentos || [];
		totalPaginas = respuesta.total_paginas || 1;

		renderizarDocumentos();
		renderizarPaginacion();
	} catch (error) {
		API.manejarError(error, "cargar documentos");
		documentosActuales = [];
		renderizarDocumentos();
	} finally {
		cargandoDocumentos = false;
		mostrarEstadoCarga(false);
	}
}

/**
 * Obtener parámetros de filtros de la UI
 */
function obtenerParametrosFiltros() {
	const parametros = {};

	const busqueda = document.getElementById("busqueda-documentos")?.value.trim();
	const nivel = document.getElementById("filtro-nivel")?.value;
	const ordenar = document.getElementById("filtro-ordenar")?.value;
	const categoria = document.getElementById("filtro-categoria")?.value.trim();
	const fechaDesde = document.getElementById("filtro-fecha-desde")?.value;
	const fechaHasta = document.getElementById("filtro-fecha-hasta")?.value;

	if (busqueda) parametros.busqueda = busqueda;
	if (nivel) parametros.nivel_seguridad = nivel;
	if (ordenar) parametros.ordenar_por = ordenar;
	if (categoria) parametros.categoria = categoria;
	if (fechaDesde) parametros.fecha_desde = fechaDesde;
	if (fechaHasta) parametros.fecha_hasta = fechaHasta;

	return parametros;
}

// ===== FUNCIONES DE RENDERIZADO =====

/**
 * Renderizar lista de documentos
 */
function renderizarDocumentos() {
	const lista = document.getElementById("lista-documentos-tree");
	if (!lista) return;
	if (!Array.isArray(documentosActuales) || documentosActuales.length === 0) {
		lista.innerHTML = `
      <div class="list-group-item text-center py-5">
        <i class="bi bi-folder2-open d-block display-6 text-muted mb-2"></i>
        <h6 class="text-muted mb-1">No se encontraron documentos</h6>
        <p class="text-muted small mb-0">Ajusta los filtros o sube tu primer documento.</p>
      </div>`;
		enlazarAccionesDocumentos(); // asegura listeners de acciones (por si hay paginador)
		return;
	}

	const nodos = construirArbol(documentosActuales);
	const html = nodos.map((n) => renderNodo(n, 0)).join("");
	lista.innerHTML = html;
	enlazarAccionesDocumentos();
}
// Si ya vienen carpetas/hijos, se respetan.
// Si vienen planos, intentamos con: ruta ("Carpeta/Sub/archivo.ext") -> carpeta -> categoria -> raíz.
function construirArbol(items) {
	const root = { tipo: "carpeta", nombre: "__root__", hijos: [] };
	items.forEach((item) => {
		//console.log(item);
		// Determinar si ya es carpeta declarada
		if (item.es_carpeta || Array.isArray(item.hijos)) {
			root.hijos.push(normalizarCarpeta(item));
			return;
		}

		const partesRuta =
			(typeof item.ruta === "string" && item.ruta.trim().length ? desglosarRuta(item.ruta) : null) ||
			(typeof item.carpeta === "string" && item.carpeta.trim().length ? [item.carpeta.trim()] : null);
		if (!partesRuta) {
			root.hijos.push({ tipo: "archivo", data: item });
			return;
		}
		// Insertar según las partes
		let cursor = root;
		partesRuta.forEach((parte, idx) => {
			let hijo = cursor.hijos.find((h) => h.tipo === "carpeta" && h.nombre.toLowerCase() === String(parte).toLowerCase());
			if (!hijo) {
				hijo = { tipo: "carpeta", nombre: parte, hijos: [] };
				cursor.hijos.push(hijo);
			}
			cursor = hijo;
			if (idx === partesRuta.length - 1) {
				cursor.hijos.push({ tipo: "archivo", data: item });
			}
		});
	});

	return root.hijos;
}
function normalizarCarpeta(node) {
	return {
		tipo: "carpeta",
		nombre: node.nombre || node.carpeta || "Carpeta",
		hijos: (node.hijos || []).map((h) => (h.es_carpeta || Array.isArray(h.hijos) ? normalizarCarpeta(h) : { tipo: "archivo", data: h })),
	};
}
function desglosarRuta(ruta) {
	return String(ruta)
		.split("/")
		.map((s) => s.trim())
		.filter(Boolean);
}
/* Render HTML Fila Documento */
function renderNodo(nodo, nivel = 0) {
	if (nodo.tipo === "carpeta") {
		const childrenHTML = (nodo.hijos || []).map((h) => renderNodo(h, nivel + 1)).join("");
		return `
      <div class="list-group-item tree-row" role="treeitem" aria-expanded="false" data-tipo="carpeta">
        <div class="tree-cell w-name">
          <button class="btn btn-sm btn-toggle me-2" aria-label="Expandir">
            <i class="bi bi-caret-right"></i>
          </button>
          <i class="bi bi-folder-fill text-warning me-2"></i>
          <span class="tree-name">${escapeHtml(nodo.nombre)}</span>
        </div>
        <div class="tree-cell w-size">—</div>
        <div class="tree-cell w-date">—</div>
        <div class="tree-cell w-level">
          <span class="badge bg-secondary-subtle text-secondary">Carpeta</span>
        </div>
        <div class="tree-cell w-actions">
          <!-- Podrías agregar acciones para carpeta si las necesitas -->
        </div>
      </div>
      <div class="tree-children collapse ps-5">
        ${childrenHTML}
      </div>
    `;
	}
	// archivo
	return renderFilaArchivo(nodo.data, nivel);
}
function renderFilaArchivo(archivo, nivel = 0) {
	const nombre = archivo?.nombre || archivo?.nombre_archivo_original || "Documento";
	const fecha = safeFormatearFecha(archivo?.fecha_modificacion || archivo?.fecha_creacion);
	const tam = safeFormatearTamano(archivo?.tamano_archivo);
	const nivelSeg = (archivo?.nivel_seguridad || "—").toString().toLowerCase();
	const badge = claseNivelBadge(nivelSeg);
	const icono = iconoPorExtension(nombre, archivo?.extension_archivo, archivo?.tipo_mime);
	const idAttr = archivo?.id ?? ""; // número o string, ambos válidos
	return `
    <div class="list-group-item tree-row" role="treeitem" data-tipo="archivo" data-id="${escapeAttr(idAttr)}">
      <div class="tree-cell w-name">
        <i class="bi ${icono} me-2"></i>
        <span class="tree-name">${escapeHtml(nombre)}</span>
      </div>
      <div class="tree-cell w-size">${tam || "—"}</div>
      <div class="tree-cell w-date">${fecha || "—"}</div>
      <div class="tree-cell w-level">
        <span class="badge ${badge}">${escapeHtml(archivo?.nivel_seguridad || "—")}</span>
      </div>
      <div class="tree-cell w-actions">
        <button class="btn-accion" data-accion="ver" data-id="${escapeAttr(idAttr)}" aria-label="Ver">
          <i class="bi bi-eye"></i>
        </button>
        <button class="btn-accion" data-accion="descargar" data-id="${escapeAttr(idAttr)}" aria-label="Descargar">
          <i class="bi bi-download"></i>
        </button>
        <button class="btn-accion" data-accion="borrar" data-id="${escapeAttr(idAttr)}" aria-label="Borrar">
          <i class="bi bi-trash"></i>
        </button>
      </div>
    </div>
  `;
}
function iconoPorExtension(nombre = "", extension_archivo = "", tipo_mime = "") {
	const ext = (extension_archivo || nombre.split(".").pop() || "").toLowerCase();
	const mapa = {
		pdf: "bi-file-earmark-pdf",
		doc: "bi-file-earmark-word",
		docx: "bi-file-earmark-word",
		xls: "bi-file-earmark-excel",
		xlsx: "bi-file-earmark-excel",
		csv: "bi-file-earmark-spreadsheet",
		ppt: "bi-file-earmark-ppt",
		pptx: "bi-file-earmark-ppt",
		txt: "bi-file-earmark-text",
		jpg: "bi-file-earmark-image",
		jpeg: "bi-file-earmark-image",
		png: "bi-file-earmark-image",
		gif: "bi-file-earmark-image",
		html: "bi-filetype-html",
		css: "bi-filetype-css",
		js: "bi-filetype-js",
		json: "bi-filetype-json",
		zip: "bi-file-earmark-zip",
		rar: "bi-file-earmark-zip",
	};
	if (mapa[ext]) return mapa[ext];
	// fallback por mime
	if ((tipo_mime || "").startsWith("image/")) return "bi-file-earmark-image";
	if ((tipo_mime || "").startsWith("video/")) return "bi-file-earmark-play";
	if ((tipo_mime || "").startsWith("audio/")) return "bi-file-earmark-music";
	return "bi-file-earmark";
}

function claseNivelBadge(nivel) {
	switch ((nivel || "").toString().toLowerCase()) {
		case "publico":
		case "público":
			return "bg-primary-subtle text-primary";
		case "confidencial":
			return "bg-warning-subtle text-warning";
		case "secreto":
			return "bg-danger-subtle text-danger";
		default:
			return "bg-secondary-subtle text-secondary";
	}
}
// Delegación de eventos para acciones ver/descargar/borrar
function enlazarAccionesDocumentos() {
	const lista = document.getElementById("lista-documentos-tree");
	if (!lista) return;

	lista.addEventListener("click", (e) => {
		const btn = e.target.closest(".btn-accion");

		if (!btn) return;

		const id = btn.dataset.id;
		const accion = btn.dataset.accion;

		if (accion === "ver" && typeof verDocumento === "function") {
			verDocumento(id);
		} else if (accion === "descargar" && typeof descargarDocumento === "function") {
			descargarDocumento(id);
		} else if (accion === "borrar" && typeof eliminarDocumento === "function") {
			eliminarDocumento(id);
		}
	}); // se registra una vez por render
}

/* --------------------- Helpers seguros ----------------- */
function safeFormatearFecha(v) {
	if (typeof formatearFecha === "function") return formatearFecha(v);
	if (!v) return "";
	try {
		const d = new Date(v);
		const dd = String(d.getDate()).padStart(2, "0");
		const mm = String(d.getMonth() + 1).padStart(2, "0");
		const yyyy = d.getFullYear();
		return `${dd}/${mm}/${yyyy}`;
	} catch {
		return "";
	}
}
function safeFormatearTamano(bytes) {
	if (typeof formatearTamano === "function") return formatearTamano(bytes);
	if (typeof bytes !== "number") return "";
	const k = 1024,
		sizes = ["Bytes", "KB", "MB", "GB", "TB"];
	if (bytes === 0) return "0 Bytes";
	const i = Math.floor(Math.log(bytes) / Math.log(k));
	return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}
const aTexto = (v) => {
	if (v === null || v === undefined) return "";
	return typeof v === "string" ? v : String(v);
};
function escapeHtml(v) {
	const s = aTexto(v);
	return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
function escapeAttr(v) {
	const s = aTexto(v);
	// Orden pensado para atributos HTML
	return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#039;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * Renderizar paginación
 */
function renderizarPaginacion() {
	const contenedor = document.getElementById("contenedor-paginacion");
	if (!contenedor || totalPaginas <= 1) {
		contenedor.innerHTML = "";
		return;
	}

	let html = `
        <div class="info-paginacion">
            Página ${paginaActual} de ${totalPaginas}
        </div>
    `;

	if (paginaActual > 1) {
		html += `<button class="boton-pagina" onclick="cambiarPagina(${paginaActual - 1})">‹ Anterior</button>`;
	}

	// Mostrar páginas
	const inicio = Math.max(1, paginaActual - 2);
	const fin = Math.min(totalPaginas, paginaActual + 2);

	for (let i = inicio; i <= fin; i++) {
		const clase = i === paginaActual ? "boton-pagina activo" : "boton-pagina";
		html += `<button class="${clase}" onclick="cambiarPagina(${i})">${i}</button>`;
	}

	if (paginaActual < totalPaginas) {
		html += `<button class="boton-pagina" onclick="cambiarPagina(${paginaActual + 1})">Siguiente ›</button>`;
	}

	contenedor.innerHTML = html;
}

// ===== FUNCIONES DE ACCIONES DE DOCUMENTOS =====

/**
 * Ver documento específico
 */
async function verDocumento(id) {
	//número para comparación
	const numeroId = Number(id);
	const documento = documentosActuales.find((d) => d.id === numeroId);
	if (!documento) {
		API.mostrarNotificacion("Documento no encontrado", "error");
		return;
	}

	const datosUsuario = obtenerDatosUsuario();
	if (!datosUsuario) {
		API.mostrarNotificacion("Sesión expirada", "error");
		return;
	}

	try {
		let respuesta;

		// Verificar si requiere OTP según las reglas
		if (requiereOTPPorAccion("ver", documento, datosUsuario)) {
			console.log(`Visualización de "${documento.nombre}" requiere OTP`);
			respuesta = await API.ejecutarConOTP(API.obtenerDocumentoPorId, id);
		} else {
			console.log(`Visualización de "${documento.nombre}" NO requiere OTP`);
			respuesta = await API.obtenerDocumentoPorId(id);
		}
		const documentoCompleto = respuesta.documento || respuesta;
		const permisos = respuesta.permisos_usuario || {};
		const propietario = respuesta.propietario || {};
		const metadatos = respuesta.metadatos_sistema || {};
		mostrarModalDocumento({
			...documentoCompleto,
			permisos_usuario: permisos,
			propietario: propietario,
			metadatos_sistema: metadatos,
		});
	} catch (error) {
		if (error.message !== "Acción cancelada por el usuario") {
			API.manejarError(error, "ver documento");
		}
	}
}

/**
 * Descargar documento
 */
async function descargarDocumento(id) {
	const numeroId = Number(id);
	const documento = documentosActuales.find((d) => d.id === numeroId);
	if (!documento) {
		API.mostrarNotificacion("Documento no encontrado", "error");
		return;
	}

	const datosUsuario = obtenerDatosUsuario();
	if (!datosUsuario) {
		API.mostrarNotificacion("Sesión expirada", "error");
		return;
	}
	try {
		let blob;

		// Verificar si requiere OTP según las reglas
		if (requiereOTPPorAccion("descargar", documento, datosUsuario)) {
			console.log(`Descarga de "${documento.nombre}" requiere OTP`);
			blob = await API.ejecutarConOTP(API.descargarDocumento, id);
		} else {
			console.log(`Descarga de "${documento.nombre}" NO requiere OTP`);
			blob = await API.descargarDocumento(id);
		}
		const nombreArchivo = documento ? documento.nombre_archivo || `documento_${id}` : `documento_${id}`;
		// Crear enlace de descarga
		const url = window.URL.createObjectURL(blob);
		const enlace = document.createElement("a");
		enlace.href = url;
		enlace.download = nombreArchivo;
		enlace.click();

		window.URL.revokeObjectURL(url);
		API.mostrarNotificacion("Documento descargado correctamente", "exito");
	} catch (error) {
		if (error.message !== "Acción cancelada por el usuario") {
			API.manejarError(error, "descargar documento");
		}
	}
}

/**
 * Eliminar documento
 */
async function eliminarDocumento(id) {
	const numeroId = Number(id);
	const documento = documentosActuales.find((d) => d.id === numeroId);
	if (!documento) {
		API.mostrarNotificacion("Documento no encontrado", "error");
		return;
	}
	const datosUsuario = obtenerDatosUsuario();
	if (!datosUsuario) {
		API.mostrarNotificacion("Sesión expirada", "error");
		return;
	}
	// Confirmar eliminación
	if (!confirm(`¿Estás seguro de que quieres eliminar "${documento.nombre}"?`)) {
		return;
	}

	try {
		// Verificar si requiere OTP según las reglas
		if (requiereOTPPorAccion("eliminar", documento, datosUsuario)) {
			console.log(`Eliminación de "${documento.nombre}" requiere OTP`);
			const resultado = await API.ejecutarConOTP(API.eliminarDocumento, id);
			if (resultado) {
				API.mostrarNotificacion("Documento eliminado correctamente", "exito");
			}
		} else {
			console.log(`Eliminación de "${documento.nombre}" NO requiere OTP`);
			//await API.eliminarDocumento(id);
		}

		const existeModal = verificarModalExiste();
		if (existeModal) {
			const modal = document.getElementById("modal-ver-documento");
			if (modal.classList.contains("show")) {
				// El modal de ver documento está abierto y se eliminó desde el modal.
				modal.hide();
			}
		}
		// Recargar documentos
		await cargarDocumentos();
	} catch (error) {
		if (error.message !== "Acción cancelada por el usuario") {
			API.manejarError(error, "eliminar documento");
		}
	}
}
function requiereOTPPorAccion(accion, documento, datosUsuario) {
	if (!documento || !datosUsuario) return false;
	const { rol, id: usuarioId } = datosUsuario;
	const { nivel_seguridad, propietario_id } = documento;
	const esPropio = propietario_id === usuarioId;
	const esAdmin = rol === "admin";
	const esSupervisor = rol === "supervisor";

	switch (accion) {
		case "ver":
			// Solo documentos secretos requieren OTP para ver
			if (nivel_seguridad === "secreto") {
				return true;
			}
			return false;

		case "descargar":
			// Secretos: siempre requiere OTP
			if (nivel_seguridad === "secreto") {
				return true;
			}
			// Confidenciales: requiere OTP si admin accede documento de otro
			if (nivel_seguridad === "confidencial" && esAdmin && !esPropio) {
				return true;
			}
			return false;

		case "eliminar":
			// Secretos y Confidenciales: siempre requiere OTP
			if (nivel_seguridad === "secreto" || nivel_seguridad === "confidencial") {
				return true;
			}
			// Públicos: requiere OTP para admin/propietario (según regla específica)
			if (nivel_seguridad === "publico" && (esAdmin || esPropio)) {
				return true;
			}
			return false;

		case "editar":
			// Confidenciales y secretos requieren OTP para editar
			return nivel_seguridad === "confidencial" || nivel_seguridad === "secreto";

		default:
			return false;
	}
}
/**
 * Editar documento (función placeholder)
 */
function editarDocumento(id) {
	// Por ahora, mostrar modal de vista con opción de editar metadatos
	verDocumento(id);
}

/**
 * Mostrar modal con detalles del documento
 */
function mostrarModalDocumento(documento) {
	const modalElement = document.getElementById("modal-ver-documento");
	if (!modalElement) {
		console.error("Modal 'modal-ver-documento' no encontrado en el DOM");
		API.mostrarNotificacion("Error: Modal no disponible", "error");
		return;
	}
	const modal = new bootstrap.Modal(modalElement);
	const titulo = document.getElementById("titulo-documento-modal");
	const contenido = document.getElementById("contenido-documento-modal");
	const acciones = document.getElementById("acciones-documento-modal");
	if (!titulo || !contenido || !acciones) {
		console.error("Elementos del modal no encontrados:", { titulo: !!titulo, contenido: !!contenido, acciones: !!acciones });
		API.mostrarNotificacion("Error: Modal mal configurado", "error");
		return;
	}
	titulo.textContent = `${documento.nombre || "Documento sin nombre"}`;
	document.getElementById("titulo-documento-modal").textContent = `${documento.nombre}`;

	contenido.innerHTML = `
		<div class="row">
			<div class="col-md-6">
				<h6>Información General</h6>
				<table class="table table-sm">
					<tr><td><strong>Nombre:</strong></td><td>${escapeHtml(documento.nombre || "Sin nombre")}</td></tr>
					<tr><td><strong>Nivel:</strong></td><td>
						<span class="badge ${obtenerClaseBadgeNivel(documento.nivel_seguridad)}">
							${obtenerIconoNivel(documento.nivel_seguridad)} ${(documento.nivel_seguridad || "público").toUpperCase()}
						</span>
					</td></tr>
					<tr><td><strong>Categoría:</strong></td><td>${escapeHtml(documento.categoria || "Sin categoría")}</td></tr>
					<tr><td><strong>Tamaño:</strong></td><td>${formatearTamano(documento.tamano_archivo)}</td></tr>
					<tr><td><strong>Tipo:</strong></td><td>${documento.tipo_mime || "Desconocido"}</td></tr>
					<tr><td><strong>Extensión:</strong></td><td>${documento.extension_archivo || "N/A"}</td></tr>
				</table>
			</div>
			<div class="col-md-6">
				<h6>Fechas y Estadísticas</h6>
				<table class="table table-sm">
					<tr><td><strong>Creado:</strong></td><td>${formatearFechaCompleta(documento.fecha_creacion)}</td></tr>
					<tr><td><strong>Modificado:</strong></td><td>${formatearFechaCompleta(documento.fecha_modificacion)}</td></tr>
					<tr><td><strong>Último acceso:</strong></td><td>${formatearFechaCompleta(documento.fecha_ultimo_acceso)}</td></tr>
					<tr><td><strong>Visualizaciones:</strong></td><td>${documento.visualizaciones || 0}</td></tr>
					<tr><td><strong>Descargas:</strong></td><td>${documento.descargas || 0}</td></tr>
				</table>
				
				${
					documento.tags
						? `
					<h6>Etiquetas</h6>
					<div class="mb-3">
						${documento.tags
							.split(",")
							.map((tag) => `<span class="badge bg-secondary me-1">${escapeHtml(tag.trim())}</span>`)
							.join("")}
					</div>
				`
						: ""
				}
			</div>
		</div>
		
		${
			documento.descripcion
				? `
			<div class="mt-3">
				<h6>Descripción</h6>
				<p class="border rounded p-2 bg-light">${escapeHtml(documento.descripcion)}</p>
			</div>
		`
				: ""
		}
		
		${
			documento.propietario
				? `
			<div class="mt-3">
				<h6>Propietario</h6>
				<p class="text-muted">
					<strong>${escapeHtml(documento.propietario.nombre_completo || documento.propietario.email)}</strong>
					<span class="badge bg-info ms-2">${documento.propietario.rol}</span>
				</p>
			</div>
		`
				: ""
		}
		
		${
			documento.metadatos_sistema
				? `
			<div class="mt-3">
				<h6>Información del Sistema</h6>
				<div class="row">
					<div class="col-md-6">
						<small class="text-muted">
							<strong>Archivo original:</strong> ${escapeHtml(documento.nombre_archivo_original || "N/A")}<br>
							<strong>Archivo en sistema:</strong> ${escapeHtml(documento.metadatos_sistema.nombre_archivo_sistema || "N/A")}<br>
							<strong>Estado:</strong> ${documento.estado || "activo"}
						</small>
					</div>
					<div class="col-md-6">
						<small class="text-muted">
							<strong>Versión:</strong> ${documento.version || "1.0"}<br>
							<strong>Tamaño (MB):</strong> ${documento.tamano_archivo_mb || "N/A"}<br>
							<strong>Días desde creación:</strong> ${documento.dias_desde_creacion || 0}
						</small>
					</div>
				</div>
			</div>
		`
				: ""
		}
	`;

	// Generar acciones para el modal
	const permisos = documento.permisos_usuario || {};
	let botonesAcciones = [];
	if (permisos.puede_descargar) {
		botonesAcciones.push(`
			<button class="btn btn-primary me-2" onclick="descargarDocumento(${documento.id})">
				Descargar
			</button>
		`);
	}

	if (permisos.puede_editar) {
		botonesAcciones.push(`
			<button class="btn btn-outline-secondary me-2" onclick="editarDocumento(${documento.id})">
				Editar
			</button>
		`);
	}

	if (permisos.puede_eliminar) {
		botonesAcciones.push(`
			<button class="btn btn-outline-danger" onclick="eliminarDocumento(${documento.id})">
				Eliminar
			</button>
		`);
	}

	acciones.innerHTML = botonesAcciones.join("");
	modal.show();
}
function obtenerClaseBadgeNivel(nivel) {
	switch ((nivel || "").toLowerCase()) {
		case "publico":
		case "público":
			return "bg-success text-white";
		case "confidencial":
			return "bg-warning text-dark";
		case "secreto":
			return "bg-danger text-white";
		default:
			return "bg-secondary text-white";
	}
}
function verificarModalExiste() {
	const modal = document.getElementById("modal-ver-documento");
	if (!modal) {
		console.error("Modal 'modal-ver-documento' no existe en el DOM");
		console.log(
			"Modales disponibles:",
			Array.from(document.querySelectorAll('[id*="modal"]')).map((m) => m.id)
		);
		return false;
	}
	return true;
}
// ===== FUNCIONES DE SUBIDA DE DOCUMENTOS =====

/**
 * Manejar subida de documento
 */
async function manejarSubidaDocumento(e) {
	e.preventDefault();

	const formulario = e.target;
	const formData = new FormData(formulario);

	// Validar archivo
	const archivo = document.getElementById("archivo-documento").files[0];
	if (!archivo) {
		API.mostrarNotificacion("Por favor selecciona un archivo", "advertencia");
		return;
	}

	if (!validarArchivo(archivo)) {
		return;
	}

	try {
		cambiarEstadoBotonGuardar(true);

		const respuesta = await API.crearDocumento(formData);

		API.mostrarNotificacion("Documento subido correctamente", "exito");
		// limpiar formulario
		formulario.reset();
		document.getElementById("info-archivo").classList.add("oculto");

		// Recargar documentos
		await cargarDocumentos(true);
	} catch (error) {
		API.manejarError(error, "subir documento");
	} finally {
		cambiarEstadoBotonGuardar(false);
	}
}

/**
 * Validar archivo antes de subir
 */
function validarArchivo(archivo) {
	// Validar tamaño
	if (archivo.size > CONFIGURACION.TAMANO_MAXIMO_ARCHIVO) {
		API.mostrarNotificacion(`El archivo es demasiado grande. Máximo permitido: ${formatearTamano(CONFIGURACION.TAMANO_MAXIMO_ARCHIVO)}`, "error");
		return false;
	}

	// Validar tipo
	const extension = "." + archivo.name.split(".").pop().toLowerCase();
	if (!CONFIGURACION.EXTENSIONES_PERMITIDAS.includes(extension)) {
		API.mostrarNotificacion(`Tipo de archivo no permitido. Extensiones válidas: ${CONFIGURACION.EXTENSIONES_PERMITIDAS.join(", ")}`, "error");
		return false;
	}

	return true;
}

/**
 * Cambiar estado del botón de guardar
 */
function cambiarEstadoBotonGuardar(cargando = false) {
	const boton = document.getElementById("boton-guardar-documento");
	const textoGuardar = document.querySelector(".texto-guardar");
	const spinnerGuardar = document.querySelector(".spinner-guardar");

	if (cargando) {
		boton.disabled = true;
		textoGuardar.classList.add("oculto");
		spinnerGuardar.classList.remove("oculto");
	} else {
		boton.disabled = false;
		textoGuardar.classList.remove("oculto");
		spinnerGuardar.classList.add("oculto");
	}
}

// ===== FUNCIONES DE OTP =====

/**
 * Generar nuevo código OTP
 */
async function generarNuevoOTP() {
	try {
		await API.generarCodigoOTP();
		API.mostrarNotificacion("Nuevo código OTP generado", "exito");
	} catch (error) {
		API.manejarError(error, "generar OTP");
	}
}

/**
 * Confirmar acción con OTP
 */
async function confirmarAccionConOTP() {
	if (!accionPendienteOTP) return;

	const codigoOTP = document.getElementById("codigo-otp").value.trim();

	if (!codigoOTP || codigoOTP.length !== 6) {
		API.mostrarNotificacion("Por favor ingresa un código OTP válido de 6 dígitos", "advertencia");
		return;
	}

	try {
		const resultado = await accionPendienteOTP.funcion(...accionPendienteOTP.argumentos, codigoOTP);

		const modal = bootstrap.Modal.getInstance(document.getElementById("modal-otp"));
		modal.hide();
		document.getElementById("codigo-otp").value = "";

		accionPendienteOTP.resolver(resultado);
		accionPendienteOTP = null;
	} catch (error) {
		if (error.message.includes("OTP") || error.message.includes("código")) {
			API.mostrarNotificacion("Código OTP incorrecto. Intenta nuevamente.", "error");
		} else {
			API.manejarError(error, "confirmar con OTP");
			accionPendienteOTP.rechazar(error);
			accionPendienteOTP = null;
		}
	}
}

// ===== FUNCIONES DE NAVEGACIÓN =====

/**
 * Cambiar página de documentos
 */
function cambiarPagina(nuevaPagina) {
	if (nuevaPagina < 1 || nuevaPagina > totalPaginas || nuevaPagina === paginaActual) {
		return;
	}

	paginaActual = nuevaPagina;
	cargarDocumentos();
}

// ===== FUNCIONES DE UTILIDAD =====

/**
 * Mostrar/ocultar estado de carga
 */
function mostrarEstadoCarga(mostrar) {
	const contenedor = document.getElementById("contenedor-documentos");
	if (!contenedor) return;

	if (mostrar) {
		contenedor.classList.add("cargando");
	} else {
		contenedor.classList.remove("cargando");
	}
}

/**
 * Obtener clase CSS según nivel de seguridad
 */
function obtenerClaseNivel(nivel) {
	const clases = {
		publico: "nivel-publico",
		confidencial: "nivel-confidencial",
		secreto: "nivel-secreto",
	};
	return clases[nivel] || "";
}

/**
 * Obtener icono según nivel de seguridad
 */
function obtenerIconoNivel(nivel) {
	const iconos = {
		publico: "📘",
		confidencial: "📙",
		secreto: "📕",
	};
	return iconos[nivel] || "📄";
}

/**
 * Formatear fecha
 */
function formatearFecha(fecha) {
	if (!fecha) return "Fecha desconocida";

	const date = new Date(fecha);
	return date.toLocaleDateString("es-ES", {
		day: "2-digit",
		month: "2-digit",
		year: "numeric",
	});
}

/**
 * Formatear fecha completa
 */
function formatearFechaCompleta(fecha) {
	if (!fecha) return "Fecha desconocida";

	const date = new Date(fecha);
	return date.toLocaleDateString("es-ES", {
		weekday: "long",
		year: "numeric",
		month: "long",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
}

/**
 * Formatear tamaño de archivo
 */
function formatearTamano(bytes) {
	if (!bytes || bytes === 0) return "0 Bytes";

	const k = 1024;
	const tamaños = ["Bytes", "KB", "MB", "GB"];
	const i = Math.floor(Math.log(bytes) / Math.log(k));

	return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + tamaños[i];
}

/**
 * Escapar HTML para prevenir XSS
 */
function escapeHtml(texto) {
	if (!texto) return "";

	const map = {
		"&": "&amp;",
		"<": "&lt;",
		">": "&gt;",
		'"': "&quot;",
		"'": "&#039;",
	};

	return texto.replace(/[&<>"']/g, function (m) {
		return map[m];
	});
}
// ===== EXPORTAR FUNCIONES PARA USO GLOBAL =====
window.DocumentosManager = {
	cargarDocumentos,
	verDocumento,
	descargarDocumento,
	eliminarDocumento,
	editarDocumento,
	manejarSubidaDocumento,
	generarNuevoOTP,
	confirmarAccionConOTP,
	cambiarPagina,
};

// Hacer funciones disponibles globalmente para eventos onclick
window.verDocumento = verDocumento;
window.descargarDocumento = descargarDocumento;
window.eliminarDocumento = eliminarDocumento;
window.editarDocumento = editarDocumento;
window.manejarSubidaDocumento = manejarSubidaDocumento;
window.generarNuevoOTP = generarNuevoOTP;
window.confirmarAccionConOTP = confirmarAccionConOTP;
window.cambiarPagina = cambiarPagina;
