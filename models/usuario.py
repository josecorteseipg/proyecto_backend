from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask import current_app
from datetime import datetime
from flask_jwt_extended import create_access_token, create_refresh_token
import re
# Instancias que se inicializarán en app.py
db = SQLAlchemy()
bcrypt = Bcrypt()

class Usuario(db.Model):
    """
    Modelo Usuario para el sistema de gestión de documentos seguros.
    Incluye autenticación, roles y integración con sistema OTP.
    """
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    nombre_completo = db.Column(db.String(200), nullable=False)
    # Sistema de roles
    rol = db.Column(db.String(20), nullable=False, default='usuario')  # usuario, supervisor, admin
    activo = db.Column(db.Boolean, default=True, nullable=False)
    # Campos de seguimiento
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_ultimo_acceso = db.Column(db.DateTime)
    intentos_login_fallidos = db.Column(db.Integer, default=0)
    # Integración OTP
    clave_otp_base32 = db.Column(db.String(64))  # Clave base32 para OTP
    otp_habilitado = db.Column(db.Boolean, default=False)
    fecha_ultimo_otp = db.Column(db.DateTime)
    # Campos adicionales de seguridad
    requiere_cambio_password = db.Column(db.Boolean, default=False)
    fecha_ultimo_cambio_password = db.Column(db.DateTime, default=datetime.utcnow)
    # Relaciones
    documentos_propios = db.relationship('Documento', backref='propietario', lazy='dynamic', 
                                       foreign_keys='Documento.propietario_id')
    def __repr__(self):
        return f'<Usuario {self.email}>'
    # ===============================
    # MÉTODOS DE AUTENTICACIÓN
    # ===============================
    
    def establecer_password(self, password_plano):
        """
        Genera hash seguro de la contraseña usando bcrypt.
        
        Args:
            password_plano (str): Contraseña en texto plano
        """
        if not password_plano or len(password_plano) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        
        self.password_hash = bcrypt.generate_password_hash(password_plano).decode('utf-8')
        self.fecha_ultimo_cambio_password = datetime.utcnow()
        self.requiere_cambio_password = False
        self.intentos_login_fallidos = 0
    def verificar_password(self, password_plano):
        """
        Verifica si la contraseña proporcionada es correcta.
        
        Args:
            password_plano (str): Contraseña a verificar
        
        Returns:
            bool: True si la contraseña es correcta
        """
        if not password_plano or not self.password_hash:
            return False
        
        return bcrypt.check_password_hash(self.password_hash, password_plano)
    def generar_tokens_jwt(self):
        """
        Genera tokens JWT de acceso y refresco para el usuario.
        
        Returns:
            dict: Diccionario con access_token y refresh_token
        """
        # Información adicional en el token
        claims_adicionales = {
            'rol': self.rol,
            'nombre': self.nombre_completo,
            'otp_habilitado': self.otp_habilitado
        }
        
        access_token = create_access_token(
            identity=self.id,
            additional_claims=claims_adicionales
        )
        
        refresh_token = create_refresh_token(identity=self.id)
        
        # Actualizar último acceso
        self.fecha_ultimo_acceso = datetime.utcnow()
        self.intentos_login_fallidos = 0
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'usuario': {
                'id': self.id,
                'email': self.email,
                'nombre_completo': self.nombre_completo,
                'rol': self.rol
            }
        }
    # ===============================
    # MÉTODOS DE ROLES Y PERMISOS
    # ===============================
    
    def es_admin(self):
        """Verifica si el usuario es administrador"""
        return self.rol == 'admin'
    
    
    def es_supervisor(self):
        """Verifica si el usuario es supervisor o admin"""
        return self.rol in ['supervisor', 'admin']
    
    
    def puede_acceder_documento(self, documento):
        """
        Verifica si el usuario puede acceder a un documento según su rol y nivel de seguridad.
        
        Args:
            documento: Instancia del modelo Documento
        
        Returns:
            bool: True si puede acceder
        """
        # Admin puede acceder a todo
        if self.es_admin():
            return True
        
        # Propietario puede acceder a sus documentos
        if documento.propietario_id == self.id:
            return True
        
        # Documentos públicos son accesibles por todos
        if documento.nivel_seguridad == 'publico':
            return True
        
        # Supervisores pueden acceder a documentos confidenciales
        if self.es_supervisor() and documento.nivel_seguridad == 'confidencial':
            return True
        
        # Por defecto, no puede acceder
        return False
    
    
    def puede_modificar_documento(self, documento):
        """
        Verifica si el usuario puede modificar un documento.
        
        Args:
            documento: Instancia del modelo Documento
        
        Returns:
            bool: True si puede modificar
        """
        # Admin puede modificar todo
        if self.es_admin():
            return True
        
        # Propietario puede modificar sus documentos
        if documento.propietario_id == self.id:
            return True
        
        # Supervisores pueden modificar documentos no secretos
        if self.es_supervisor() and documento.nivel_seguridad != 'secreto':
            return True
        
        return False
    
    
    def puede_eliminar_documento(self, documento):
        """
        Verifica si el usuario puede eliminar un documento.
        
        Args:
            documento: Instancia del modelo Documento
        
        Returns:
            bool: True si puede eliminar
        """
        # Solo admin y propietario pueden eliminar
        return self.es_admin() or documento.propietario_id == self.id
    
    
    # ===============================
    # MÉTODOS DE INTEGRACIÓN OTP
    # ===============================
    
    def configurar_otp(self):
        """
        Configura OTP para el usuario generando nueva clave base32.
        
        Returns:
            dict: Datos OTP generados (clave, QR, etc.)
        """
        from .otp import GestorOTP
        
        datos_otp = GestorOTP.generar_otp_para_usuario(self.email, self.nombre_completo)
        
        if datos_otp:
            self.clave_otp_base32 = datos_otp['clave_base32']
            self.otp_habilitado = False
            
            return datos_otp
        
        return None
    
    
    def activar_otp_con_validacion(self, codigo_validacion):
        """
        Activa OTP después de validar código inicial.
        
        Args:
            codigo_validacion (str): Código de 6 dígitos para validar
            
        Returns:
            bool: True si se activó correctamente
        """
        if not self.clave_otp_base32:
            return False
            
        if self.validar_otp(codigo_validacion):
            self.otp_habilitado = True
            self.fecha_ultimo_otp = datetime.utcnow()
            db.session.commit()
            return True
        
        return False
    def validar_otp(self, codigo_otp):
        """
        Valida un código OTP para este usuario.
        
        Args:
            codigo_otp (str): Código OTP a validar
        
        Returns:
            bool: True si el código es válido
        """
        if not self.otp_habilitado or not self.clave_otp_base32:
            return False
        
        from .otp import GestorOTP
        
        resultado = GestorOTP.validar_otp_codigo(codigo_otp, self.clave_otp_base32)
        
        if resultado['es_valido']:
            self.fecha_ultimo_otp = datetime.utcnow()
            db.session.commit()
            return True
        
        return False
    
    
    def validar_otp_con_debug(self, codigo_otp):
        """
        Validar OTP con logging detallado para debugging.
        """
        try:
            
            if not self.clave_otp_base32:
                current_app.logger.error(f"Usuario {self.email} no tiene clave base32")
                return False
            
            from .otp import GestorOTP
            
            # Usar función del gestor con debug
            resultado = GestorOTP.validar_otp_codigo(codigo_otp, self.clave_otp_base32)
            
            current_app.logger.info(f"Resultado GestorOTP: {resultado}")
            
            if resultado.get('es_valido'):
                self.fecha_ultimo_otp = datetime.utcnow()
                return True
            
            return False
            
        except Exception as e:
            current_app.logger.error(f"Error validando OTP para {self.email}: {str(e)}", exc_info=True)
            return False
    def requiere_otp_para(self, accion, nivel_seguridad):
        """
        Determina si este usuario requiere OTP para una acción específica.
        
        Args:
            accion (str): Acción a realizar
            nivel_seguridad (str): Nivel de seguridad del documento
        
        Returns:
            bool: True si requiere OTP
        """
        from .otp import GestorOTP
        
        return GestorOTP.requiere_otp_para_accion(accion, nivel_seguridad, self.rol)
    
    
    # ===============================
    # MÉTODOS DE SEGURIDAD
    # ===============================
    
    def registrar_intento_fallido(self):
        """Registra un intento de login fallido"""
        self.intentos_login_fallidos += 1
        db.session.commit()
    
    
    def esta_bloqueado(self):
        """Verifica si la cuenta está bloqueada por intentos fallidos"""
        return self.intentos_login_fallidos >= 5
    
    
    def desbloquear_cuenta(self):
        """Desbloquea la cuenta reseteando intentos fallidos"""
        self.intentos_login_fallidos = 0
        db.session.commit()
    
    
    # ===============================
    # MÉTODOS DE VALIDACIÓN
    # ===============================
    
    @staticmethod
    def validar_email(email):
        """
        Valida formato de email.
        
        Args:
            email (str): Email a validar
        
        Returns:
            bool: True si el formato es válido
        """
        patron_email = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(patron_email, email) is not None
    
    
    @staticmethod
    def validar_rol(rol):
        """
        Valida que el rol sea válido.
        
        Args:
            rol (str): Rol a validar
        
        Returns:
            bool: True si el rol es válido
        """
        from flask import current_app
        roles_validos = current_app.config.get('ROLES_USUARIO', ['usuario', 'supervisor', 'admin'])
        return rol in roles_validos
    
    
    def to_dict(self, incluir_sensible=False):
        """
        Convierte el usuario a diccionario para JSON.
        
        Args:
            incluir_sensible (bool): Si incluir campos sensibles
        
        Returns:
            dict: Representación del usuario
        """
        datos = {
            'id': self.id,
            'email': self.email,
            'nombre_completo': self.nombre_completo,
            'rol': self.rol,
            'activo': self.activo,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            'otp_habilitado': self.otp_habilitado
        }
        
        if incluir_sensible:
            datos.update({
                'fecha_ultimo_acceso': self.fecha_ultimo_acceso.isoformat() if self.fecha_ultimo_acceso else None,
                'intentos_login_fallidos': self.intentos_login_fallidos,
                'requiere_cambio_password': self.requiere_cambio_password
            })
        
        return datos
