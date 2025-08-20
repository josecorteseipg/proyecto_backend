import re
import os
from datetime import datetime
from flask import current_app
from werkzeug.utils import secure_filename

class ValidadorDatos:
    """
    Clase centralizada para todas las validaciones del sistema.
    Proporciona métodos estáticos para validar diferentes tipos de datos.
    """
    
    # ===============================
    # VALIDACIONES DE USUARIO
    # ===============================
    
    @staticmethod
    def validar_email(email):
        """
        Valida formato de email.
        
        Args:
            email (str): Email a validar
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not email:
            return False, "Email es requerido"
        
        if len(email) > 120:
            return False, "Email demasiado largo (máximo 120 caracteres)"
        
        # Patrón regex para email
        patron_email = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(patron_email, email):
            return False, "Formato de email inválido"
        
        return True, None
    
    
    @staticmethod
    def validar_password(password):
        """
        Valida fortaleza de contraseña.
        
        Args:
            password (str): Contraseña a validar
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not password:
            return False, "Contraseña es requerida"
        
        if len(password) < 6:
            return False, "Contraseña debe tener al menos 6 caracteres"
        
        if len(password) > 128:
            return False, "Contraseña demasiado larga (máximo 128 caracteres)"
        
        # Validaciones adicionales de seguridad
        tiene_minuscula = bool(re.search(r'[a-z]', password))
        tiene_mayuscula = bool(re.search(r'[A-Z]', password))
        tiene_numero = bool(re.search(r'\d', password))
        
        puntuacion_seguridad = 0
        
        if tiene_minuscula:
            puntuacion_seguridad += 1
        if tiene_mayuscula:
            puntuacion_seguridad += 1
        if tiene_numero:
            puntuacion_seguridad += 1
        if len(password) >= 8:
            puntuacion_seguridad += 1
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            puntuacion_seguridad += 1
        
        # Contraseñas muy débiles
        if puntuacion_seguridad < 2:
            return False, "Contraseña muy débil. Debe contener letras y números"
        
        return True, None
    
    
    @staticmethod
    def validar_nombre_completo(nombre):
        """
        Valida nombre completo.
        
        Args:
            nombre (str): Nombre a validar
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not nombre or not nombre.strip():
            return False, "Nombre completo es requerido"
        
        nombre = nombre.strip()
        
        if len(nombre) < 2:
            return False, "Nombre debe tener al menos 2 caracteres"
        
        if len(nombre) > 200:
            return False, "Nombre demasiado largo (máximo 200 caracteres)"
        
        # Solo letras, espacios, tildes y algunos caracteres especiales
        patron_nombre = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s\-\.\']+$'
        
        if not re.match(patron_nombre, nombre):
            return False, "Nombre contiene caracteres inválidos"
        
        return True, None
    
    
    @staticmethod
    def validar_rol(rol):
        """
        Valida que el rol sea válido.
        
        Args:
            rol (str): Rol a validar
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not rol:
            return False, "Rol es requerido"
        
        roles_validos = current_app.config.get('ROLES_USUARIO', ['usuario', 'supervisor', 'admin'])
        
        if rol not in roles_validos:
            return False, f"Rol inválido. Roles válidos: {', '.join(roles_validos)}"
        
        return True, None
    
    
    # ===============================
    # VALIDACIONES DE DOCUMENTO
    # ===============================
    
    @staticmethod
    def validar_nombre_documento(nombre):
        """
        Valida nombre de documento.
        
        Args:
            nombre (str): Nombre del documento
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not nombre or not nombre.strip():
            return False, "Nombre del documento es requerido"
        
        nombre = nombre.strip()
        
        if len(nombre) < 3:
            return False, "Nombre del documento debe tener al menos 3 caracteres"
        
        if len(nombre) > 255:
            return False, "Nombre del documento demasiado largo (máximo 255 caracteres)"
        
        # Caracteres prohibidos en nombres de archivo
        caracteres_prohibidos = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        
        for caracter in caracteres_prohibidos:
            if caracter in nombre:
                return False, f"Nombre contiene caracteres prohibidos: {', '.join(caracteres_prohibidos)}"
        
        return True, None
    
    
    @staticmethod
    def validar_nivel_seguridad(nivel):
        """
        Valida nivel de seguridad del documento.
        
        Args:
            nivel (str): Nivel de seguridad
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not nivel:
            return False, "Nivel de seguridad es requerido"
        
        niveles_validos = current_app.config.get('NIVELES_SEGURIDAD', ['publico', 'confidencial', 'secreto'])
        
        if nivel not in niveles_validos:
            return False, f"Nivel de seguridad inválido. Niveles válidos: {', '.join(niveles_validos)}"
        
        return True, None
    
    
    @staticmethod
    def validar_archivo(archivo):
        """
        Valida archivo subido.
        
        Args:
            archivo: Objeto file de werkzeug
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not archivo:
            return False, "Archivo es requerido"
        
        if not archivo.filename:
            return False, "Nombre de archivo es requerido"
        
        # Validar extensión
        extension = ValidadorDatos._obtener_extension(archivo.filename)
        
        if not extension:
            return False, "Archivo debe tener una extensión"
        
        extensiones_permitidas = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'doc', 'docx', 'txt'})
        
        if extension.lower() not in extensiones_permitidas:
            return False, f"Extensión no permitida. Extensiones válidas: {', '.join(extensiones_permitidas)}"
        
        # Validar tamaño
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)  # 16MB por defecto
                
        # Validar nombre de archivo
        nombre_seguro = secure_filename(archivo.filename)
        
        if not nombre_seguro:
            return False, "Nombre de archivo inválido"
        
        return True, None
    
    
    @staticmethod
    def validar_descripcion(descripcion):
        """
        Valida descripción del documento.
        
        Args:
            descripcion (str): Descripción a validar
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if descripcion is None:
            return True, None  # Descripción es opcional
        
        if len(descripcion) > 1000:
            return False, "Descripción demasiado larga (máximo 1000 caracteres)"
        
        return True, None
    
    
    # ===============================
    # VALIDACIONES DE OTP
    # ===============================
    
    @staticmethod
    def validar_codigo_otp(codigo):
        """
        Valida formato de código OTP.
        
        Args:
            codigo (str): Código OTP
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not codigo:
            return False, "Código OTP es requerido"
        
        # Remover espacios
        codigo = codigo.strip().replace(' ', '')
        
        # Debe ser 6 dígitos
        if not re.match(r'^\d{6}$', codigo):
            return False, "Código OTP debe ser de 6 dígitos"
        
        return True, None
    
    
    @staticmethod
    def validar_clave_base32(clave):
        """
        Valida clave base32 para OTP.
        
        Args:
            clave (str): Clave base32
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not clave:
            return False, "Clave base32 es requerida"
        
        # Base32 válido: solo letras A-Z y números 2-7
        if not re.match(r'^[A-Z2-7]+$', clave):
            return False, "Clave base32 inválida"
        
        # Longitud típica de clave base32
        if len(clave) < 16 or len(clave) > 64:
            return False, "Longitud de clave base32 inválida"
        
        return True, None
    
    
    # ===============================
    # VALIDACIONES GENERALES
    # ===============================
    
    @staticmethod
    def validar_id(id_valor, nombre_campo="ID"):
        """
        Valida que un ID sea válido.
        
        Args:
            id_valor: Valor del ID
            nombre_campo (str): Nombre del campo para el mensaje de error
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if id_valor is None:
            return False, f"{nombre_campo} es requerido"
        
        try:
            id_entero = int(id_valor)
            if id_entero <= 0:
                return False, f"{nombre_campo} debe ser un número positivo"
            return True, None
        except (ValueError, TypeError):
            return False, f"{nombre_campo} debe ser un número válido"
    
    
    @staticmethod
    def validar_paginacion(pagina, por_pagina, maximo_por_pagina=100):
        """
        Valida parámetros de paginación.
        
        Args:
            pagina: Número de página
            por_pagina: Elementos por página
            maximo_por_pagina (int): Máximo elementos por página
        
        Returns:
            tuple: (es_valido, mensaje_error, pagina_validada, por_pagina_validada)
        """
        # Validar página
        try:
            pagina = int(pagina) if pagina else 1
            if pagina < 1:
                pagina = 1
        except (ValueError, TypeError):
            pagina = 1
        
        # Validar por_pagina
        try:
            por_pagina = int(por_pagina) if por_pagina else 10
            if por_pagina < 1:
                por_pagina = 10
            if por_pagina > maximo_por_pagina:
                por_pagina = maximo_por_pagina
        except (ValueError, TypeError):
            por_pagina = 10
        
        return True, None, pagina, por_pagina
    
    
    @staticmethod
    def validar_busqueda(termino_busqueda):
        """
        Valida términos de búsqueda.
        
        Args:
            termino_busqueda (str): Término de búsqueda
        
        Returns:
            tuple: (es_valido, mensaje_error, termino_limpio)
        """
        if not termino_busqueda:
            return True, None, ""
        
        # Limpiar término
        termino_limpio = termino_busqueda.strip()
        
        if len(termino_limpio) < 2:
            return False, "Término de búsqueda debe tener al menos 2 caracteres", termino_limpio
        
        if len(termino_limpio) > 100:
            return False, "Término de búsqueda demasiado largo (máximo 100 caracteres)", termino_limpio
        
        # Remover caracteres especiales problemáticos para SQL
        caracteres_problematicos = ['%', '_', '\\']
        for caracter in caracteres_problematicos:
            termino_limpio = termino_limpio.replace(caracter, '')
        
        return True, None, termino_limpio
    
    
    # ===============================
    # MÉTODOS AUXILIARES
    # ===============================
    
    @staticmethod
    def _obtener_extension(nombre_archivo):
        """
        Obtiene la extensión de un archivo.
        
        Args:
            nombre_archivo (str): Nombre del archivo
        
        Returns:
            str: Extensión del archivo (sin punto)
        """
        return nombre_archivo.rsplit('.', 1)[1] if '.' in nombre_archivo else ''
    
    
    @staticmethod
    def limpiar_datos_entrada(datos):
        """
        Limpia datos de entrada eliminando espacios y caracteres problemáticos.
        
        Args:
            datos (dict): Diccionario con datos a limpiar
        
        Returns:
            dict: Datos limpiados
        """
        datos_limpios = {}
        
        for clave, valor in datos.items():
            if isinstance(valor, str):
                # Limpiar espacios al inicio y final
                valor_limpio = valor.strip()
                
                # Convertir cadenas vacías a None
                if valor_limpio == '':
                    valor_limpio = None
                
                datos_limpios[clave] = valor_limpio
            else:
                datos_limpios[clave] = valor
        
        return datos_limpios


# ===============================
# FUNCIONES DE CONVENIENCIA
# ===============================

def validar_datos_usuario(datos):
    """
    Valida todos los datos necesarios para crear/actualizar un usuario.
    
    Args:
        datos (dict): Datos del usuario
    
    Returns:
        tuple: (es_valido, errores_dict)
    """
    errores = {}
    
    # Validar email
    if 'email' in datos:
        es_valido, mensaje = ValidadorDatos.validar_email(datos['email'])
        if not es_valido:
            errores['email'] = mensaje
    
    # Validar password (solo si está presente)
    if 'password' in datos and datos['password']:
        es_valido, mensaje = ValidadorDatos.validar_password(datos['password'])
        if not es_valido:
            errores['password'] = mensaje
    
    # Validar nombre completo
    if 'nombre_completo' in datos:
        es_valido, mensaje = ValidadorDatos.validar_nombre_completo(datos['nombre_completo'])
        if not es_valido:
            errores['nombre_completo'] = mensaje
    
    # Validar rol
    if 'rol' in datos:
        es_valido, mensaje = ValidadorDatos.validar_rol(datos['rol'])
        if not es_valido:
            errores['rol'] = mensaje
    
    return len(errores) == 0, errores


def validar_datos_documento(datos, archivo=None):
    """
    Valida todos los datos necesarios para crear/actualizar un documento.
    
    Args:
        datos (dict): Datos del documento
        archivo: Archivo adjunto (opcional)
    
    Returns:
        tuple: (es_valido, errores_dict)
    """
    errores = {}
    
    # Validar nombre
    if 'nombre' in datos:
        es_valido, mensaje = ValidadorDatos.validar_nombre_documento(datos['nombre'])
        if not es_valido:
            errores['nombre'] = mensaje
    
    # Validar descripción
    if 'descripcion' in datos:
        es_valido, mensaje = ValidadorDatos.validar_descripcion(datos['descripcion'])
        if not es_valido:
            errores['descripcion'] = mensaje
    
    # Validar nivel de seguridad
    if 'nivel_seguridad' in datos:
        es_valido, mensaje = ValidadorDatos.validar_nivel_seguridad(datos['nivel_seguridad'])
        if not es_valido:
            errores['nivel_seguridad'] = mensaje
    
    # Validar archivo si está presente
    if archivo:
        es_valido, mensaje = ValidadorDatos.validar_archivo(archivo)
        if not es_valido:
            errores['archivo'] = mensaje
    
    return len(errores) == 0, errores