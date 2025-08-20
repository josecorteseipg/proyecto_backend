from functools import wraps
import os
from flask import jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from models import Usuario, Documento

def requiere_autenticacion(f):
    """
    Decorador que requiere autenticación JWT válida.
    
    Usage:
        @app.route('/api/perfil')
        @requiere_autenticacion
        def obtener_perfil():
            # usuario_actual estará disponible
            pass
    """
    @wraps(f)
    @jwt_required()
    def funcion_decorada(*args, **kwargs):
        try:
            # Obtener ID del usuario del token JWT
            usuario_id = get_jwt_identity()
            # Buscar usuario en base de datos
            usuario_actual = Usuario.query.get(usuario_id)
            print(usuario_actual)
            if not usuario_actual:
                return jsonify({
                    'error': 'Usuario no encontrado',
                    'codigo': 'USUARIO_NO_ENCONTRADO'
                }), 401
            
            if not usuario_actual.activo:
                return jsonify({
                    'error': 'Cuenta de usuario desactivada',
                    'codigo': 'CUENTA_DESACTIVADA'
                }), 401
            
            # Inyectar usuario actual en kwargs
            kwargs['usuario_actual'] = usuario_actual
            
            return f(*args, **kwargs)
            
        except Exception as e:
            current_app.logger.error(f"Error en autenticación: {str(e)}")
            return jsonify({
                'error': 'Error de autenticación',
                'codigo': 'ERROR_AUTENTICACION'
            }), 401
    
    return funcion_decorada


def requiere_rol(*roles_permitidos):
    """
    Decorador que requiere uno de los roles especificados.
    
    Args:
        *roles_permitidos: Lista de roles que pueden acceder
    
    Usage:
        @app.route('/api/admin')
        @requiere_rol('admin')
        def funcion_admin():
            pass
            
        @app.route('/api/supervisores')
        @requiere_rol('supervisor', 'admin')
        def funcion_supervisor():
            pass
    """
    def decorador(f):
        @wraps(f)
        @requiere_autenticacion
        def funcion_decorada(*args, **kwargs):
            usuario_actual = kwargs.get('usuario_actual')
            
            if usuario_actual.rol not in roles_permitidos:
                return jsonify({
                    'error': f'Acceso denegado. Se requiere rol: {", ".join(roles_permitidos)}',
                    'codigo': 'ROL_INSUFICIENTE',
                    'rol_actual': usuario_actual.rol,
                    'roles_requeridos': list(roles_permitidos)
                }), 403
            
            return f(*args, **kwargs)
        
        return funcion_decorada
    return decorador


def requiere_admin(f):
    """
    Decorador que requiere rol de administrador.
    
    Usage:
        @app.route('/api/admin/usuarios')
        @requiere_admin
        def gestionar_usuarios():
            pass
    """
    return requiere_rol('admin')(f)


def requiere_supervisor_o_admin(f):
    """
    Decorador que requiere rol de supervisor o administrador.
    
    Usage:
        @app.route('/api/reportes')
        @requiere_supervisor_o_admin
        def ver_reportes():
            pass
    """
    return requiere_rol('supervisor', 'admin')(f)


