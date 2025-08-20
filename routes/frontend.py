from flask import Blueprint, render_template, redirect, url_for, request
from functools import wraps
import jwt
from config import Config

# Crear blueprint para rutas frontend
frontend_bp = Blueprint('frontend', __name__)

def verificar_token_opcional(f):
    """
    Decorador para verificar token JWT de forma opcional
    No bloquea el acceso si no hay token
    """
    @wraps(f)
    def funcion_decorada(*args, **kwargs):
        token = None
        usuario_autenticado = False
        
        # Buscar token en headers de autorización
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if token:
            try:
                # Verificar token
                payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
                usuario_autenticado = True
            except jwt.ExpiredSignatureError:
                usuario_autenticado = False
            except jwt.InvalidTokenError:
                usuario_autenticado = False
        
        # Pasar información de autenticación al template
        kwargs['usuario_autenticado'] = usuario_autenticado
        return f(*args, **kwargs)
    
    return funcion_decorada

@frontend_bp.route('/')
def inicio():
    """
    Página de inicio - siempre mostrar dashboard, JS maneja autenticación
    """
    return render_template('dashboard/documentos.html')

@frontend_bp.route('/login')
def login():
    """
    Página de login - no verificar autenticación server-side
    """
    return render_template('auth/login.html')

@frontend_bp.route('/dashboard')
def dashboard():
    """
    Dashboard principal - autenticación manejada por JavaScript
    """
    return render_template('dashboard/documentos.html')

@frontend_bp.route('/documentos')
@verificar_token_opcional
def documentos(usuario_autenticado=False):
    """
    Página de gestión de documentos (alias del dashboard)
    """
    if not usuario_autenticado:
        return redirect(url_for('frontend.login'))
    
    return render_template('dashboard/documentos.html')

# ===== MANEJO DE ERRORES =====

@frontend_bp.errorhandler(404)
def pagina_no_encontrada(error):
    """
    Página de error 404 personalizada
    """
    return render_template('errores/404.html'), 404

@frontend_bp.errorhandler(500)
def error_servidor(error):
    """
    Página de error 500 personalizada
    """
    return render_template('errores/500.html'), 500

# ===== RUTAS DE UTILIDAD =====

@frontend_bp.route('/salud')
def salud_frontend():
    """
    Endpoint de salud para verificar que el frontend está funcionando
    """
    return {
        'estado': 'ok',
        'servicio': 'frontend',
        'mensaje': 'Frontend funcionando correctamente'
    }

@frontend_bp.route('/info')
def info_aplicacion():
    """
    Información básica de la aplicación
    """
    return {
        'nombre': 'Sistema de Gestión de Documentos Seguros',
        'version': '2.1.0',
        'descripcion': 'Sistema web para gestión segura de documentos',
        'tecnologias': {
            'backend': 'Flask + Python',
            'frontend': 'Bootstrap 5 + JavaScript',
            'base_datos': 'SQLite',
            'autenticacion': 'JWT + OTP'
        },
        'funcionalidades': [
            'Autenticación JWT con roles',
            'Sistema OTP para acciones sensibles',
            'CRUD completo de documentos',
            'Gestión de archivos por nivel de seguridad',
            'Búsqueda y filtros avanzados'
        ]
    }