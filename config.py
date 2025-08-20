import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'IPG_BACKEND_JLC_IPG2025'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///documentos.db'
    # Subida de archivos
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png', 'xlsx', 'pptx'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB máx
    # JWT Configuración
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'IPG_BACKEND_JLC_IPG2025'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_ALGORITHM = 'HS256'
    # Sistema de caché
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutos
    # Caché fallback por si Redis no esta disponible
    CACHE_FALLBACK_TYPE = 'simple'
    CACHE_FALLBACK_TIMEOUT = 180  # 3 minutos
    # Rate Limiting avanzado
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/1'
    RATELIMIT_DEFAULT = "100 per hour"
    RATELIMIT_ENABLED = True
    # Rate limits específicos por endpoint
    RATELIMIT_CONFIGURACION = {
        'auth_login': "5 per minute",
        'documentos_upload': "10 per minute", 
        'documentos_list': "60 per minute",
        'otp_generar': "3 per minute",
        'api_general': "200 per hour"
    }
    # Compresión HTTP
    COMPRESS_MIMETYPES = [
        'text/html', 'text/css', 'text/xml', 'text/javascript',
        'application/json', 'application/javascript', 'application/xml',
        'application/rss+xml', 'application/atom+xml', 'image/svg+xml'
    ]
    COMPRESS_LEVEL = 6
    COMPRESS_MIN_SIZE = 500  # bytes
    # Logs
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE_PATH = 'logs/sistema_documentos.log'
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    # Auditoría y monitoreo
    AUDITORIA_HABILITADA = True
    METRICAS_HABILITADAS = True
    MONITOREO_PERFORMANCE = True
    # Configuración de sesiones optimizada
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE = False  # True en producción
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Funcionalidad OTP
    OTP_ISSUER_NAME = "IPG_Backend"
    OTP_EXPIRATION_TIME = 300  # 5 minutos
    QR_FOLDER = os.path.join(os.getcwd(), 'qr_codes')  # Carpeta para QR codes
    NIVELES_SEGURIDAD = ['publico', 'confidencial', 'secreto']
    ROLES_USUARIO = ['usuario', 'supervisor', 'admin']
    CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:5000"]
    @staticmethod
    def init_app(app):
        """Inicialización de configuración específica"""
        # Crear carpetas necesarias
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['QR_FOLDER'], exist_ok=True)


class ConfiguracionDesarrollo(Config):
    """Configuración para entorno de desarrollo"""
    DEBUG = True
    SQLALCHEMY_ECHO = True  # Mostrar queries SQL en desarrollo
    CACHE_DEFAULT_TIMEOUT = 60  # 1 minuto
    RATELIMIT_ENABLED = False
    LOG_LEVEL = 'DEBUG'
class ConfiguracionProduccion(Config):
    """Configuración para producción"""
    DEBUG = False    
    CACHE_DEFAULT_TIMEOUT = 900  # 15 minutos    
    # Rate limiting estricto
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = "50 per hour"    
    # Compresión máxima
    COMPRESS_LEVEL = 9    
    # Sesiones seguras
    SESSION_COOKIE_SECURE = True    
    # Logging optimizado
    LOG_LEVEL = 'WARNING'

configuraciones = {
    'desarrollo': ConfiguracionDesarrollo,
    'produccion': ConfiguracionProduccion,
    'default': ConfiguracionDesarrollo
}

def obtener_configuracion(nombre_entorno=None):
    """
    Obtiene la configuración según el entorno
    """
    if not nombre_entorno:
        nombre_entorno = os.environ.get('FLASK_ENV', 'default')
    
    return configuraciones.get(nombre_entorno, ConfiguracionDesarrollo)