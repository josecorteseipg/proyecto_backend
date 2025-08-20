// ===== CONSTANTES =====
const STORAGE_KEYS = {
	ACCESS_TOKEN: "access_token",
	USUARIO_DATOS: "usuario_datos",
	ULTIMO_LOGIN: "ultimo_login",
	CONFIGURACION_USUARIO: "configuracion_usuario",
};

const ROLES_USUARIO = {
	ADMIN: "admin",
	SUPERVISOR: "supervisor",
	USUARIO: "usuario",
};

const NIVELES_SEGURIDAD = {
	PUBLICO: "publico",
	CONFIDENCIAL: "confidencial",
	SECRETO: "secreto",
};
// ===== FUNCIONES DE AUTENTICACIÓN =====
/**
 * Verificar si el usuario está autenticado
 */
function verificarAutenticacion() {
	const token = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
	const datosUsuario = localStorage.getItem(STORAGE_KEYS.USUARIO_DATOS);
	if (!token || !datosUsuario) {
		limpiarSesion();
		return false;
	}

	try {
		// Verificar si el token no ha expirado
		const payload = decodificarTokenJWT(token);
		const ahora = Math.floor(Date.now() / 1000);

		if (payload.exp && payload.exp < ahora) {
			limpiarSesion();
			return false;
		}

		return true;
	} catch (error) {
		console.error("Error verificando token:", error);
		limpiarSesion();
		return false;
	}
}
/**
 * Decodificar token JWT (solo payload, sin verificar firma)
 */
function decodificarTokenJWT(token) {
	try {
		const partes = token.split(".");
		if (partes.length !== 3) {
			throw new Error("Token JWT inválido");
		}

		const payload = partes[1];
		const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
		return JSON.parse(decoded);
	} catch (error) {
		throw new Error("Error decodificando token JWT");
	}
}
/**
 * Obtener datos del usuario actual
 */
function obtenerDatosUsuario() {
	try {
		const datos = localStorage.getItem(STORAGE_KEYS.USUARIO_DATOS);
		return datos ? JSON.parse(datos) : null;
	} catch (error) {
		console.error("Error obteniendo datos de usuario:", error);
		return null;
	}
}
/**
 * Obtener token de acceso actual
 */
function obtenerTokenAcceso() {
	return localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
}
/**
 * Guardar datos de sesión
 */
function guardarSesion(token, datosUsuario) {
	try {
		localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, token);
		localStorage.setItem(STORAGE_KEYS.USUARIO_DATOS, JSON.stringify(datosUsuario));
		localStorage.setItem(STORAGE_KEYS.ULTIMO_LOGIN, new Date().toISOString());

		// Actualizar UI con info del usuario
		actualizarInfoUsuarioUI(datosUsuario);

		return true;
	} catch (error) {
		console.error("Error guardando sesión:", error);
		mostrarNotificacion("Error guardando datos de sesión", "error");
		return false;
	}
}

/**
 * Limpiar datos de sesión
 */
function limpiarSesion() {
	localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
	localStorage.removeItem(STORAGE_KEYS.USUARIO_DATOS);
	localStorage.removeItem(STORAGE_KEYS.CONFIGURACION_USUARIO);

	// Limpiar UI
	limpiarInfoUsuarioUI();
}

/**
 * Cerrar sesión del usuario
 */
function cerrarSesion() {
	limpiarSesion();
	mostrarNotificacion("Sesión cerrada correctamente", "info");

	setTimeout(() => {
		window.location.href = "/login";
	}, 1000);
}

// ===== FUNCIONES DE PERMISOS =====

/**
 * Verificar si el usuario tiene un rol específico
 */
function tieneRol(rol) {
	const datosUsuario = obtenerDatosUsuario();
	return datosUsuario && datosUsuario.rol === rol;
}

/**
 * Verificar si el usuario es administrador
 */
function esAdministrador() {
	return tieneRol(ROLES_USUARIO.ADMIN);
}

/**
 * Verificar si el usuario es supervisor
 */
function esSupervisor() {
	return tieneRol(ROLES_USUARIO.SUPERVISOR);
}

