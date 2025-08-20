class GestorOTP {
	constructor() {
		this.modalOTP = null;
		this.modalConfiguracion = null;
		this.accionPendiente = null;
		this.intentosOTP = 0;
		this.maxIntentos = 3;

		this.inicializar();
	}

	/**
	 * Inicializar gestor OTP
	 */
	inicializar() {
		// Verificar que los modales existen
		const modalOTPElement = document.getElementById("modal-otp");
		const modalConfigElement = document.getElementById("modal-configurar-otp");

		if (!modalOTPElement || !modalConfigElement) {
			console.error("Modales OTP no encontrados en el DOM");
			return;
		}

		// Inicializar modales Bootstrap
		this.modalOTP = new bootstrap.Modal(modalOTPElement);
		this.modalConfiguracion = new bootstrap.Modal(modalConfigElement);

		// Configurar event listeners
		this.configurarEventListeners();

		console.log("Gestor OTP inicializado correctamente");
	}

	/**
	 * Configurar event listeners para modales y botones
	 */
	configurarEventListeners() {
		// Botón confirmar OTP
		const btnConfirmar = document.getElementById("confirmar-otp");
		if (btnConfirmar) {
			btnConfirmar.addEventListener("click", () => this.confirmarCodigoOTP());
		}
		// Botón reconfigurar OTP
		const btnReconfigurar = document.getElementById("btn-reconfigurar-otp");
		if (btnReconfigurar) {
			btnReconfigurar.addEventListener("click", () => this.reconfigurarOTP());
		}

		// Botón generar QR
		const btnGenerarQR = document.getElementById("btn-generar-qr");
		if (btnGenerarQR) {
			btnGenerarQR.addEventListener("click", () => this.generarQRConfiguracion());
		}

		// Botón validar configuración
		const btnValidarConfig = document.getElementById("btn-validar-configuracion");
		if (btnValidarConfig) {
			btnValidarConfig.addEventListener("click", () => this.validarConfiguracionInicial());
		}

		// Input de código OTP (validación en tiempo real)
		const inputOTP = document.getElementById("codigo-otp");
		if (inputOTP) {
			inputOTP.addEventListener("input", (e) => this.validarFormatoCodigoOTP(e.target));
			inputOTP.addEventListener("keypress", (e) => {
				if (e.key === "Enter") {
					this.confirmarCodigoOTP();
				}
			});
		}

		// Input de validación inicial
		const inputValidacion = document.getElementById("codigo-validacion-inicial");
		if (inputValidacion) {
			inputValidacion.addEventListener("input", (e) => this.validarFormatoCodigoOTP(e.target));
			inputValidacion.addEventListener("keypress", (e) => {
				if (e.key === "Enter") {
					this.validarConfiguracionInicial();
				}
			});
		}

		// Limpiar cuando se abren modales
		document.getElementById("modal-otp").addEventListener("shown.bs.modal", () => {
			this.limpiarFormularioOTP();
			document.getElementById("codigo-otp").focus();
		});

		document.getElementById("modal-configurar-otp").addEventListener("shown.bs.modal", () => {
			this.limpiarFormularioConfiguracion();
		});
	}

	/**
	 * FUNCIÓN PRINCIPAL: Ejecutar acción con OTP
	 *
	 * @param {Function} funcionAPI - Función de API a ejecutar
	 * @param {...any} argumentos - Argumentos para la función
	 * @returns {Promise} - Resultado de la función o error
	 */
	async ejecutarConOTP(funcionAPI, ...argumentos) {
		console.log("Ejecutando accion con OTP");
		return new Promise(async (resolve, reject) => {
			try {
				// 1. Verificar estado OTP del usuario
				const estadoOTP = await this.verificarEstadoOTP();

				if (!estadoOTP.otp_habilitado) {
					// Usuario no tiene OTP configurado
					const deseaConfigurar = await this.mostrarModalConfiguracionOTP();
					if (!deseaConfigurar) {
						reject(new Error("Configuración OTP cancelada por el usuario"));
						return;
					}
				}

				// 2. Solicitar código OTP
				const codigoOTP = await this.mostrarModalValidacionOTP();

				// 3. Ejecutar función con código OTP
				const resultado = await this.ejecutarConCodigoOTP(funcionAPI, codigoOTP, ...argumentos);
				resolve(resultado);
			} catch (error) {
				this.manejarErrorOTP(error);
				reject(error);
			}
		});
	}
	/**
	 * Reconfigurar OTP desde modal de validación
	 *
	 */
	async reconfigurarOTP() {
		try {
			// Confirmar con el usuario
			const confirmar = confirm(
				"¿Estás seguro de que quieres reconfigurar la autenticación de dos factores?\n\n" +
					"Esto desactivará tu configuración actual y tendrás que escanear un nuevo código QR."
			);

			if (!confirmar) {
				return;
			}

			this.cambiarEstadoBotonCarga("btn-reconfigurar-otp", true);

			// 1. Resetear configuración OTP en el backend
			const response = await fetch("/api/auth/otp/resetear", {
				method: "POST",
				headers: {
					Authorization: `Bearer ${localStorage.getItem("access_token")}`,
					"Content-Type": "application/json",
				},
			});

			if (!response.ok) {
				throw new Error(`Error reseteando OTP: ${response.status}`);
			}

			const resultado = await response.json();

			if (resultado.reseteado) {
				// 2. Cerrar modal actual
				this.modalOTP.hide();

				// 3. Mostrar notificación
				API.mostrarNotificacion("Configuración reseteada. Configurando nuevamente...", "info");

				// 4. Abrir modal de configuración automáticamente
				setTimeout(() => {
					this.iniciarConfiguracionCompleta();
				}, 500);
			}
		} catch (error) {
			console.error("Error reconfigurándo OTP:", error);
			API.mostrarNotificacion("Error al resetear configuración", "error");
		} finally {
			this.cambiarEstadoBotonCarga("btn-reconfigurar-otp", false);
		}
	}
	/**
	 * Iniciar configuración completa (resetear + configurar)
	 */
	async iniciarConfiguracionCompleta() {
		return new Promise((resolve) => {
			// Mostrar modal de configuración
			this.mostrarPasoConfiguracion(1);
			this.modalConfiguracion.show();

			// Auto-generar QR al abrir
			setTimeout(() => {
				this.generarQRConfiguracion();
			}, 500);

			// Configurar resolución cuando se complete
			this.accionPendiente = {
				tipo: "configuracion_completa",
				resolver: resolve,
			};
		});
	}
	/**
	 * Verificar estado OTP del usuario actual
	 */
	async verificarEstadoOTP() {
		try {
			const response = await fetch("/api/auth/otp/estado", {
				method: "GET",
				headers: {
					Authorization: `Bearer ${localStorage.getItem("access_token")}`,
					"Content-Type": "application/json",
				},
			});

			if (!response.ok) {
				throw new Error(`Error verificando estado OTP: ${response.status}`);
			}

			return await response.json();
		} catch (error) {
			console.error("Error verificando estado OTP:", error);
			throw error;
		}
	}

	/**
	 * Mostrar modal para configuración inicial de OTP
	 */
	async mostrarModalConfiguracionOTP() {
		return new Promise((resolve) => {
			// Mostrar paso 1: generar QR
			this.mostrarPasoConfiguracion(1);
			this.modalConfiguracion.show();

			// Configurar handlers para resolver promesa
			const btnGenerar = document.getElementById("btn-generar-qr");
			const btnCancelar = document.querySelector("#modal-configurar-otp .btn-secondary");

			btnCancelar.onclick = () => {
				this.modalConfiguracion.hide();
				resolve(false);
			};

			// La promesa se resuelve cuando se completa la configuración
			this.accionPendiente = {
				tipo: "configuracion",
				resolver: resolve,
			};
		});
	}

	/**
	 * Mostrar modal para validación de código OTP
	 */
	async mostrarModalValidacionOTP() {
		return new Promise((resolve, reject) => {
			this.modalOTP.show();

			// Configurar handlers
			this.accionPendiente = {
				tipo: "validacion",
				resolver: resolve,
				rechazar: reject,
			};
		});
	}

	/**
	 * Generar QR para configuración inicial
	 */
	async generarQRConfiguracion() {
		try {
			this.cambiarEstadoBotonCarga("btn-generar-qr", true);
			// 1. Generar QR en el backend
			const response = await fetch("/api/auth/otp/configurar-inicial", {
				method: "POST",
				headers: {
					Authorization: `Bearer ${localStorage.getItem("access_token")}`,
					"Content-Type": "application/json",
				},
				body: JSON.stringify({}),
			});

			if (!response.ok) {
				throw new Error(`Error generando QR: ${response.status}`);
			}

			const datos = await response.json();

			// 2. Descargar imagen QR con autenticación
			if (datos.qrurl) {
				await this.cargarImagenQRAutenticada(datos.qrurl);
			}

			// 3. Cambiar a paso 2: validación
			this.mostrarPasoConfiguracion(2);

			API.mostrarNotificacion("QR generado. Escanéalo con tu app de autenticación.", "info");
		} catch (error) {
			console.error("Error generando QR:", error);
			API.mostrarNotificacion("Error generando código QR", "error");
		} finally {
			this.cambiarEstadoBotonCarga("btn-generar-qr", false);
		}
	}

	/**
	 * Cargar imagen QR usando fetch con autenticación - NUEVA FUNCIÓN
	 */
	async cargarImagenQRAutenticada(qrFilename) {
		try {
			// Fetch de la imagen con headers de autenticación
			const response = await fetch(`/api/auth/otp/qr/${qrFilename}`, {
				method: "GET",
				headers: {
					Authorization: `Bearer ${localStorage.getItem("access_token")}`,
				},
			});

			if (!response.ok) {
				throw new Error(`Error cargando QR: ${response.status}`);
			}

			// Convertir respuesta a blob
			const blob = await response.blob();
			// Usar FileReader para crear Data URL en lugar de Blob URL
			const reader = new FileReader();
			return new Promise((resolve, reject) => {
				reader.onload = () => {
					// Asignar Data URL al elemento img
					const imagenQR = document.getElementById("imagen-qr-otp");
					if (imagenQR) {
						imagenQR.src = reader.result;
						console.log("Imagen QR cargada como Data URL");
						resolve();
					} else {
						reject(new Error("Elemento imagen QR no encontrado"));
					}
				};

				reader.onerror = () => {
					reject(new Error("Error leyendo blob como Data URL"));
				};

				// Convertir blob a Data URL
				reader.readAsDataURL(blob);
			});
		} catch (error) {
			console.error("Error cargando imagen QR:", error);
			API.mostrarNotificacion("Error cargando imagen QR", "error");

			// Mostrar mensaje de error en lugar de la imagen
			const imagenQR = document.getElementById("imagen-qr-otp");
			if (imagenQR) {
				imagenQR.alt = "Error cargando QR - Intenta generar nuevamente";
				imagenQR.style.display = "none";
			}
		}
	}
	/**
	 * Validar configuración inicial con código
	 */
	async validarConfiguracionInicial() {
		try {
			const codigo = document.getElementById("codigo-validacion-inicial").value.trim();
			// Validar que el codigo cumpla con los requisitos
			if (!this.validarFormatoCodigoOTP({ value: codigo })) {
				API.mostrarNotificacion("Código debe ser de 6 dígitos", "advertencia");
				return;
			}

			this.cambiarEstadoBotonCarga("btn-validar-configuracion", true);

			const response = await fetch("/api/auth/otp/configurar-inicial", {
				method: "POST",
				headers: {
					Authorization: `Bearer ${localStorage.getItem("access_token")}`,
					"Content-Type": "application/json",
				},
				body: JSON.stringify({
					codigo_validacion: codigo,
				}),
			});

			if (!response.ok) {
				throw new Error(`Error validando código: ${response.status}`);
			}

			const resultado = await response.json();

			if (resultado.otp_configurado) {
				// Configuración exitosa
				this.modalConfiguracion.hide();
				API.mostrarNotificacion("¡OTP configurado correctamente. Debe volver a realizar la acción ejecutada al archivo", "exito");

				// Resolver promesa de configuración
				if (this.accionPendiente) {
					if (this.accionPendiente.tipo === "configuracion") {
						this.accionPendiente.resolver(true);
					} else if (this.accionPendiente.tipo === "configuracion_completa") {
						this.accionPendiente.resolver(true);
					}
					this.accionPendiente = null;
				}
			} else {
				API.mostrarNotificacion("Código incorrecto. Intenta nuevamente.", "error");
			}
		} catch (error) {
			console.error("Error validando configuración:", error);
			API.mostrarNotificacion("Error validando código", "error");
		} finally {
			this.cambiarEstadoBotonCarga("btn-validar-configuracion", false);
		}
	}

	/**
	 * Confirmar código OTP para acción
	 */
	async confirmarCodigoOTP() {
		try {
			const codigo = document.getElementById("codigo-otp").value.trim();

			if (!this.validarFormatoCodigoOTP({ value: codigo })) {
				API.mostrarNotificacion("Código debe ser de 6 dígitos", "advertencia");
				return;
			}

			// Resolver promesa con el código
			if (this.accionPendiente && this.accionPendiente.tipo === "validacion") {
				this.modalOTP.hide();
				this.accionPendiente.resolver(codigo);
				this.accionPendiente = null;
				this.intentosOTP = 0;
			}
		} catch (error) {
			console.error("Error confirmando OTP:", error);
			if (this.accionPendiente && this.accionPendiente.rechazar) {
				this.accionPendiente.rechazar(error);
				this.accionPendiente = null;
			}
		}
	}

	/**
	 * Ejecutar función con código OTP
	 */
	async ejecutarConCodigoOTP(funcionAPI, codigoOTP, ...argumentos) {
		try {
			console.log("Ejecutando con OTP:", funcionAPI.name, "código:", codigoOTP);
			// Si la función API maneja headers personalizados
			if (funcionAPI.name === "descargarDocumento") {
				return await API.descargarDocumento(argumentos[0], codigoOTP);
			} else if (funcionAPI.name === "eliminarDocumento") {
				return await API.eliminarDocumento(argumentos[0], codigoOTP);
			} else if (funcionAPI.name === "obtenerDocumentoPorId") {
				return await API.obtenerDocumentoPorId(argumentos[0], codigoOTP);
			} else {
				// Para funciones genéricas, pasar codigo como último argumento
				return await funcionAPI.apply(API, argumentos.concat([codigoOTP]));
			}
		} catch (error) {
			if (error.codigo_invalido || error.message.includes("OTP")) {
				this.intentosOTP++;
				if (this.intentosOTP >= this.maxIntentos) {
					throw new Error("Máximo de intentos OTP alcanzado");
				}
				throw new Error("Código OTP incorrecto");
			}
			throw error;
		}
	}

	/**
	 * Validar formato de código OTP
	 */
	validarFormatoCodigoOTP(input) {
		const valor = input.value.replace(/\D/g, ""); // Solo dígitos
		input.value = valor.substring(0, 6); // Máximo 6 dígitos

		const esValido = valor.length === 6;

		return esValido;
	}

	/**
	 * Manejar errores OTP
	 */
	manejarErrorOTP(error) {
		if (error.message.includes("cancelada")) {
			API.mostrarNotificacion("Acción cancelada", "info");
		} else if (error.codigo_invalido || error.message.includes("incorrecto")) {
			API.mostrarNotificacion("Código OTP incorrecto. Intenta nuevamente.", "error");
		} else if (error.requiere_configurar_otp) {
			API.mostrarNotificacion("Debes configurar autenticación de dos factores primero", "advertencia");
		} else {
			API.mostrarNotificacion("Error en autenticación OTP", "error");
		}
	}

	/**
	 * Mostrar paso específico de configuración
	 */
	mostrarPasoConfiguracion(paso) {
		const paso1 = document.getElementById("paso-1-qr");
		const paso2 = document.getElementById("paso-2-validacion");
		const btnGenerar = document.getElementById("btn-generar-qr");
		const btnValidar = document.getElementById("btn-validar-configuracion");

		if (paso === 1) {
			paso1.style.display = "block";
			paso2.style.display = "none";
			btnGenerar.classList.remove("d-none");
			btnValidar.classList.add("d-none");
		} else {
			paso1.style.display = "block";
			paso2.style.display = "block";
			btnGenerar.classList.add("d-none");
			btnValidar.classList.remove("d-none");
		}
	}

	/**
	 * Cambiar estado de carga de botón
	 */
	cambiarEstadoBotonCarga(idBoton, cargando) {
		const boton = document.getElementById(idBoton);
		if (!boton) return;
		const spinner = boton.querySelector(".spinner-border");
		const texto = boton.querySelector("span:not(.spinner-border)") || boton;
		if (cargando) {
			boton.disabled = true;
			if (spinner) spinner.classList.remove("d-none");
			if (idBoton === "btn-reconfigurar-otp") {
				texto.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Reseteando...';
			}
		} else {
			boton.disabled = false;
			if (spinner) spinner.classList.add("d-none");
			if (idBoton === "btn-reconfigurar-otp") {
				texto.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Reconfigurar OTP';
			}
		}
	}

	/**
	 * Limpiar formulario OTP
	 */
	limpiarFormularioOTP() {
		const input = document.getElementById("codigo-otp");
		if (input) {
			input.value = "";
			input.classList.remove("is-valid", "is-invalid");
		}
		this.intentosOTP = 0;
	}

	/**
	 * Limpiar formulario configuración
	 */
	limpiarFormularioConfiguracion() {
		const inputValidacion = document.getElementById("codigo-validacion-inicial");
		const imagenQR = document.getElementById("imagen-qr-otp");

		if (inputValidacion) {
			inputValidacion.value = "";
			inputValidacion.classList.remove("is-valid", "is-invalid");
		}

		if (imagenQR) {
			imagenQR.src = "";
		}

		this.mostrarPasoConfiguracion(1);
	}
}

// ===============================
// INICIALIZACIÓN Y EXPORTACIÓN
// ===============================

// Instancia global del gestor OTP
let gestorOTP = null;

// Inicializar cuando el DOM esté listo
document.addEventListener("DOMContentLoaded", function () {
	gestorOTP = new GestorOTP();

	// Hacer disponible globalmente
	window.GestorOTP = gestorOTP;
});

// Funciones de compatibilidad para el código existente
window.ejecutarConOTP = function (funcionAPI, ...argumentos) {
	if (gestorOTP) {
		return gestorOTP.ejecutarConOTP(funcionAPI, ...argumentos);
	} else {
		console.error("Gestor OTP no inicializado");
		return Promise.reject(new Error("Gestor OTP no disponible"));
	}
};

window.confirmarAccionConOTP = function () {
	if (gestorOTP) {
		return gestorOTP.confirmarCodigoOTP();
	}
};

window.generarNuevoOTP = function () {
	if (gestorOTP) {
		return gestorOTP.generarQRConfiguracion();
	}
};