def validar_acceso_documento(accion='ver'):
    """
    Decorador que valida si el usuario puede realizar una acción sobre un documento.
    
    Args:
        accion (str): Acción a validar ('ver', 'eliminar', 'descargar')
    
    Usage:
        @app.route('/api/documentos/<int:documento_id>')
        @validar_acceso_documento('ver')
        def ver_documento(documento_id, usuario_actual, documento):
            pass
    """
    def decorador(f):
        @wraps(f)
        @requiere_autenticacion
        def funcion_decorada(*args, **kwargs):
            usuario_actual = kwargs.get('usuario_actual')
            
            # Extraer documento_id de la URL
            documento_id = kwargs.get('documento_id') or request.view_args.get('documento_id')
            
            if not documento_id:
                return jsonify({
                    'error': 'ID de documento requerido',
                    'codigo': 'DOCUMENTO_ID_FALTANTE'
                }), 400
            
            # Buscar documento
            documento = Documento.query.get(documento_id)
            
            if not documento:
                return jsonify({
                    'error': 'Documento no encontrado',
                    'codigo': 'DOCUMENTO_NO_ENCONTRADO'
                }), 404
            
            if documento.estado != 'activo':
                return jsonify({
                    'error': 'Documento no disponible',
                    'codigo': 'DOCUMENTO_NO_DISPONIBLE'
                }), 410
            
            # Validar permisos según la acción
            puede_realizar_accion = False
            
            if accion == 'ver':
                puede_realizar_accion = documento.puede_ser_accedido_por(usuario_actual)
            elif accion == 'editar':
                puede_realizar_accion = documento.puede_ser_modificado_por(usuario_actual)
            elif accion == 'eliminar':
                puede_realizar_accion = documento.puede_ser_eliminado_por(usuario_actual)
            elif accion == 'descargar':
                puede_realizar_accion = documento.puede_ser_accedido_por(usuario_actual)
            
            if not puede_realizar_accion:
                return jsonify({
                    'error': f'No tienes permisos para {accion} este documento',
                    'codigo': 'PERMISOS_INSUFICIENTES',
                    'accion': accion,
                    'nivel_seguridad': documento.nivel_seguridad
                }), 403
            
            # Inyectar documento en kwargs
            kwargs['documento'] = documento
            
            return f(*args, **kwargs)
        
        return funcion_decorada
    return decorador