/**
 * Verificar si el usuario puede acceder a un nivel de seguridad
 */
function puedeAccederNivel(nivelSeguridad) {
	const datosUsuario = obtenerDatosUsuario();
	console.log(datosUsuario);
	if (!datosUsuario) return false;

	switch (nivelSeguridad) {
		case NIVELES_SEGURIDAD.PUBLICO:
			return true; // Todos pueden acceder a documentos públicos

		case NIVELES_SEGURIDAD.CONFIDENCIAL:
			return datosUsuario.rol === ROLES_USUARIO.ADMIN || datosUsuario.rol === ROLES_USUARIO.SUPERVISOR;

		case NIVELES_SEGURIDAD.SECRETO:
			return datosUsuario.rol === ROLES_USUARIO.ADMIN;

		default:
			return false;
	}
}

/**
 * Verificar si el usuario puede crear documentos con nivel específico
 */
function puedeCrearNivel(nivelSeguridad) {
	const datosUsuario = obtenerDatosUsuario();
	if (!datosUsuario) return false;

	switch (nivelSeguridad) {
		case NIVELES_SEGURIDAD.PUBLICO:
		case NIVELES_SEGURIDAD.CONFIDENCIAL:
			return true; // Todos pueden crear públicos y confidenciales

		case NIVELES_SEGURIDAD.SECRETO:
			return datosUsuario.rol === ROLES_USUARIO.ADMIN || datosUsuario.rol === ROLES_USUARIO.SUPERVISOR;

		default:
			return false;
	}
}

/**
 * Verificar si el usuario puede eliminar cualquier documento
 */
function puedeEliminarCualquiera() {
	return esAdministrador();
}

// ===== FUNCIONES DE UI =====

/**
 * Actualizar información del usuario en la UI
 */
function actualizarInfoUsuarioUI(datosUsuario) {
	const contenedorInfo = document.getElementById("usuario-info");
	if (!contenedorInfo) return;
	const etiquetasRol = {
		[ROLES_USUARIO.ADMIN]: "Administrador",
		[ROLES_USUARIO.SUPERVISOR]: "Supervisor",
		[ROLES_USUARIO.USUARIO]: "Usuario",
	};

	contenedorInfo.innerHTML = `
        <div class="info-usuario">
            <p class="nombre-usuario">
               ${datosUsuario.nombre_completo || datosUsuario.email} - Rol ${etiquetasRol[datosUsuario.rol] || "Usuario"}
            </p>
        </div>
        <a href="#" class="boton-cerrar-sesion" onclick="cerrarSesion()">
            Salir
        </a>
    `;
}

/**
 * Limpiar información del usuario en la UI
 */
function limpiarInfoUsuarioUI() {
	const contenedorInfo = document.getElementById("usuario-info");
	if (contenedorInfo) {
		contenedorInfo.innerHTML = "";
	}
}

/**
 * Configurar restricciones de UI según rol
 */
function configurarRestriccionesUI() {
	const datosUsuario = obtenerDatosUsuario();
	if (!datosUsuario) return;

	// Ocultar opción de documentos secretos si no tiene permisos
	if (!puedeCrearNivel(NIVELES_SEGURIDAD.SECRETO)) {
		const opcionSecreto = document.getElementById("opcion-secreto");
		if (opcionSecreto) {
			opcionSecreto.style.display = "none";
		}
	}

	// Configurar filtros según permisos
	configurarFiltrosSegunPermisos();
}

/**
 * Configurar filtros de nivel según permisos del usuario
 */
function configurarFiltrosSegunPermisos() {
	const filtroNivel = document.getElementById("filtro-nivel");
	if (!filtroNivel) return;

	const datosUsuario = obtenerDatosUsuario();
	if (!datosUsuario) return;

	// Si no es admin, ocultar opción de filtrar por secretos
	if (!puedeAccederNivel(NIVELES_SEGURIDAD.SECRETO)) {
		const opciones = filtroNivel.querySelectorAll('option[value="secreto"]');
		opciones.forEach((opcion) => (opcion.style.display = "none"));
	}
}

