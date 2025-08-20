"""
Sistema de Gestión de Documentos Seguros
Aplicación principal Flask con autenticación JWT y sistema OTP
Autor: José Luis Cortese
Asignatura: Backend - IPG 2025
"""

import os
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_migrate import Migrate
from sqlalchemy import text
from datetime import datetime

# Importar configuración
from config import obtener_configuracion
# Importar sistemas de optimización
from utils.cache_simple import gestor_cache
from utils.sistema_loggin import gestor_logging
from utils.middleware_optimizacion import (
    gestor_compresion,middleware_performance, middleware_seguridad,gestor_rate_limiting
)

# Importar modelos y utilidades
from models import db, bcrypt, inicializar_base_datos, obtener_estadisticas_sistema
from models.usuario import Usuario

# Importar blueprints/rutas
from routes.auth import auth_bp
from routes.documentos import documentos_bp
from routes.frontend import frontend_bp
from routes.monitoreo import monitoreo_bp

def crear_aplicacion(config_name=None):
    """
    Crear y configurar la aplicación Flask.
    
    Args:
        config_name (str): Nombre de la configuración a usar
    
    Returns:
        Flask: Instancia de aplicación configurada
    """
    
    # Crear instancia Flask
    app = Flask(__name__, template_folder='plantillas')
    
    # Determinar configuración
    if not config_name:
        config_name = os.environ.get('FLASK_ENV', 'desarrollo')
    
    # Cargar configuración
    configuracion = obtener_configuracion(config_name)
    app.config.from_object(configuracion)
    
    # Inicializar configuración específica
    configuracion.init_app(app)
    
    # Inicializar extensiones
    inicializar_extensiones(app)
    
    # Registrar blueprints
    registrar_blueprints(app)
    
    # Configurar manejo de errores
    configurar_manejo_errores(app)

    # Sistema de caché
    gestor_cache.init_app(app)    
    # Sistema de logging avanzado
    gestor_logging.init_app(app)
    gestor_rate_limiting.init_app(app)
    
    # Rate limiting granular
    if app.config.get('RATELIMIT_ENABLED', True):
        gestor_rate_limiting.init_app(app)
    # Compresión HTTP
    gestor_compresion.init_app(app)    
    # Middleware de performance
    middleware_performance.init_app(app)
    # Middleware de seguridad
    middleware_seguridad.init_app(app)
   
    # Crear base de datos y datos iniciales
    with app.app_context():
        inicializar_base_datos(app)
    
    # Log de inicio
    app.logger.info(f"Aplicación iniciada en modo: {config_name}")
    
    return app


def inicializar_extensiones(app):
    """
    Inicializa todas las extensiones Flask.
    
    Args:
        app: Instancia de aplicación Flask
    """
    
    # Base de datos
    db.init_app(app)
    
    # Bcrypt para hashing de contraseñas
    bcrypt.init_app(app)
    
    # JWT Manager
    jwt = JWTManager(app)
    configurar_jwt(jwt, app)
    
    # CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config.get('CORS_ORIGINS', ["http://localhost:3000"]),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-OTP-Code"]
        }
    })

    migrate = Migrate(app, db)

def configurar_jwt(jwt, app):
    """
    Configura JWT Manager con callbacks personalizados.
    
    Args:
        jwt: Instancia de JWTManager
        app: Instancia de aplicación Flask
    """
    
    @jwt.user_identity_loader
    def user_identity_lookup(usuario):
        """Define qué usar como identidad en el token"""
        if hasattr(usuario, 'id'):
            return str(usuario.id)  # CONVERTIR A STRING
        return str(usuario)
    
    
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """Callback para cargar usuario desde token"""
        identity = jwt_data["sub"]
        return Usuario.query.get(int(identity))
    
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        """Callback para tokens expirados"""
        return jsonify({
            'error': 'Token expirado',
            'codigo': 'TOKEN_EXPIRADO'
        }), 401
    
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        """Callback para tokens inválidos"""
        return jsonify({
            'error': 'Token inválido',
            'codigo': 'TOKEN_INVALIDO',
            'debug_error': str(error)
        }), 401
    
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        """Callback para requests sin token"""
        return jsonify({
            'error': 'Token de autorización requerido',
            'codigo': 'TOKEN_REQUERIDO'
        }), 401
    
    
    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        """Callback para tokens revocados"""
        return jsonify({
            'error': 'Token revocado',
            'codigo': 'TOKEN_REVOCADO'
        }), 401


