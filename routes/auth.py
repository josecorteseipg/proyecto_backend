"""
Rutas para gestión de autenticación y OTP del Sistema de Gestión de Documentos Seguros
CRUD completo con autenticación, autorización y sistema OTP integrado
Autor: José Luis Cortese
Asignatura: Backend - IPG 2025
Fecha: Agosto 17, 2025
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Usuario, db
from utils.decoradores import (
    requiere_autenticacion, 
    validar_contenido_json, 
    limitar_frecuencia,
    registrar_auditoria
)
from utils.validaciones import ValidadorDatos
import os

# Crear blueprint para rutas de autenticación
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# ===============================
# RUTAS DE AUTENTICACIÓN BÁSICA
# ===============================

@auth_bp.route('/login', methods=['POST'])
@validar_contenido_json(['email', 'password'])
@limitar_frecuencia(maximo_intentos=5, ventana_tiempo=900)  # 5 intentos en 15 minutos
@registrar_auditoria('intento_login')
def login():
    """
    Autentica un usuario y retorna tokens JWT.    
    Request JSON:
    {
        "email": "usuario@test.com",
        "password": "contraseña"
    }    
    Response:
    {
        "mensaje": "Login exitoso",
        "access_token": "...",
        "refresh_token": "...",
        "usuario": {...}
    }
    """
    try:
        datos = request.get_json()
        email = datos.get('email', '').strip().lower()
        password = datos.get('password', '')
        
        # Validar datos básicos
        if not email or not password:
            return jsonify({
                'error': 'Email y contraseña son requeridos',
                'codigo': 'DATOS_FALTANTES'
            }), 400
        
        # Buscar usuario por email
        usuario = Usuario.query.filter_by(email=email).first()
        
        if not usuario:
            return jsonify({
                'error': 'Credenciales inválidas',
                'codigo': 'CREDENCIALES_INVALIDAS'
            }), 401
        
        # Verificar si la cuenta está activa
        if not usuario.activo:
            return jsonify({
                'error': 'Cuenta desactivada',
                'codigo': 'CUENTA_DESACTIVADA'
            }), 401
        
        # Verificar si la cuenta está bloqueada (Escalable)
        if usuario.esta_bloqueado():
            return jsonify({
                'error': 'Cuenta bloqueada por demasiados intentos fallidos',
                'codigo': 'CUENTA_BLOQUEADA'
            }), 423  # Locked
        
        # Verificar contraseña
        if not usuario.verificar_password(password):
            usuario.registrar_intento_fallido()
            return jsonify({
                'error': 'Credenciales inválidas',
                'codigo': 'CREDENCIALES_INVALIDAS'
            }), 401
        
        # Generar tokens JWT
        tokens = usuario.generar_tokens_jwt()
        
        return jsonify({
            'mensaje': 'Login exitoso',
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'usuario': tokens['usuario'],
            'otp_habilitado': usuario.otp_habilitado
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error en login: {str(e)}")
        return jsonify({
            'error': 'Error interno del servidor',
            'codigo': 'ERROR_INTERNO'
        }), 500


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
@registrar_auditoria('refresh_token')
def refrescar_token():
    """
    Genera nuevo access token usando refresh token.
    """
    try:
        usuario_id = get_jwt_identity()
        usuario = Usuario.query.get(usuario_id)
        
        if not usuario or not usuario.activo:
            return jsonify({
                'error': 'Usuario no válido',
                'codigo': 'USUARIO_INVALIDO'
            }), 401
        
        # Generar nuevo access token
        tokens = usuario.generar_tokens_jwt()
        
        return jsonify({
            'access_token': tokens['access_token'],
            'usuario': tokens['usuario']
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error refrescando token: {str(e)}")
        return jsonify({
            'error': 'Error interno del servidor',
            'codigo': 'ERROR_INTERNO'
        }), 500

@auth_bp.route('/verificar', methods=['GET'])
@jwt_required()
def verificar():
    """
    Verificar si el token JWT es válido y retorna info del usuario
    """
    try:
        usuario_id = get_jwt_identity()
        usuario = Usuario.query.get(usuario_id)
        
        if not usuario or not usuario.activo:
            return jsonify({'error': 'Usuario inválido'}), 401
            
        return jsonify({
            'valido': True,
            'usuario': {
                'id': usuario.id,
                'email': usuario.email,
                'nombre_completo': usuario.nombre_completo,
                'rol': usuario.rol,
                'activo': usuario.activo
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Token inválido'}), 401
# ===============================
# RUTAS OTP
# ===============================
@auth_bp.route('/otp/generar', methods=['GET', 'POST'])
@requiere_autenticacion
@registrar_auditoria('generar_otp')
def generar_otp_route(usuario_actual):
    """
    Genera código OTP para el usuario autenticado.    
    Puede recibir parámetros por GET (compatibilidad) o por POST con JSON.
    """
    try:
        usuario_id = get_jwt_identity()
        usuario = Usuario.query.get(usuario_id)
        
        if not usuario or not usuario.activo:
            return jsonify({
                'error': 'Usuario inválido o inactivo',
                'codigo': 'USUARIO_INVALIDO'
            }), 401
        datos_otp = usuario.configurar_otp()            
        if not datos_otp:
            return jsonify({
                'error': 'Error configurando OTP',
                'codigo': 'ERROR_CONFIGURAR_OTP'
            }), 500
        
        respuesta = {
            'mensaje': 'OTP configurado exitosamente',
            'key32': datos_otp['clave_base32'],
            'url': datos_otp['url_qr'],
            'qrurl': datos_otp['archivo_qr'],
            'usuario': usuario.email,
            'configurado_exitosamente': True
        }
        
        return jsonify(respuesta), 200
            
            
    except Exception as e:
        current_app.logger.error(f"Error generando OTP: {str(e)}")
        return jsonify({
            'error': 'Error interno del servidor',
            'codigo': 'ERROR_INTERNO'
        }), 500

@auth_bp.route('/otp/validar',  methods=['POST'])
@jwt_required()
@limitar_frecuencia(maximo_intentos=10, ventana_tiempo=300)  # 10 intentos en 5 minutos
@registrar_auditoria('validar_otp')
def validar_otp_route():
    """
    Valida código OTP.
    Mantiene compatibilidad con la ruta original.
    
    Parámetros GET (compatibilidad):
    - otp: Código OTP de 6 dígitos
    - base: Clave base32 generada previamente
    
    """
    try:
        usuario_id = get_jwt_identity()
        usuario = Usuario.query.get(usuario_id)
        if not usuario or not usuario.activo:
            return jsonify({'error': 'Usuario inválido'}), 401
        datos = request.get_json()
        if not datos:
            return jsonify({
                'error': 'JSON requerido',
                'codigo': 'JSON_REQUERIDO'
            }), 400
        if not usuario.clave_otp_base32:
            current_app.logger.warning(f"Usuario {usuario.email} intenta validar sin clave OTP")
            return jsonify({
                'error': 'No hay configuración OTP pendiente. Genera un QR primero.',
                'codigo': 'NO_HAY_CONFIGURACION_PENDIENTE'
            }), 400
        codigo_otp = datos.get('codigo')
        email_usuario = usuario.email
        
        if not codigo_otp:
            return jsonify({
                'error': 'Código OTP requerido',
                'codigo': 'CODIGO_OTP_REQUERIDO'
            }), 400
        
        # Validar formato
        es_valido, mensaje = ValidadorDatos.validar_codigo_otp(codigo_otp)
        if not es_valido:
            return jsonify({
                'error': mensaje,
                'codigo': 'OTP_FORMATO_INVALIDO'
            }), 400
        
        # Si hay email, buscar usuario específico
        if email_usuario:
                        
            # Validar OTP del usuario
            otp_valido = usuario.validar_otp(codigo_otp)
            
            return jsonify({
                'valido': otp_valido,
                'mensaje': 'OTP válido' if otp_valido else 'OTP inválido',
                'usuario': email_usuario
            }), 200
        
                    
        return jsonify({
            'error': 'Email de usuario requerido o autenticación necesaria',
            'codigo': 'USUARIO_REQUERIDO'
        }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error validando OTP: {str(e)}")
        return jsonify({
            'error': 'Error interno del servidor',
            'codigo': 'ERROR_INTERNO'
        }), 500


@auth_bp.route('/otp/qr/<filename>')
@jwt_required()
def descargar_qr(filename):
    """
    Descarga imagen QR generada para OTP.
    Solo permite descargar QR del usuario autenticado.
    """
    try:
        usuario_id = get_jwt_identity()
        usuario = Usuario.query.get(usuario_id)
        if not usuario or not usuario.activo:
            return jsonify({
                'error': 'Usuario inválido',
                'codigo': 'USUARIO_INVALIDO'
            }), 401
        # Validar que el archivo corresponde al usuario autenticado
        email_sanitizado = usuario.email.replace('@', '_').replace('.', '_')
        archivo_esperado = f"qr_{email_sanitizado}.png"
        
        if filename != archivo_esperado:
            current_app.logger.warning(f"Usuario {usuario.email} intentó acceder a QR no autorizado: {filename}")
            return jsonify({
                'error': 'No autorizado para descargar este QR',
                'codigo': 'QR_NO_AUTORIZADO'
            }), 403
        
        # Construir ruta del archivo
        carpeta_qr = current_app.config.get('QR_FOLDER', 'qr_codes')
        ruta_archivo = os.path.join(carpeta_qr, filename)
        
        # Verificar que el archivo existe
        if not os.path.exists(ruta_archivo):
            return jsonify({
                'error': 'Archivo QR no encontrado',
                'codigo': 'QR_NO_ENCONTRADO'
            }), 404
        
        return send_file(ruta_archivo, as_attachment=False, download_name=filename,mimetype='image/png')
        
    except Exception as e:
        current_app.logger.error(f"Error descargando QR: {str(e)}")
        return jsonify({
            'error': 'Error interno del servidor',
            'codigo': 'ERROR_INTERNO'
        }), 500


@auth_bp.route('/otp/estado', methods=['GET'])
@jwt_required()
@registrar_auditoria('verificar_estado_otp')
def verificar_estado_otp():
    """
    Verificar si el usuario tiene OTP configurado y activo.
    Nuevo endpoint para facilitar la validación desde frontend.
    """
    try:
        usuario_id = get_jwt_identity()
        usuario = Usuario.query.get(usuario_id)
        
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        return jsonify({
            'otp_habilitado': usuario.otp_habilitado,
            'fecha_ultimo_otp': usuario.fecha_ultimo_otp.isoformat() if usuario.fecha_ultimo_otp else None,
            'email': usuario.email,
            'necesita_configuracion': not usuario.otp_habilitado
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error verificando estado OTP: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@auth_bp.route('/otp/configurar-inicial', methods=['POST'])
@jwt_required()
@registrar_auditoria('configurar_otp_inicial')
def configurar_otp_inicial():
    """
    Endpoint para configuración inicial de OTP.
    
    POST sin JSON: Genera QR para configuración (NO activa OTP)
    POST con 'codigo_validacion': Valida y ACTIVA OTP
    """
    try:
        usuario_id = get_jwt_identity()
        usuario = Usuario.query.get(usuario_id)
        
        if not usuario or not usuario.activo:
            return jsonify({'error': 'Usuario inválido'}), 401
        
        try:
            datos_request = request.get_json() or {}
            current_app.logger.info(f"JSON recibido: {datos_request}")
        except Exception as e:
            current_app.logger.warning(f"Error parseando JSON: {str(e)}")
            datos_request = {}
        codigo_validacion = datos_request.get('codigo_validacion')
        
        if not codigo_validacion:
            # PASO 1: Generar QR para configuración inicial (SIN ACTIVAR)
            current_app.logger.info(f"PASO 1: Generando QR para {usuario.email}")
            datos_otp = usuario.configurar_otp()
            if not datos_otp:
                current_app.logger.error(f"Error generando OTP para {usuario.email}")
                return jsonify({'error': 'Error generando configuración OTP'}), 500
            
            # NO activar hasta validación exitosa
            usuario.otp_habilitado = False  # mantener desactivado
            db.session.commit()
            
            return jsonify({
                'configuracion_iniciada': True,
                'qr_url': f"/api/auth/otp/qr/{datos_otp['archivo_qr']}",
                'qr_data': datos_otp['url_qr'],
                'qrurl': datos_otp['archivo_qr'],  # Para compatibilidad
                'mensaje': 'QR generado. Escanea con tu app y envía código para validar',
                'email_usuario': usuario.email,
                'otp_activo': False  # Confirmar que NO está activo aún
            }), 200
        
        else:
            # PASO 2: Validar código y ACTIVAR OTP
            current_app.logger.info(f"PASO 2: Validando código para {usuario.email}")
            if not usuario.clave_otp_base32:
                current_app.logger.warning(f"Usuario {usuario.email} intenta validar sin clave OTP")
                return jsonify({
                    'error': 'No hay configuración OTP pendiente. Genera un QR primero.',
                    'codigo': 'NO_HAY_CONFIGURACION_PENDIENTE'
                }), 400
            if not codigo_validacion.isdigit() or len(codigo_validacion) != 6:
                current_app.logger.info(f"PASO 2: Validando código para {usuario.email}")
                return jsonify({
                    'error': 'Código debe ser de 6 dígitos numéricos',
                    'codigo_invalido': True
                }), 400
            
            resultado_validacion = usuario.validar_otp_con_debug(codigo_validacion)
            current_app.logger.info(f"Resultado validación: {resultado_validacion}")
            if resultado_validacion:
                # activar OTP
                usuario.otp_habilitado = True
                usuario.fecha_ultimo_otp = datetime.utcnow()
                db.session.commit()
                return jsonify({
                    'otp_configurado': True,
                    'otp_activo': True,
                    'mensaje': 'Autenticación de dos factores activada correctamente'
                }), 200
            else:
                current_app.logger.warning(f"Código inválido para {usuario.email}")
                return jsonify({
                    'error': 'Código de validación incorrecto',
                    'codigo_invalido': True
                }), 400
        
    except Exception as e:
        current_app.logger.error(f"Error configurando OTP inicial: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@auth_bp.route('/otp/resetear', methods=['POST'])
@jwt_required()
@registrar_auditoria('resetear_otp')
def resetear_configuracion_otp():
    """
    Resetear configuración OTP para permitir reconfiguración.
    
    Esto permite al usuario reconfigurar OTP si:
    - Se generó el QR pero no se validó correctamente
    - Perdió acceso a la app de autenticación
    - Quiere cambiar de dispositivo
    """
    try:
        usuario_id = get_jwt_identity()
        usuario = Usuario.query.get(usuario_id)
        
        if not usuario or not usuario.activo:
            return jsonify({
                'error': 'Usuario inválido',
                'codigo': 'USUARIO_INVALIDO'
            }), 401
        current_app.logger.info(f"Reseteando OTP para usuario: {usuario.email}")
        # Resetear configuración OTP
        usuario.otp_habilitado = False
        usuario.clave_otp_base32 = None
        usuario.fecha_ultimo_otp = None
        db.session.commit()
        
        # Limpiar archivo QR existente si existe
        try:
            carpeta_qr = current_app.config.get('QR_FOLDER', 'qr_codes')
            email_sanitizado = usuario.email.replace('@', '_').replace('.', '_')
            archivo_qr = os.path.join(carpeta_qr, f"qr_{email_sanitizado}.png")
            if os.path.exists(archivo_qr):
                os.remove(archivo_qr)
                current_app.logger.info(f"QR eliminado para reconfiguración: {usuario.email}")
        except Exception as e:
            current_app.logger.warning(f"No se pudo eliminar QR: {str(e)}")
            # No es crítico, continuar
        
        current_app.logger.info(f"OTP reseteado para usuario: {usuario.email}")
        
        return jsonify({
            'reseteado': True,
            'mensaje': 'Configuración OTP reseteada correctamente',
            'puede_reconfigurar': True,
            'usuario': usuario.email
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error reseteando OTP: {str(e)}")
        return jsonify({
            'error': 'Error interno del servidor',
            'codigo': 'ERROR_INTERNO'
        }), 500

# ===============================
# RUTAS DE GESTIÓN DE CUENTA
# ===============================

@auth_bp.route('/perfil', methods=['GET'])
@requiere_autenticacion
def obtener_perfil(usuario_actual):
    """
    Obtiene información del perfil del usuario autenticado.
    """
    return jsonify({
        'usuario': usuario_actual.to_dict(),
        'otp_configurado': usuario_actual.otp_habilitado
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@requiere_autenticacion
@registrar_auditoria('logout')
def logout(usuario_actual):
    """
    Cierra sesión del usuario.
    Nota: el logout es principalmente del lado frontend.
    """
    return jsonify({
        'mensaje': 'Sesión cerrada exitosamente'
    }), 200