def requiere_otp_para_documento(f):
    """
    Decorador que valida OTP para acciones en documentos.
    
    Args:
        accion (str): Acción que requiere OTP
    
    Usage:
        @app.route('/api/documentos/<int:documento_id>/eliminar', methods=['DELETE'])
        @requiere_otp_para_documento('eliminar')
        def eliminar_documento(documento_id, usuario_actual, documento):
            pass
    """
    @wraps(f)
    def decorador(*args, **kwargs):
        try:
            # Obtener usuario autenticado
            usuario_id = get_jwt_identity()
            usuario = Usuario.query.get(usuario_id)
            
            if not usuario or not usuario.activo:
                current_app.logger.warning(f"Intento de acceso con usuario inválido: {usuario_id}")
                return jsonify({
                    'error': 'Usuario inválido o inactivo',
                    'codigo': 'USUARIO_INVALIDO'
                }), 401
            # Obtener ID del documento desde diferentes fuentes
            documento_id = (
                kwargs.get('documento_id') or 
                kwargs.get('id') or 
                request.view_args.get('documento_id') or
                request.view_args.get('id')
            )
            if not documento_id:
                current_app.logger.error("No se pudo obtener ID del documento en decorador OTP")
                return jsonify({
                    'error': 'ID de documento requerido',
                    'codigo': 'DOCUMENTO_ID_FALTANTE'
                }), 400
            # Buscar documento
            documento = Documento.query.get(documento_id)
            if not documento or documento.estado != 'activo':
                return jsonify({
                    'error': 'Documento no encontrado o inactivo',
                    'codigo': 'DOCUMENTO_NO_ENCONTRADO'
                }), 404
            
            # Determinar acción basada en el método HTTP y ruta
            accion_map = {
                'GET': 'ver',
                'PUT': 'editar',
                'PATCH': 'editar', 
                'DELETE': 'eliminar',
                'POST': 'crear'
            }
            accion = accion_map.get(request.method, 'ver')
            # Casos especiales basados en la ruta
            endpoint = request.endpoint or ''
            if 'descargar' in endpoint or '/descargar' in request.path:
                accion = 'descargar'
            elif 'actualizar' in endpoint:
                accion = 'editar'
            from models.otp import GestorOTP
            requiere_otp = GestorOTP.requiere_otp_para_accion(
                accion, 
                documento.nivel_seguridad, 
                usuario.rol
            )
            # Log para debug
            current_app.logger.debug(
                f"OTP Check - Usuario: {usuario.email} ({usuario.rol}), "
                f"Documento: {documento.nombre} ({documento.nivel_seguridad}), "
                f"Acción: {accion}, Requiere OTP: {requiere_otp}"
            )
            if not requiere_otp:
                return f(*args, **kwargs)
            # REQUIERE OTP - Validar configuración del usuario
            if not usuario.otp_habilitado:
                current_app.logger.warning(f"Usuario {usuario.email} requiere OTP pero no está configurado")
                return jsonify({
                    'error': 'OTP no configurado',
                    'requiere_configurar_otp': True,
                    'mensaje': 'Esta acción requiere autenticación de dos factores. Configúrala primero.',
                    'endpoint_configuracion': '/api/auth/otp/generar',
                    'accion_solicitada': accion,
                    'documento_id': documento_id
                }), 428  # Precondicion requerida
            # Verificar presencia del código OTP
            codigo_otp = request.headers.get('X-OTP-Code')
            if not codigo_otp:
                current_app.logger.info(f"Código OTP requerido para {accion} en documento {documento_id}")
                return jsonify({
                    'error': 'Código OTP requerido',
                    'requiere_otp_codigo': True,
                    'mensaje': f'Esta acción ({accion}) requiere código de autenticación de dos factores',
                    'accion_solicitada': accion,
                    'documento_id': documento_id,
                    'nivel_seguridad': documento.nivel_seguridad
                }), 428
            # Validar formato del código OTP
            if not codigo_otp.isdigit() or len(codigo_otp) != 6:
                return jsonify({
                    'error': 'Formato de código OTP inválido',
                    'codigo_invalido': True,
                    'mensaje': 'El código debe ser de 6 dígitos numéricos'
                }), 400
            # Validar código OTP
            if not usuario.validar_otp(codigo_otp):
                current_app.logger.warning(
                    f"Código OTP inválido para usuario {usuario.email} "
                    f"en acción {accion} sobre documento {documento_id}"
                )
                return jsonify({
                    'error': 'Código OTP inválido',
                    'codigo_invalido': True,
                    'mensaje': 'El código ingresado es incorrecto o ha expirado',
                    'intentos_restantes': 'Consultar con administrador si persiste'
                }), 401
            current_app.logger.info(
                f"Acción autorizada con OTP - Usuario: {usuario.email}, "
                f"Acción: {accion}, Documento: {documento_id}"
            )
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({
                'error': 'Error interno del servidor',
                'codigo': 'ERROR_OTP_INTERNO',
                'mensaje': 'Contacta al administrador del sistema'
            }), 500
    return decorador


def validar_otp_header(codigo_requerido=True):
    """
    Decorador auxiliar para validar header OTP en endpoints específicos.
    
    Args:
        codigo_requerido (bool): Si True, el código OTP es obligatorio
    """
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            codigo_otp = request.headers.get('X-OTP-Code')
            
            if codigo_requerido and not codigo_otp:
                return jsonify({
                    'error': 'Header X-OTP-Code requerido',
                    'codigo': 'OTP_HEADER_FALTANTE'
                }), 400
            
            if codigo_otp:
                # Validar formato
                if not codigo_otp.isdigit() or len(codigo_otp) != 6:
                    return jsonify({
                        'error': 'Formato de código OTP inválido',
                        'codigo': 'OTP_FORMATO_INVALIDO'
                    }), 400
                
                # Añadir código validado a kwargs para la función
                kwargs['codigo_otp_validado'] = codigo_otp
            
            return f(*args, **kwargs)
        return wrapper
    return decorador


