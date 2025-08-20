"""
Rate limiting, compresión HTTP y middleware de performance
"""
import time
from functools import wraps
from flask import request, g, current_app, jsonify
from flask_compress import Compress

# Solo compresión por ahora, rate limiting opcional
compress = Compress()

class GestorRateLimitingSimple:
    """
    Gestor de rate limiting simple sin dependencias externas
    Implementación básica para desarrollo
    """
    
    def __init__(self, app=None):
        self.app = app
        self.requests_store = {}  # Almacenamiento en memoria
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa rate limiting simple"""
        
        def manejar_limite_excedido():
            """Maneja cuando se excede el límite"""
            current_app.logger.warning(
                f"Rate limit excedido: {request.remote_addr} - {request.endpoint}"
            )
            
            return jsonify({
                'error': 'Límite de solicitudes excedido',
                'mensaje': 'Has realizado demasiadas solicitudes. Intenta nuevamente más tarde.',
                'retry_after': 60
            }), 429
        
        app._rate_limiter = self
        app.logger.info("Sistema de rate limiting simple inicializado")
    
    def verificar_limite(self, clave, limite_por_minuto=10):
        """
        Verifica si se ha excedido el límite para una clave
        
        Args:
            clave: Identificador único
            limite_por_minuto: Límite de requests por minuto
        
        Returns:
            bool: True si está dentro del límite
        """
        import time
        ahora = time.time()
        minuto_actual = int(ahora // 60)
        
        if clave not in self.requests_store:
            self.requests_store[clave] = {}
        
        # Limpiar minutos antiguos
        for minuto in list(self.requests_store[clave].keys()):
            if minuto < minuto_actual - 1:  # Mantener solo último minuto
                del self.requests_store[clave][minuto]
        
        # Contar requests en el minuto actual
        count_actual = self.requests_store[clave].get(minuto_actual, 0)
        
        if count_actual >= limite_por_minuto:
            return False
        
        # Incrementar contador
        self.requests_store[clave][minuto_actual] = count_actual + 1
        return True

class GestorCompresion:
    """
    Gestor de compresión HTTP inteligente
    """
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa la compresión HTTP con la app Flask"""
        
        # Configurar compresión con parámetros optimizados
        compress.init_app(app)
        
        # Configurar tipos MIME para comprimir
        if hasattr(app.config, 'COMPRESS_MIMETYPES'):
            app.config['COMPRESS_MIMETYPES'] = app.config['COMPRESS_MIMETYPES']
        
        app.logger.info("Sistema de compresión HTTP inicializado")

def limite_simple(limite_por_minuto=10):
    """
    Decorador simple de rate limiting
    
    Args:
        limite_por_minuto: Límite de requests por minuto
    """
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generar clave única por IP y endpoint
            clave = f"{request.remote_addr}:{request.endpoint}"
            
            # Verificar límite si el rate limiter está disponible
            if hasattr(current_app, '_rate_limiter'):
                if not current_app._rate_limiter.verificar_limite(clave, limite_por_minuto):
                    return jsonify({
                        'error': 'Límite de solicitudes excedido',
                        'mensaje': 'Has realizado demasiadas solicitudes. Intenta nuevamente más tarde.',
                        'retry_after': 60
                    }), 429
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorador

def limite_por_rol_simple(limites_por_rol):
    """
    Decorador simple para límites por rol
    
    Args:
        limites_por_rol: Dict con límites por rol
    """
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Obtener rol del usuario actual
            rol_usuario = 'anonimo'
            if hasattr(g, 'usuario_actual') and g.usuario_actual:
                rol_usuario = g.usuario_actual.rol
            
            # Obtener límite para el rol
            limite = limites_por_rol.get(rol_usuario, limites_por_rol.get('default', 10))
            
            # Aplicar límite
            clave = f"{request.remote_addr}:{request.endpoint}:{rol_usuario}"
            
            if hasattr(current_app, '_rate_limiter'):
                if not current_app._rate_limiter.verificar_limite(clave, limite):
                    return jsonify({
                        'error': 'Límite de solicitudes excedido',
                        'mensaje': f'Límite para rol {rol_usuario} excedido. Intenta más tarde.',
                        'retry_after': 60
                    }), 429
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorador

class MiddlewarePerformance:
    """
    Middleware para medir performance de requests automáticamente
    """
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Registra middleware de performance"""
        
        @app.before_request
        def antes_request():
            """Registra inicio del request"""
            g.tiempo_inicio = time.time()
            g.endpoint_actual = request.endpoint
        
        @app.after_request
        def despues_request(response):
            """Registra fin del request y métricas"""
            
            if hasattr(g, 'tiempo_inicio'):
                tiempo_total = (time.time() - g.tiempo_inicio) * 1000  # ms
                
                # Registrar si es lento (>500ms)
                if tiempo_total > 500:
                    current_app.logger.warning(
                        f"Request lento: {g.endpoint_actual} - {tiempo_total:.2f}ms"
                    )
                
                # Agregar header de tiempo de respuesta
                response.headers['X-Response-Time'] = f"{tiempo_total:.2f}ms"
            
            return response
        
        app.logger.info("Middleware de performance inicializado")

class MiddlewareSeguridad:
    """
    Middleware adicional de seguridad
    """
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Registra headers de seguridad"""
        
        @app.after_request
        def agregar_headers_seguridad(response):
            """Agrega headers de seguridad a todas las respuestas"""
            
            # Headers de seguridad estándar
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            
            
            return response
        
        app.logger.info("Middleware de seguridad inicializado")

# Instancias globales de los gestores
gestor_rate_limiting = GestorRateLimitingSimple()
gestor_compresion = GestorCompresion()
middleware_performance = MiddlewarePerformance()
middleware_seguridad = MiddlewareSeguridad()

# Decoradores específicos para endpoints comunes
def limite_auth():
    """Límite específico para endpoints de autenticación"""
    return limite_simple(5)  # 5 per minute

def limite_upload():
    """Límite específico para subida de archivos"""
    return limite_por_rol_simple({
        'usuario': 5,
        'supervisor': 10, 
        'admin': 20,
        'default': 2
    })

def limite_api_general():
    """Límite general para endpoints de API"""
    return limite_por_rol_simple({
        'usuario': 30,
        'supervisor': 60,
        'admin': 100, 
        'default': 10
    })

def limite_otp():
    """Límite específico para generación de OTP"""
    return limite_simple(3)  # 3 per minute

class MonitorRateLimiting:
    """
    Clase para monitorear el uso del rate limiting
    """
    
    @staticmethod
    def obtener_estadisticas_rate_limiting():
        """
        Obtiene estadísticas del rate limiting
        """
        return {
            'tipo_storage': 'Memoria local (desarrollo)',
            'estado': 'Activo',
            'implementacion': 'Rate limiting simple'
        }
    
    @staticmethod
    def obtener_limites_configurados():
        """
        Obtiene la configuración actual de límites
        """
        return {
            'limite_por_defecto': '10 por minuto',
            'limites_especificos': {
                'auth': '5 por minuto',
                'upload': 'Por rol (2-20 por minuto)',
                'api_general': 'Por rol (10-100 por minuto)',
                'otp': '3 por minuto'
            },
            'habilitado': True,
            'storage': 'Memoria local'
        }