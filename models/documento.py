from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from flask import current_app
from .usuario import db

class Documento(db.Model):
    """
    Modelo Documento para el sistema de gestión de documentos seguros.
    Incluye niveles de seguridad, relaciones con usuarios y gestión de archivos.
    """
    
    __tablename__ = 'documentos'
    
    # ===============================
    # CAMPOS PRINCIPALES
    # ===============================
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    descripcion = db.Column(db.Text)
    
    # Seguridad y clasificación
    nivel_seguridad = db.Column(db.String(20), nullable=False, default='publico')  # publico, confidencial, secreto
    categoria = db.Column(db.String(100))  # categoría opcional del documento
    tags = db.Column(db.Text)  # tags separados por comas
    
    # Gestión de archivos
    nombre_archivo_original = db.Column(db.String(300))
    nombre_archivo_sistema = db.Column(db.String(300))  # nombre único en el sistema
    extension_archivo = db.Column(db.String(10))
    tamano_archivo = db.Column(db.Integer)  # tamaño en bytes
    tipo_mime = db.Column(db.String(100))
    ruta_archivo = db.Column(db.String(500))  # ruta completa del archivo
    
    # Relaciones
    propietario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    # Campos de auditoría
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fecha_ultimo_acceso = db.Column(db.DateTime)
    
    # Estadísticas de uso
    contador_descargas = db.Column(db.Integer, default=0)
    contador_visualizaciones = db.Column(db.Integer, default=0)
    
    # Control de versiones básico
    version = db.Column(db.String(20), default='1.0')
    es_version_actual = db.Column(db.Boolean, default=True)
    documento_padre_id = db.Column(db.Integer, db.ForeignKey('documentos.id'))
    
    # Metadatos adicionales
    palabras_clave = db.Column(db.Text)
    estado = db.Column(db.String(20), default='activo')  # activo, archivado, eliminado
    
    # Relaciones adicionales
    versiones = db.relationship('Documento', backref=db.backref('documento_padre', remote_side=[id]), lazy='dynamic')
    
    def __repr__(self):
        return f'<Documento {self.nombre}>'
    
    
    # ===============================
    # MÉTODOS DE GESTIÓN DE ARCHIVOS
    # ===============================
    
    def establecer_archivo(self, archivo, carpeta_destino=None):
        """
        Establece el archivo físico asociado al documento.
        
        Args:
            archivo: Objeto file de werkzeug
            carpeta_destino (str): Carpeta específica (opcional)
        
        Returns:
            bool: True si se guardó correctamente
        """
        try:
            if not archivo or not archivo.filename:
                return False
            
            # Obtener información del archivo
            self.nombre_archivo_original = archivo.filename
            self.extension_archivo = self._obtener_extension(archivo.filename)
            self.tipo_mime = archivo.content_type
            
            # Validar extensión
            if not self._es_extension_permitida(self.extension_archivo):
                raise ValueError(f"Extensión {self.extension_archivo} no permitida")
            
            # Generar nombre único para el sistema
            self.nombre_archivo_sistema = self._generar_nombre_unico(archivo.filename)
            
            # Determinar carpeta de destino
            if not carpeta_destino:
                carpeta_destino = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            
            # Crear subcarpeta por nivel de seguridad
            subcarpeta = os.path.join(carpeta_destino, self.nivel_seguridad)
            os.makedirs(subcarpeta, exist_ok=True)
            
            # Ruta completa del archivo
            self.ruta_archivo = os.path.join(subcarpeta, self.nombre_archivo_sistema)
            
            # Guardar archivo
            archivo.save(self.ruta_archivo)
            
            # Obtener tamaño del archivo
            self.tamano_archivo = os.path.getsize(self.ruta_archivo)
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error guardando archivo: {str(e)}")
            return False
    
    
    def obtener_ruta_completa(self):
        """
        Obtiene la ruta completa del archivo en el sistema.
        
        Returns:
            str: Ruta completa del archivo o None si no existe
        """
        if self.ruta_archivo and os.path.exists(self.ruta_archivo):
            return self.ruta_archivo
        return None
    
    
    def eliminar_archivo_fisico(self):
        """
        Elimina el archivo físico del sistema de archivos.
        
        Returns:
            bool: True si se eliminó correctamente
        """
        try:
            if self.ruta_archivo and os.path.exists(self.ruta_archivo):
                os.remove(self.ruta_archivo)
                return True
            return False
        except Exception as e:
            current_app.logger.error(f"Error eliminando archivo {self.ruta_archivo}: {str(e)}")
            return False
    
    
    def mover_a_carpeta_seguridad(self):
        """
        Mueve el archivo a la carpeta correspondiente según su nivel de seguridad.
        
        Returns:
            bool: True si se movió correctamente
        """
        try:
            if not self.ruta_archivo or not os.path.exists(self.ruta_archivo):
                return False
            
            # Nueva ruta según nivel de seguridad
            carpeta_base = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            nueva_carpeta = os.path.join(carpeta_base, self.nivel_seguridad)
            os.makedirs(nueva_carpeta, exist_ok=True)
            
            nueva_ruta = os.path.join(nueva_carpeta, self.nombre_archivo_sistema)
            
            # Mover archivo si la ruta es diferente
            if self.ruta_archivo != nueva_ruta:
                os.rename(self.ruta_archivo, nueva_ruta)
                self.ruta_archivo = nueva_ruta
                db.session.commit()
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error moviendo archivo: {str(e)}")
            return False
    
    
    # ===============================
    # MÉTODOS DE SEGURIDAD Y PERMISOS
    # ===============================
    
    def requiere_otp_para_accion(self, accion, usuario):
        """
        Determina si una acción requiere OTP para este documento y usuario.
        
        Args:
            accion (str): Acción a realizar ('ver','eliminar', 'descargar')
            usuario: Instancia del modelo Usuario
        
        Returns:
            bool: True si requiere OTP
        """
        from .otp import GestorOTP
        
        return GestorOTP.requiere_otp_para_accion(accion, self.nivel_seguridad, usuario.rol)
    
    
    def puede_ser_accedido_por(self, usuario):
        """
        Verifica si un usuario puede acceder a este documento.
        
        Args:
            usuario: Instancia del modelo Usuario
        
        Returns:
            bool: True si puede acceder
        """
        return usuario.puede_acceder_documento(self)
    
    
    def puede_ser_modificado_por(self, usuario):
        """
        Verifica si un usuario puede modificar este documento.
        
        Args:
            usuario: Instancia del modelo Usuario
        
        Returns:
            bool: True si puede modificar
        """
        return usuario.puede_modificar_documento(self)
    
    
    def puede_ser_eliminado_por(self, usuario):
        """
        Verifica si un usuario puede eliminar este documento.
        
        Args:
            usuario: Instancia del modelo Usuario
        
        Returns:
            bool: True si puede eliminar
        """
        return usuario.puede_eliminar_documento(self)
    
    
    # ===============================
    # MÉTODOS DE ESTADÍSTICAS
    # ===============================
    
    def registrar_visualizacion(self, usuario_id=None):
        """
        Registra una visualización del documento.
        
        Args:
            usuario_id (int): ID del usuario que visualiza (opcional)
        """
        self.contador_visualizaciones += 1
        self.fecha_ultimo_acceso = datetime.utcnow()
        db.session.commit()
    
    
    def registrar_descarga(self, usuario_id=None):
        """
        Registra una descarga del documento.
        
        Args:
            usuario_id (int): ID del usuario que descarga (opcional)
        """
        self.contador_descargas += 1
        self.fecha_ultimo_acceso = datetime.utcnow()
        db.session.commit()
    
    
    def obtener_estadisticas(self):
        """
        Obtiene estadísticas del documento.
        
        Returns:
            dict: Estadísticas del documento
        """
        return {
            'visualizaciones': self.contador_visualizaciones,
            'descargas': self.contador_descargas,
            'fecha_ultimo_acceso': self.fecha_ultimo_acceso.isoformat() if self.fecha_ultimo_acceso else None,
            'tamano_archivo_mb': round(self.tamano_archivo / 1024 / 1024, 2) if self.tamano_archivo else 0,
            'dias_desde_creacion': (datetime.utcnow() - self.fecha_creacion).days
        }
    
    
    # ===============================
    # MÉTODOS DE VALIDACIÓN
    # ===============================
    
    @staticmethod
    def validar_nivel_seguridad(nivel):
        """
        Valida que el nivel de seguridad sea válido.
        
        Args:
            nivel (str): Nivel de seguridad a validar
        
        Returns:
            bool: True si es válido
        """
        from flask import current_app
        niveles_validos = current_app.config.get('NIVELES_SEGURIDAD', ['publico', 'confidencial', 'secreto'])
        return nivel in niveles_validos
    
    
    def _es_extension_permitida(self, extension):
        """
        Verifica si la extensión del archivo está permitida.
        
        Args:
            extension (str): Extensión del archivo
        
        Returns:
            bool: True si está permitida
        """
        extensiones_permitidas = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'doc', 'docx', 'txt'})
        return extension.lower() in extensiones_permitidas
    
    
    def _obtener_extension(self, nombre_archivo):
        """
        Obtiene la extensión de un archivo.
        
        Args:
            nombre_archivo (str): Nombre del archivo
        
        Returns:
            str: Extensión del archivo (sin punto)
        """
        return nombre_archivo.rsplit('.', 1)[1] if '.' in nombre_archivo else ''
    
    
    def _generar_nombre_unico(self, nombre_original):
        """
        Genera un nombre único para el archivo en el sistema.
        
        Args:
            nombre_original (str): Nombre original del archivo
        
        Returns:
            str: Nombre único generado
        """
        import uuid
        
        nombre_seguro = secure_filename(nombre_original)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        identificador_unico = str(uuid.uuid4())[:8]
        
        # Formato: timestamp_id_nombreoriginal
        extension = self._obtener_extension(nombre_seguro)
        nombre_sin_extension = nombre_seguro.rsplit('.', 1)[0] if '.' in nombre_seguro else nombre_seguro
        
        return f"{timestamp}_{identificador_unico}_{nombre_sin_extension}.{extension}"
    
    
    # ===============================
    # MÉTODOS DE CONVERSIÓN Y SERIALIZACIÓN
    # ===============================
    
    def to_dict(self, incluir_estadisticas=False, incluir_archivo_info=False):
        """
        Convierte el documento a diccionario para JSON.
        
        Args:
            incluir_estadisticas (bool): Si incluir estadísticas de uso
            incluir_archivo_info (bool): Si incluir información del archivo
        
        Returns:
            dict: Representación del documento
        """
        datos = {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'nivel_seguridad': self.nivel_seguridad,
            'categoria': self.categoria,
            'propietario_id': self.propietario_id,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            'fecha_modificacion': self.fecha_modificacion.isoformat() if self.fecha_modificacion else None,
            'version': self.version,
            'estado': self.estado
        }
        
        if incluir_archivo_info:
            datos.update({
                'nombre_archivo_original': self.nombre_archivo_original,
                'extension_archivo': self.extension_archivo,
                'tamano_archivo': self.tamano_archivo,
                'tipo_mime': self.tipo_mime
            })
        
        if incluir_estadisticas:
            datos.update(self.obtener_estadisticas())
        
        return datos
    
    
    def to_dict_publico(self):
        """
        Versión pública del documento (sin información sensible).
        
        Returns:
            dict: Representación pública del documento
        """
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'categoria': self.categoria,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            'extension_archivo': self.extension_archivo
        }


