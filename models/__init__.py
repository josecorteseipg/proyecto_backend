"""
Paquete de modelos para el Sistema de Gestión de Documentos Seguros.

Este paquete contiene todos los modelos de datos del sistema:
- Usuario: Gestión de usuarios, roles y autenticación
- Documento: Gestión de documentos con niveles de seguridad
- OTP: Sistema de autenticación de doble factor

Uso:
    from models import Usuario, Documento, db, bcrypt
    from models.otp import GestorOTP
"""

# Importaciones principales de los modelos
from .usuario import Usuario, db, bcrypt, crear_usuario_admin_inicial, crear_usuarios_prueba
from .documento import Documento, buscar_documentos, obtener_documentos_por_nivel_seguridad
from .otp import GestorOTP, generar_otp, validar_otp

# Exponer las clases principales para facilitar importaciones
__all__ = [
    # Modelos principales
    'Usuario',
    'Documento',
    
    # Instancias de extensiones
    'db',
    'bcrypt',
    
    # Clase gestora OTP
    'GestorOTP',
    
    # Funciones de utilidad
    'crear_usuario_admin_inicial',
    'crear_usuarios_prueba',
    'buscar_documentos',
    'obtener_documentos_por_nivel_seguridad',
    
    # Funciones de compatibilidad OTP
    'generar_otp',
    'validar_otp'
]

def inicializar_base_datos(app):
    """
    Inicializa la base de datos y crea las tablas necesarias.
    
    Args:
        app: Instancia de la aplicación Flask
    """
    with app.app_context():
        # Crear todas las tablas
        db.create_all()
        
        # Crear usuario administrador inicial
        crear_usuario_admin_inicial()
        
        # En modo desarrollo, crear usuarios de prueba
        if app.config.get('DEBUG', False):
            crear_usuarios_prueba()
        
        app.logger.info("Base de datos inicializada correctamente")


def obtener_estadisticas_sistema():
    """
    Obtiene estadísticas generales del sistema.
    
    Returns:
        dict: Estadísticas del sistema
    """
    total_usuarios = Usuario.query.count()
    usuarios_activos = Usuario.query.filter_by(activo=True).count()
    
    total_documentos = Documento.query.count()
    documentos_publicos = Documento.query.filter_by(nivel_seguridad='publico').count()
    documentos_confidenciales = Documento.query.filter_by(nivel_seguridad='confidencial').count()
    documentos_secretos = Documento.query.filter_by(nivel_seguridad='secreto').count()
    
    usuarios_con_otp = Usuario.query.filter_by(otp_habilitado=True).count()
    
    return {
        'usuarios': {
            'total': total_usuarios,
            'activos': usuarios_activos,
            'con_otp': usuarios_con_otp
        },
        'documentos': {
            'total': total_documentos,
            'publicos': documentos_publicos,
            'confidenciales': documentos_confidenciales,
            'secretos': documentos_secretos
        }
    }