// ===== FUNCIONES DE VALIDACIÓN DE SESIÓN =====

/**
 * Verificar sesión periódicamente
 */
function iniciarVerificacionPeriodica() {
	// Verificar cada 5 minutos
	setInterval(async () => {
		if (!verificarAutenticacion()) {
			return;
		}

		try {
			await API.verificarToken();
		} catch (error) {
			console.log("Token expirado, cerrando sesión");
			manejarSesionExpirada();
		}
	}, 5 * 60 * 1000); // 5 minutos
}

/**
 * Manejar sesión expirada
 */
function manejarSesionExpirada() {
	limpiarSesion();
	mostrarNotificacion("Tu sesión ha expirado. Debes iniciar sesión nuevamente.", "advertencia");

	setTimeout(() => {
		window.location.href = "/login";
	}, 3000);
}

/**
 * Interceptor para actualizar token en las llamadas
 */
function configurarInterceptorToken() {
	// Este interceptor se maneja en api.js
	// Aquí solo configuramos el manejo de errores 401
	window.addEventListener("error", function (e) {
		if (e.error && e.error.message && e.error.message.includes("401")) {
			manejarSesionExpirada();
		}
	});
}

// ===== FUNCIONES DE CONFIGURACIÓN =====

/**
 * Guardar configuración del usuario
 */
function guardarConfiguracionUsuario(configuracion) {
	try {
		const configActual = obtenerConfiguracionUsuario();
		const configNueva = { ...configActual, ...configuracion };
		localStorage.setItem(STORAGE_KEYS.CONFIGURACION_USUARIO, JSON.stringify(configNueva));
		return true;
	} catch (error) {
		console.error("Error guardando configuración:", error);
		return false;
	}
}

/**
 * Obtener configuración del usuario
 */
function obtenerConfiguracionUsuario() {
	try {
		const config = localStorage.getItem(STORAGE_KEYS.CONFIGURACION_USUARIO);
		return config
			? JSON.parse(config)
			: {
					tema: "claro",
					notificaciones: true,
					documentosPorPagina: 10,
					vistaPreferida: "tarjetas",
			  };
	} catch (error) {
		console.error("Error obteniendo configuración:", error);
		return {};
	}
}
/**
 * Inicializar sistema de autenticación
 */
function inicializarAutenticacion() {
	// Verificar autenticación en páginas protegidas
	if (window.location.pathname !== "/login" && !verificarAutenticacion()) {
		window.location.href = "/login";
		return false;
	}
	// Si está autenticado, actualizar UI
	if (verificarAutenticacion()) {
		const datosUsuario = obtenerDatosUsuario();
		if (datosUsuario) {
			actualizarInfoUsuarioUI(datosUsuario);
			configurarRestriccionesUI();
		}
		// Iniciar verificación periódica
		iniciarVerificacionPeriodica();
	}
	// Configurar interceptores
	configurarInterceptorToken();
	return true;
}

// ===== EXPORTAR FUNCIONES PARA USO GLOBAL =====
window.Auth = {
	// Verificación y sesión
	verificarAutenticacion,
	obtenerDatosUsuario,
	obtenerTokenAcceso,
	guardarSesion,
	limpiarSesion,
	cerrarSesion,
	// Permisos
	tieneRol,
	esAdministrador,
	esSupervisor,
	puedeAccederNivel,
	puedeCrearNivel,
	puedeEliminarCualquiera,
	// UI
	actualizarInfoUsuarioUI,
	configurarRestriccionesUI,
	// Configuración
	guardarConfiguracionUsuario,
	obtenerConfiguracionUsuario,
	// Inicialización
	inicializarAutenticacion,
	// Constantes
	ROLES_USUARIO,
	NIVELES_SEGURIDAD,
};

// ===== AUTO-INICIALIZACIÓN =====
document.addEventListener("DOMContentLoaded", function () {
	// No auto-inicializar si estamos en la página de login
	if (window.location.pathname !== "/login") {
		Auth.inicializarAutenticacion();
	}
});