def registrar_blueprints(app):
    """
    Registra todos los blueprints de la aplicación.
    
    Args:
        app: Instancia de aplicación Flask
    """
    
    # Blueprint de autenticación
    app.register_blueprint(auth_bp)
    app.register_blueprint(documentos_bp)
    app.register_blueprint(frontend_bp)
    app.register_blueprint(monitoreo_bp)

    # Ruta raíz de la API
    @app.route('/api')
    def api_info():
        """Información básica de la API"""
        return jsonify({
            'mensaje': 'Sistema de Gestión de Documentos Seguros',
            'version': '3.0.0',
            'estado': 'operativo',
            'autor': 'José Luis Cortese',
            'funcionalidades': [
                'Autenticación JWT + OTP',
                'CRUD Documentos con niveles de seguridad',
                'Sistema de roles y permisos',
                'Frontend web responsive',
                'Sistema de caché inteligente',
                'Rate limiting granular',
                'Logging y auditoría avanzada',
                'Compresión HTTP automática',
                'Monitoreo de performance'
            ],
            'optimizaciones_activas': {
                'cache': app.config.get('CACHE_TYPE', 'Desconocido'),
                'compresion': True,
                'rate_limiting': app.config.get('RATELIMIT_ENABLED', False),
                'logging_avanzado': True,
                'middleware_performance': True,
                'headers_seguridad': True
            },
            'endpoints': {
                'autenticacion': '/api/auth',
                'documentos': '/api/documentos',
                'monitoreo': '/api/monitoreo/*'
            },
            'fechahora': datetime.utcnow().isoformat()
        })
    
    
    # Ruta de salud del sistema
    @app.route('/api/health')
    def health_check():
        """Verificación de estado del sistema"""
        try:
            # Verificar conexión a base de datos
            db.session.execute(text('SELECT 1'))
            # Obtener estadísticas básicas
            stats = obtener_estadisticas_sistema()
            cache_activo = hasattr(app, 'extensions') and 'cache' in app.extensions
            
            return jsonify({
                'estado': 'operativa',
                'base_datos': 'conectada',
                'timestamp': datetime.utcnow().isoformat(),
                'estadisticas': stats,
                'optimizaciones': {
                    'cache': 'activo' if cache_activo else 'inactivo',
                    'rate_limiting': 'activo' if app.config.get('RATELIMIT_ENABLED') else 'inactivo',
                    'compresion': 'activo',
                    'logging': 'activo'
                },
            }), 200
            
        except Exception as e:
            app.logger.error(f"Error en health check: {str(e)}")
            return jsonify({
                'estado': 'error',
                'base_datos': 'desconectada',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 500
    
    


def configurar_manejo_errores(app):
    """
    Configura manejadores de errores personalizados.
    
    Args:
        app: Instancia de aplicación Flask
    """
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Solicitud inválida',
            'codigo': 'BAD_REQUEST',
            'descripcion': str(error.description) if hasattr(error, 'description') else None
        }), 400
    
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'error': 'No autorizado',
            'codigo': 'UNAUTHORIZED',
            'descripcion': 'Credenciales inválidas o token requerido'
        }), 401
    
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'error': 'Acceso denegado',
            'codigo': 'FORBIDDEN',
            'descripcion': 'No tienes permisos para realizar esta acción'
        }), 403
    
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Recurso no encontrado',
            'codigo': 'NOT_FOUND',
            'descripcion': 'El recurso solicitado no existe'
        }), 404
    
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'error': 'Método no permitido',
            'codigo': 'METHOD_NOT_ALLOWED',
            'descripcion': f'Método {request.method} no permitido para esta ruta'
        }), 405
    
    
    @app.errorhandler(413)
    def payload_too_large(error):
        return jsonify({
            'error': 'Archivo demasiado grande',
            'codigo': 'PAYLOAD_TOO_LARGE',
            'descripcion': 'El archivo excede el tamaño máximo permitido'
        }), 413
    
    
    @app.errorhandler(422)
    def unprocessable_entity(error):
        return jsonify({
            'error': 'Datos no procesables',
            'codigo': 'UNPROCESSABLE_ENTITY',
            'descripcion': 'Los datos enviados no pueden ser procesados'
        }), 422
    
    
    @app.errorhandler(429)
    def too_many_requests(error):
        return jsonify({
            'error': 'Demasiadas solicitudes',
            'codigo': 'TOO_MANY_REQUESTS',
            'descripcion': 'Has excedido el límite de solicitudes'
        }), 429
    
    
    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({
            'error': 'Error interno del servidor',
            'codigo': 'INTERNAL_SERVER_ERROR',
            'descripcion': 'Ha ocurrido un error interno'
        }), 500
    
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        return jsonify({
            'error': 'Error inesperado',
            'codigo': 'UNEXPECTED_ERROR',
            'descripcion': 'Ha ocurrido un error inesperado'
        }), 500


def crear_usuarios_iniciales():
    """
    Crea usuarios iniciales para desarrollo y testing.
    Se ejecuta automáticamente en modo desarrollo.
    """
    try:
        from models.usuario import crear_usuarios_prueba
        crear_usuarios_prueba()
        print("Usuarios de prueba creados exitosamente")
    except Exception as e:
        print(f"Error creando usuarios iniciales: {str(e)}")


def mostrar_informacion_inicio(app):
    print("\n" + "="*60)
    print("SISTEMA DE GESTIÓN DE DOCUMENTOS SEGUROS")
    print("Fase Final: CRUD Documentos Completo")
    print("="*60)
    print(f"Modo: {app.config.get('ENV', 'desarrollo')}")
    print(f"Base de datos: {app.config.get('SQLALCHEMY_DATABASE_URI', 'No configurada')}")    
    print(f"Carpeta uploads: {app.config.get('UPLOAD_FOLDER', 'uploads')}")
    print(f"QR codes: {app.config.get('QR_FOLDER', 'qr_codes')}")
    
    print("="*60 + "\n")


# ===============================
# PUNTO DE ENTRADA PRINCIPAL
# ===============================

if __name__ == '__main__':
    # Obtener entorno desde variable de entorno
    entorno = os.environ.get('FLASK_ENV', 'desarrollo')
    # Crear aplicación
    app = crear_aplicacion(entorno)
    
    # Mostrar información de inicio en modo desarrollo
    if app.config.get('DEBUG', False):
        mostrar_informacion_inicio(app)
    # Configuración de ejecución
    debug_mode = app.config.get('DEBUG', True)
    puerto = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    app.logger.info(f"Iniciando aplicación en modo {entorno}")
    app.logger.info(f"Servidor: http://{host}:{puerto}")
    app.logger.info("Monitoreo disponible en /api/monitoreo/")

    # Ejecutar aplicación
    try:
        app.run(
            host=host,
            port=puerto,
            debug=debug_mode,
        )
    except KeyboardInterrupt:
        print("\nSistema detenido")
    except Exception as e:
        print(f"\nError de aplicación: {str(e)}")
        exit(1)