# ===============================
# FUNCIONES AUXILIARES
# ===============================

def crear_usuario_admin_inicial():
    """
    Crea el usuario administrador inicial si no existe.
    Se ejecuta automáticamente al inicializar la aplicación.
    """
    admin_existente = Usuario.query.filter_by(rol='admin').first()
    
    if not admin_existente:
        admin = Usuario(
            email='admin@documentos.local',
            nombre_completo='Administrador del Sistema',
            rol='admin',
            activo=True
        )
        admin.establecer_password('admin123456')
        
        db.session.add(admin)
        db.session.commit()
        
        return admin
    
    return admin_existente


def crear_usuarios_prueba():
    """
    Crea usuarios de prueba para desarrollo y testing.
    """
    usuarios_prueba = [
        {
            'email': 'admin@test.com',
            'nombre_completo': 'Administrador de Prueba',
            'rol': 'admin',
            'password': 'admin123'
        },
        {
            'email': 'supervisor@test.com',
            'nombre_completo': 'Supervisor de Prueba',
            'rol': 'supervisor',
            'password': 'supervisor123'
        },
        {
            'email': 'usuario@test.com',
            'nombre_completo': 'Usuario de Prueba',
            'rol': 'usuario',
            'password': 'usuario123'
        }
    ]
    
    for datos in usuarios_prueba:
        usuario_existente = Usuario.query.filter_by(email=datos['email']).first()
        
        if not usuario_existente:
            usuario = Usuario(
                email=datos['email'],
                nombre_completo=datos['nombre_completo'],
                rol=datos['rol'],
                activo=True
            )
            usuario.establecer_password(datos['password'])
            
            db.session.add(usuario)
    
    db.session.commit()