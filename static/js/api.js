/**
 * ===== GESTIÓN DE API - SISTEMA DOCUMENTOS SEGUROS =====
 * Manejo centralizado de todas las llamadas al backend
 */
// Configuración base de la API
const API_BASE_URL = window.location.origin + "/api";
const ENDPOINTS = {
	// Autenticación
	LOGIN: "/auth/login",
	VERIFICAR: "/auth/perfil",
	OTP_GENERAR: "/auth/otp/generar",
	OTP_VALIDAR: "/auth/otp/validar",
	// Documentos
	DOCUMENTOS: "/documentos",
	DOCUMENTO_POR_ID: (id) => `/documentos/${id}`,
	DESCARGAR_DOCUMENTO: (id) => `/documentos/${id}/descargar`,
	BUSCAR_DOCUMENTOS: "/documentos/buscar",
	ESTADISTICAS: "/documentos/estadisticas",
	POR_NIVEL: (nivel) => `/documentos/por-nivel/${nivel}`,
};
/**
 * Función base para realizar llamadas HTTP
 */
async function realizarLlamadaAPI(endpoint, opciones = {}) {
	try {
		const headersAuth = obtenerHeadersAutenticacion();
		const configuracion = {
			method: opciones.method || "GET",
			headers: {
				"Content-Type": "application/json",
				...headersAuth,
				...(opciones.headers || {}), // Headers adicionales (incluyendo OTP)
			},
			...opciones,
		};
		// Limpiar headers duplicados de opciones para evitar sobrescritura
		delete configuracion.headers;
		configuracion.headers = {
			"Content-Type": "application/json",
			...headersAuth,
			...(opciones.headers || {}),
		};
		// Si hay body y no es FormData, convertir a JSON
		if (opciones.body && !(opciones.body instanceof FormData)) {
			configuracion.body = JSON.stringify(opciones.body);
		} else if (opciones.body instanceof FormData) {
			// Para FormData, quitar Content-Type para que el navegador lo configure automáticamente
			delete configuracion.headers["Content-Type"];
			configuracion.body = opciones.body;
		}

		const respuesta = await fetch(API_BASE_URL + endpoint, configuracion);
		// Manejar respuestas que no son JSON (como descargas de archivos)
		if (opciones.esperarBlob) {
			if (!respuesta.ok) {
				const error = await respuesta.text();
				throw new Error(error || `Error HTTP: ${respuesta.status}`);
			}
			return await respuesta.blob();
		}

		const datos = await respuesta.json();

		if (!respuesta.ok) {
			// Manejar errores específicos
			if (respuesta.status === 401) {
				//manejarErrorAutenticacion();
				throw new Error(datos.error || "No autorizado");
			} else if (respuesta.status === 428) {
				// OTP requerido
				throw new ErrorOTPRequerido(datos.error || "Código OTP requerido", datos);
			} else if (respuesta.status === 403) {
				throw new Error(datos.error || "Sin permisos para esta acción");
			} else if (respuesta.status === 404) {
				throw new Error(datos.error || "Recurso no encontrado");
			} else if (respuesta.status === 429) {
				throw new Error(datos.error || "Demasiadas solicitudes. Intenta más tarde.");
			}

			throw new Error(datos.error || `Error: ${respuesta.status}`);
		}

		return datos;
	} catch (error) {
		console.error("Error en llamada API:", error);
		throw error;
	}
}

/**
 * Obtener headers de autenticación
 */
function obtenerHeadersAutenticacion() {
	const token = localStorage.getItem("access_token");
	const headers = {};

	if (token) {
		headers["Authorization"] = `Bearer ${token}`;
	}
	return headers;
}

/**
 * Manejar errores de autenticación
 */
function manejarErrorAutenticacion() {
	localStorage.removeItem("access_token");
	localStorage.removeItem("usuario_datos");
	if (window.location.pathname !== "/login") {
		mostrarNotificacion("Sesión expirada. Redirigiendo al login...", "advertencia");
		setTimeout(() => {
			window.location.href = "/login";
		}, 2000);
	}
}

/**
 * Clase para errores que requieren OTP
 */
class ErrorOTPRequerido extends Error {
	constructor(mensaje, datos) {
		super(mensaje);
		this.name = "ErrorOTPRequerido";
		this.datos = datos;
		this.requiereOTP = true;
	}
}

// ===== FUNCIONES DE AUTENTICACIÓN =====

/**
 * Realizar login
 */
async function loginUsuario(email, password) {
	return await realizarLlamadaAPI(ENDPOINTS.LOGIN, {
		method: "POST",
		body: { email, password },
	});
}

/**
 * Verificar token actual
 */
async function verificarToken() {
	return await realizarLlamadaAPI(ENDPOINTS.VERIFICAR);
}

/**
 * Generar código OTP
 */
