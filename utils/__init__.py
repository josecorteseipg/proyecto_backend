"""
Paquete de utilidades para el Sistema de Gestión de Documentos Seguros.

Este paquete contiene:
- decoradores: Middleware de autenticación, roles y validaciones
- validaciones: Funciones para validar datos de entrada

Uso:
    from utils.decoradores import requiere_autenticacion, requiere_rol
    from utils.validaciones import ValidadorDatos, validar_datos_usuario
"""

# Importaciones principales de decoradores
from .decoradores import (
    requiere_autenticacion,
    requiere_rol,
    requiere_admin,
    requiere_supervisor_o_admin,
    validar_acceso_documento,
    requiere_otp_para_documento,
    validar_contenido_json,
    limitar_frecuencia,
    registrar_auditoria
)

# Importaciones principales de validaciones
from .validaciones import (
    ValidadorDatos,
    validar_datos_usuario,
    validar_datos_documento
)

# Exponer las funciones principales para facilitar importaciones
__all__ = [
    # Decoradores de autenticación y autorización
    'requiere_autenticacion',
    'requiere_rol',
    'requiere_admin',
    'requiere_supervisor_o_admin',
    'validar_acceso_documento',
    'requiere_otp_para_documento',
    
    # Decoradores de validación
    'validar_contenido_json',
    'limitar_frecuencia',
    'registrar_auditoria',
    
    # Validadores
    'ValidadorDatos',
    'validar_datos_usuario',
    'validar_datos_documento'
]