def requiere_otp_condicional(condicion_func):
    """
    Decorador que requiere OTP solo si se cumple una condición específica.
    
    Args:
        condicion_func (callable): Función que retorna True si requiere OTP
    """
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                # Evaluar condición
                if condicion_func(*args, **kwargs):
                    # Aplicar validación OTP
                    return requiere_otp_para_documento(f)(*args, **kwargs)
                else:
                    # Ejecutar sin OTP
                    return f(*args, **kwargs)
            except Exception as e:
                current_app.logger.error(f"Error en OTP condicional: {str(e)}")
                return jsonify({
                    'error': 'Error evaluando condición OTP',
                    'codigo': 'ERROR_OTP_CONDICIONAL'
                }), 500
        return wrapper
    return decorador

def limpiar_qr_usuario(usuario_email):
    """
    Limpiar archivo QR de un usuario específico.
    
    Args:
        usuario_email (str): Email del usuario
        
    Returns:
        bool: True si se limpió exitosamente
    """
    try:
        carpeta_qr = current_app.config.get('QR_FOLDER', 'qr_codes')
        email_sanitizado = usuario_email.replace('@', '_').replace('.', '_')
        archivo_qr = os.path.join(carpeta_qr, f"qr_{email_sanitizado}.png")
        
        if os.path.exists(archivo_qr):
            os.remove(archivo_qr)
            current_app.logger.info(f"QR eliminado para usuario: {usuario_email}")
            return True
        return True  # No existe, consideramos exitoso
    except Exception as e:
        current_app.logger.error(f"Error limpiando QR para {usuario_email}: {str(e)}")
        return False

def verificar_estado_otp_usuario(usuario_id):
    """
    Verificar estado OTP de un usuario específico.
    
    Args:
        usuario_id (int): ID del usuario
        
    Returns:
        dict: Estado OTP del usuario
    """
    try:
        usuario = Usuario.query.get(usuario_id)
        if not usuario:
            return {'error': 'Usuario no encontrado'}
        
        return {
            'otp_habilitado': usuario.otp_habilitado,
            'tiene_clave_base32': bool(usuario.clave_otp_base32),
            'fecha_ultimo_otp': usuario.fecha_ultimo_otp.isoformat() if usuario.fecha_ultimo_otp else None,
            'email': usuario.email
        }
    except Exception as e:
        current_app.logger.error(f"Error verificando estado OTP: {str(e)}")
        return {'error': 'Error interno'}

def validar_contenido_json(campos_requeridos=None):
    """
    Decorador que valida que la request tenga JSON válido y campos requeridos.
    
    Args:
        campos_requeridos (list): Lista de campos que deben estar presentes
    
    Usage:
        @app.route('/api/usuarios', methods=['POST'])
        @validar_contenido_json(['email', 'password', 'nombre_completo'])
        def crear_usuario():
            data = request.get_json()
    """
    def decorador(f):
        @wraps(f)
        def funcion_decorada(*args, **kwargs):
            # Verificar que sea JSON
            if not request.is_json:
                return jsonify({
                    'error': 'Content-Type debe ser application/json',
                    'codigo': 'CONTENT_TYPE_INVALIDO'
                }), 400
            
            try:
                datos = request.get_json()
            except Exception:
                return jsonify({
                    'error': 'JSON inválido',
                    'codigo': 'JSON_INVALIDO'
                }), 400
            
            if not datos:
                return jsonify({
                    'error': 'Cuerpo JSON vacío',
                    'codigo': 'JSON_VACIO'
                }), 400
            
            # Validar campos requeridos
            if campos_requeridos:
                campos_faltantes = []
                for campo in campos_requeridos:
                    if campo not in datos or datos[campo] is None or datos[campo] == '':
                        campos_faltantes.append(campo)
                
                if campos_faltantes:
                    return jsonify({
                        'error': 'Campos requeridos faltantes',
                        'codigo': 'CAMPOS_FALTANTES',
                        'campos_faltantes': campos_faltantes
                    }), 400
            
            return f(*args, **kwargs)
        
        return funcion_decorada
    return decorador