async function generarCodigoOTP() {
	return await realizarLlamadaAPI(ENDPOINTS.OTP_GENERAR);
}

/**
 * Validar código OTP
 */
async function validarCodigoOTP(codigo) {
	return await realizarLlamadaAPI(ENDPOINTS.OTP_VALIDAR, {
		method: "POST",
		body: { codigo },
	});
}

// ===== FUNCIONES DE DOCUMENTOS =====

/**
 * Obtener lista de documentos
 */
async function obtenerDocumentos(parametros = {}) {
	const queryString = new URLSearchParams(parametros).toString();
	const endpoint = queryString ? `${ENDPOINTS.DOCUMENTOS}?${queryString}` : ENDPOINTS.DOCUMENTOS;
	return await realizarLlamadaAPI(endpoint);
}

/**
 * Obtener documento por ID
 */
async function obtenerDocumentoPorId(id, codigoOTP = null) {
	if (codigoOTP) {
		return await realizarLlamadaAPI(ENDPOINTS.DOCUMENTO_POR_ID(id), {
			headers: {
				"X-OTP-Code": codigoOTP,
			},
		});
	}
	// Sin headers extras para OTP, solo los de autenticación automáticos
	return await realizarLlamadaAPI(ENDPOINTS.DOCUMENTO_POR_ID(id));
}

/**
 * Crear nuevo documento
 */
async function crearDocumento(formData) {
	return await realizarLlamadaAPI(ENDPOINTS.DOCUMENTOS, {
		method: "POST",
		body: formData, // FormData se envía tal como está
	});
}

/**
 * Actualizar documento
 */
async function actualizarDocumento(id, datos, codigoOTP = null) {
	const opciones = {
		method: "PUT",
		body: datos,
	};

	if (codigoOTP) {
		opciones.headers = {
			"X-OTP-Code": codigoOTP,
		};
	}

	return await realizarLlamadaAPI(ENDPOINTS.DOCUMENTO_POR_ID(id), opciones);
}

/**
 * Eliminar documento
 */
async function eliminarDocumento(id, codigoOTP = null) {
	console.log("eliminarDocumento recibió:", { id, codigoOTP });
	const opciones = {
		method: "DELETE",
	};

	if (codigoOTP) {
		console.log("Header OTP:", codigoOTP);
		opciones.headers = {
			"X-OTP-Code": codigoOTP,
		};
	}
	console.log("Opciones para solicitar eliminar:", opciones);
	const otpvalido = await validarCodigoOTP(codigoOTP);
	//const resultadovalidacion = await otpvalido.json();
	if (otpvalido.valido == true) {
		return await realizarLlamadaAPI(ENDPOINTS.DOCUMENTO_POR_ID(id), opciones);
	} else {
		API.mostrarNotificacion("Código incorrecto. Intenta nuevamente.", "error");
		return false;
	}
}

/**
 * Descargar documento
 */
async function descargarDocumento(id, codigoOTP = null) {
	const opciones = {
		esperarBlob: true,
	};

	if (codigoOTP) {
		opciones.headers = {
			"X-OTP-Code": codigoOTP,
		};
	}

	return await realizarLlamadaAPI(ENDPOINTS.DESCARGAR_DOCUMENTO(id), opciones);
}

/**
 * Búsqueda avanzada de documentos
 */
async function buscarDocumentosAvanzado(criterios) {
	return await realizarLlamadaAPI(ENDPOINTS.BUSCAR_DOCUMENTOS, {
		method: "POST",
		body: criterios,
	});
}

/**
 * Obtener estadísticas
 */
async function obtenerEstadisticas() {
	return await realizarLlamadaAPI(ENDPOINTS.ESTADISTICAS);
}

/**
 * Obtener documentos por nivel de seguridad
 */
async function obtenerDocumentosPorNivel(nivel) {
	return await realizarLlamadaAPI(ENDPOINTS.POR_NIVEL(nivel));
}

// ===== FUNCIONES DE UTILIDAD =====

/**
 * Realizar acción con OTP si es necesario
 */
async function ejecutarConOTP(funcionAPI, ...argumentos) {
	// Verificar que el gestor OTP esté disponible
	if (typeof window.GestorOTP !== "undefined" && window.GestorOTP.ejecutarConOTP) {
		// Usar el gestor OTP
		return await window.GestorOTP.ejecutarConOTP(funcionAPI, ...argumentos);
	}
	console.warn("GestorOTP no disponible, usando sistema OTP original");
	try {
		// Intentar ejecutar sin OTP primero
		return await funcionAPI.apply(this, argumentos);
	} catch (error) {
		// Si requiere OTP, usar el modal actual
		if (error.requiereOTP || error instanceof ErrorOTPRequerido) {
			return await manejarSolicitudOTP(funcionAPI, argumentos);
		}
		throw error;
	}
}
/**
 * Verificar estado OTP del usuario actual
 */