# ===============================
# FUNCIONES AUXILIARES
# ===============================

def buscar_documentos(termino_busqueda, usuario, limite=10):
    """
    Busca documentos accesibles por un usuario.
    
    Args:
        termino_busqueda (str): Término a buscar
        usuario: Instancia del modelo Usuario
        limite (int): Número máximo de resultados
    
    Returns:
        list: Lista de documentos encontrados
    """
    query = Documento.query.filter(Documento.estado == 'activo')
    
    # Filtrar por permisos de acceso según rol
    if not usuario.es_admin():
        if usuario.es_supervisor():
            # Supervisor: sus documentos + públicos + confidenciales
            query = query.filter(
                db.or_(
                    Documento.propietario_id == usuario.id,
                    Documento.nivel_seguridad == 'publico',
                    Documento.nivel_seguridad == 'confidencial'
                )
            )
        else:
            # Usuario normal: sus documentos + públicos
            query = query.filter(
                db.or_(
                    Documento.propietario_id == usuario.id,
                    Documento.nivel_seguridad == 'publico'
                )
            )
    
    # Aplicar filtro de búsqueda
    if termino_busqueda:
        filtro_busqueda = f"%{termino_busqueda}%"
        query = query.filter(
            db.or_(
                Documento.nombre.ilike(filtro_busqueda),
                Documento.descripcion.ilike(filtro_busqueda),
                Documento.categoria.ilike(filtro_busqueda),
                Documento.tags.ilike(filtro_busqueda)
            )
        )
    
    return query.limit(limite).all()


def obtener_documentos_por_nivel_seguridad(nivel_seguridad, usuario):
    """
    Obtiene documentos por nivel de seguridad accesibles por un usuario.
    
    Args:
        nivel_seguridad (str): Nivel de seguridad
        usuario: Instancia del modelo Usuario
    
    Returns:
        list: Lista de documentos del nivel especificado
    """
    query = Documento.query.filter(
        Documento.nivel_seguridad == nivel_seguridad,
        Documento.estado == 'activo'
    )
    
    # Aplicar filtros de permisos
    if not usuario.es_admin():
        if nivel_seguridad == 'secreto':
            # Solo propietarios pueden ver secretos (además de admin)
            query = query.filter(Documento.propietario_id == usuario.id)
        elif nivel_seguridad == 'confidencial' and not usuario.es_supervisor():
            # Solo supervisor+ pueden ver confidenciales
            query = query.filter(Documento.propietario_id == usuario.id)
    
    return query.all()