def limitar_frecuencia(maximo_intentos=5, ventana_tiempo=300):
    """
    Decorador simple para limitar frecuencia de requests por IP.
    
    Args:
        maximo_intentos (int): Máximo número de intentos
        ventana_tiempo (int): Ventana de tiempo en segundos
    
    Usage:
        @app.route('/api/auth/login', methods=['POST'])
        @limitar_frecuencia(maximo_intentos=3, ventana_tiempo=600)
        def login():
            pass
    
    Nota: Para producción se recomienda usar Redis o similar para el almacenamiento
    """
    def decorador(f):
        @wraps(f)
        def funcion_decorada(*args, **kwargs):
            from datetime import datetime, timedelta
            
            # Obtener IP del cliente
            ip_cliente = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            
            # Clave para almacenar intentos (en producción usar Redis)
            clave_intento = f"rate_limit_{f.__name__}_{ip_cliente}"
            
            # Para simplicidad, usar app.cache (en producción usar Redis)
            if not hasattr(current_app, '_rate_limit_cache'):
                current_app._rate_limit_cache = {}
            
            cache = current_app._rate_limit_cache
            ahora = datetime.utcnow()
            
            # Limpiar entradas expiradas
            for clave in list(cache.keys()):
                if clave.startswith('rate_limit_') and cache[clave]['expira'] < ahora:
                    del cache[clave]
            
            # Verificar límite actual
            if clave_intento in cache:
                datos_limite = cache[clave_intento]
                if datos_limite['intentos'] >= maximo_intentos:
                    tiempo_restante = int((datos_limite['expira'] - ahora).total_seconds())
                    return jsonify({
                        'error': 'Demasiados intentos. Intenta más tarde.',
                        'codigo': 'LIMITE_FRECUENCIA_EXCEDIDO',
                        'tiempo_restante_segundos': tiempo_restante
                    }), 429
                
                # Incrementar contador
                cache[clave_intento]['intentos'] += 1
            else:
                # Primer intento
                cache[clave_intento] = {
                    'intentos': 1,
                    'expira': ahora + timedelta(seconds=ventana_tiempo)
                }
            
            return f(*args, **kwargs)
        
        return funcion_decorada
    return decorador


def registrar_auditoria(accion):
    """
    Decorador que registra acciones importantes para auditoría.
    
    Args:
        accion (str): Descripción de la acción realizada
    
    Usage:
        @app.route('/api/documentos/<int:documento_id>/eliminar', methods=['DELETE'])
        @registrar_auditoria('eliminar_documento')
        def eliminar_documento():
            pass
    """
    def decorador(f):
        @wraps(f)
        def funcion_decorada(*args, **kwargs):
            # Ejecutar función original
            resultado = f(*args, **kwargs)
            
            try:
                # Obtener información del usuario si está autenticado
                usuario_info = "Anónimo"
                try:
                    verify_jwt_in_request(optional=True)
                    usuario_id = get_jwt_identity()
                    if usuario_id:
                        usuario = Usuario.query.get(usuario_id)
                        usuario_info = f"{usuario.email} (ID: {usuario_id})" if usuario else f"ID: {usuario_id}"
                except:
                    pass
                
                # Obtener información de la request
                ip_cliente = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
                user_agent = request.headers.get('User-Agent', 'Desconocido')
                
                # Log de auditoría
                current_app.logger.info(
                    f"AUDITORIA: {accion} | Usuario: {usuario_info} | "
                    f"IP: {ip_cliente} | Método: {request.method} | "
                    f"URL: {request.url} | User-Agent: {user_agent}"
                )
                
            except Exception as e:
                current_app.logger.error(f"Error registrando auditoría: {str(e)}")
            
            return resultado
        
        return funcion_decorada
    return decorador