async function verificarEstadoOTP() {
	return await realizarLlamadaAPI("/auth/otp/estado");
}
/**
 * Configurar OTP inicial
 */
async function configurarOTPInicial(codigoValidacion = null) {
	const opciones = {
		method: "POST",
	};

	if (codigoValidacion) {
		opciones.body = { codigo_validacion: codigoValidacion };
	}

	return await realizarLlamadaAPI("/auth/otp/configurar-inicial", opciones);
}
/**
 * Manejar solicitud de OTP
 */
async function manejarSolicitudOTP(funcionAPI, argumentos) {
	return new Promise((resolve, reject) => {
		// Configurar el modal OTP
		const modalOTP = new bootstrap.Modal(document.getElementById("modal-otp"));

		// Función para manejar la confirmación
		const manejarConfirmacion = async () => {
			const codigoOTP = document.getElementById("codigo-otp").value.trim();

			if (!codigoOTP || codigoOTP.length !== 6) {
				mostrarNotificacion("Por favor ingresa un código OTP válido de 6 dígitos", "advertencia");
				return;
			}

			try {
				// Añadir el código OTP a los argumentos
				const argumentosConOTP = [...argumentos, codigoOTP];
				const resultado = await funcionAPI(...argumentosConOTP);
				modalOTP.hide();
				document.getElementById("codigo-otp").value = "";
				resolve(resultado);
			} catch (error) {
				if (error.message.includes("OTP") || error.message.includes("código")) {
					mostrarNotificacion("Código OTP incorrecto. Intenta nuevamente.", "error");
				} else {
					mostrarNotificacion(error.message, "error");
					modalOTP.hide();
					reject(error);
				}
			}
		};

		// Configurar eventos del modal
		const botonConfirmar = document.getElementById("confirmar-otp");
		const botonGenerar = document.getElementById("generar-otp");

		botonConfirmar.onclick = manejarConfirmacion;
		botonGenerar.onclick = async () => {
			try {
				await generarCodigoOTP();
				mostrarNotificacion("Nuevo código OTP generado", "exito");
			} catch (error) {
				mostrarNotificacion("Error al generar código OTP: " + error.message, "error");
			}
		};

		// Manejar cancelación
		document.getElementById("modal-otp").addEventListener(
			"hidden.bs.modal",
			() => {
				document.getElementById("codigo-otp").value = "";
				reject(new Error("Acción cancelada por el usuario"));
			},
			{ once: true }
		);

		// Mostrar modal
		modalOTP.show();

		// Focus en el input
		setTimeout(() => {
			document.getElementById("codigo-otp").focus();
		}, 500);
	});
}
/**
 * Resetear configuración OTP
 */
async function resetearOTP() {
	return await realizarLlamadaAPI("/auth/otp/resetear", {
		method: "POST",
	});
}

/**
 * Función global para mostrar notificaciones
 */

function mostrarNotificacion(mensaje, tipo = "info", duracion = 5000) {
	const contenedor = document.getElementById("contenedor-notificaciones");
	if (!contenedor) return;

	const notificacion = document.createElement("div");
	notificacion.className = `notificacion notificacion-${tipo}`;

	notificacion.innerHTML = `
        <div class="d-flex align-items-center">
            <span>${mensaje}</span>
            <button type="button" class="btn-close btn-close-white ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
    `;

	contenedor.appendChild(notificacion);

	// Auto eliminar
	setTimeout(() => {
		if (notificacion.parentElement) {
			notificacion.remove();
		}
	}, duracion);
}

/**
 * Manejar errores de forma centralizada
 */
function manejarError(error, contexto = "") {
	console.error(`Error en ${contexto}:`, error);

	if (error.requiereOTP) {
		// Estos errores se manejan en el flujo OTP
		return;
	}

	const mensaje = error.message || "Error desconocido";
	mostrarNotificacion(mensaje, "error");
}

// ===== EXPORTAR FUNCIONES PARA USO GLOBAL =====
window.API = {
	// Autenticación
	loginUsuario,
	verificarToken,
	generarCodigoOTP,
	validarCodigoOTP,

	// Documentos
	obtenerDocumentos,
	obtenerDocumentoPorId,
	crearDocumento,
	actualizarDocumento,
	eliminarDocumento,
	descargarDocumento,
	buscarDocumentosAvanzado,
	obtenerEstadisticas,
	obtenerDocumentosPorNivel,

	// Utilidades
	obtenerHeadersAutenticacion,
	ejecutarConOTP,
	manejarError,
	mostrarNotificacion,
	verificarEstadoOTP,
	configurarOTPInicial,
	resetearOTP,
};

// Hacer disponibles las clases de error globalmente
window.ErrorOTPRequerido = ErrorOTPRequerido;
