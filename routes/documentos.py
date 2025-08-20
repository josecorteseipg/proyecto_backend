"""
Rutas para gestión de documentos del Sistema de Gestión de Documentos Seguros
CRUD completo con autenticación, autorización y sistema OTP integrado
Autor: José Luis Cortese
Asignatura: Backend - IPG 2025
Fecha: Agosto 17, 2025
"""

import os
from flask import Blueprint, request, jsonify, send_file, current_app
from datetime import datetime

# Importar modelos y utilidades ya disponibles
from models import db
from models.documento import Documento, buscar_documentos, obtener_documentos_por_nivel_seguridad
from models.usuario import Usuario
from models.otp import GestorOTP

# Importar decoradores ya desarrollados
from utils.decoradores import (
    requiere_autenticacion, 
    validar_acceso_documento,
    validar_contenido_json,
    registrar_auditoria,
    limitar_frecuencia
)

# Importar validaciones centralizadas
from utils.validaciones import ValidadorDatos
# ===============================
# CONFIGURACIÓN DEL BLUEPRINT
# ===============================
documentos_bp = Blueprint('documentos', __name__, url_prefix='/api/documentos')
# ===============================
# ENDPOINTS CRUD PRINCIPALES
# ===============================
@documentos_bp.route('', methods=['POST'])
@limitar_frecuencia(maximo_intentos=10, ventana_tiempo=300)  # 10 uploads cada 5 min
@requiere_autenticacion
@registrar_auditoria('crear_documento')
def crear_documento(usuario_actual):
    """
    Crea un nuevo documento con archivo asociado.    
    Endpoint: POST /api/documentos
    
    Campos del formulario:
    - archivo (file): Archivo a subir
    - nombre (str): Nombre del documento
    - descripcion (str, opcional): Descripción del documento
    - nivel_seguridad (str): 'publico', 'confidencial', 'secreto'
    - categoria (str, opcional): Categoría del documento
    - tags (str, opcional): Tags separados por comas
    
    Returns:
        JSON: Información del documento creado
    """
    try:
        # Verificar que se envió un archivo
        if 'archivo' not in request.files:
            return jsonify({
                'error': 'No se encontró archivo en la solicitud',
                'codigo': 'ARCHIVO_FALTANTE'
            }), 400
        
        archivo = request.files['archivo']
        
        # Validar archivo
        archivo_valido, mensaje_error = ValidadorDatos.validar_archivo(archivo)
        if not archivo_valido:
            return jsonify({
                'error': mensaje_error,
                'codigo': 'ARCHIVO_INVALIDO'
            }), 400
        
        # Obtener y validar datos del formulario
        nombre = request.form.get('nombre', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        nivel_seguridad = request.form.get('nivel_seguridad', 'publico').strip().lower()
        categoria = request.form.get('categoria', '').strip()
        tags = request.form.get('tags', '').strip()
        
        # Validaciones usando ValidadorDatos
        nombre_valido, error_nombre = ValidadorDatos.validar_nombre_documento(nombre)
        if not nombre_valido:
            return jsonify({
                'error': error_nombre,
                'codigo': 'NOMBRE_INVALIDO'
            }), 400
        
        nivel_valido, error_nivel = ValidadorDatos.validar_nivel_seguridad(nivel_seguridad)
        if not nivel_valido:
            return jsonify({
                'error': error_nivel,
                'codigo': 'NIVEL_SEGURIDAD_INVALIDO'
            }), 400
        
        if descripcion:
            desc_valida, error_desc = ValidadorDatos.validar_descripcion(descripcion)
            if not desc_valida:
                return jsonify({
                    'error': error_desc,
                    'codigo': 'DESCRIPCION_INVALIDA'
                }), 400
        
        # Verificar permisos para crear documentos con este nivel de seguridad
        if nivel_seguridad == 'secreto' and not (usuario_actual.es_admin() or usuario_actual.es_supervisor()):
            return jsonify({
                'error': 'No tienes permisos para crear documentos secretos',
                'codigo': 'PERMISOS_INSUFICIENTES_NIVEL_SECRETO'
            }), 403
        
        # Crear instancia del documento
        documento = Documento(
            nombre=nombre,
            descripcion=descripcion or None,
            nivel_seguridad=nivel_seguridad,
            categoria=categoria or None,
            tags=tags or None,
            propietario_id=usuario_actual.id
        )
        
        # Establecer archivo asociado
        if not documento.establecer_archivo(archivo):
            return jsonify({
                'error': 'Error al guardar el archivo',
                'codigo': 'ERROR_GUARDANDO_ARCHIVO'
            }), 500
        
        # Guardar en base de datos
        db.session.add(documento)
        db.session.commit()
                
        return jsonify({
            'mensaje': 'Documento creado exitosamente',
            'documento': documento.to_dict(incluir_archivo_info=True),
            'propietario': usuario_actual.to_dict()
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Error creando documento: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Error interno creando documento',
            'codigo': 'ERROR_INTERNO_CREACION'
        }), 500


@documentos_bp.route('', methods=['GET'])
@requiere_autenticacion
def listar_documentos(usuario_actual):
    """
    Lista documentos accesibles por el usuario con filtros opcionales.
    
    Endpoint: GET /api/documentos
    
    Parámetros query opcionales:
    - pagina (int): Número de página (default: 1)
    - por_pagina (int): Elementos por página (default: 10, max: 50)
    - nivel_seguridad (str): Filtrar por nivel de seguridad
    - categoria (str): Filtrar por categoría
    - propietario_id (int): Filtrar por propietario (solo admin/supervisor)
    - busqueda (str): Término de búsqueda en nombre/descripción
    - ordenar_por (str): Campo de ordenación (fecha_creacion, nombre, tamano_archivo)
    - orden (str): Dirección de orden (asc, desc)
    
    Returns:
        JSON: Lista paginada de documentos
    """
    try:
        # Parámetros de paginación
        pagina = request.args.get('pagina', 1, type=int)
        por_pagina = min(request.args.get('por_pagina', 10, type=int), 50)
        
        # Parámetros de filtrado
        nivel_seguridad = request.args.get('nivel_seguridad', '').strip()
        categoria = request.args.get('categoria', '').strip()
        propietario_id = request.args.get('propietario_id', type=int)
        termino_busqueda = request.args.get('busqueda', '').strip()
        
        # Parámetros de ordenación
        ordenar_por = request.args.get('ordenar_por', 'fecha_creacion').strip()
        orden = request.args.get('orden', 'desc').strip().lower()
        
        # Validar parámetros
        if ordenar_por not in ['fecha_creacion', 'nombre', 'tamano_archivo', 'fecha_modificacion']:
            ordenar_por = 'fecha_creacion'
        
        if orden not in ['asc', 'desc']:
            orden = 'desc'
        
        # Construir query base
        query = Documento.query.filter(Documento.estado == 'activo')
        
        # Aplicar filtros de permisos según rol del usuario
        if not usuario_actual.es_admin():
            if usuario_actual.es_supervisor():
                # Supervisor: sus documentos + públicos + confidenciales
                query = query.filter(
                    db.or_(
                        Documento.propietario_id == usuario_actual.id,
                        Documento.nivel_seguridad == 'publico',
                        Documento.nivel_seguridad == 'confidencial'
                    )
                )
            else:
                # Usuario normal: sus documentos + públicos
                query = query.filter(
                    db.or_(
                        Documento.propietario_id == usuario_actual.id,
                        Documento.nivel_seguridad == 'publico'
                    )
                )
        
        # Aplicar filtros adicionales
        if nivel_seguridad:
            nivel_valido, _ = ValidadorDatos.validar_nivel_seguridad(nivel_seguridad)
            if nivel_valido:
                query = query.filter(Documento.nivel_seguridad == nivel_seguridad)
        
        if categoria:
            query = query.filter(Documento.categoria.ilike(f"%{categoria}%"))
        
        if propietario_id and (usuario_actual.es_admin() or usuario_actual.es_supervisor()):
            query = query.filter(Documento.propietario_id == propietario_id)
        
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
        
        # Aplicar ordenación
        campo_orden = getattr(Documento, ordenar_por)
        if orden == 'desc':
            query = query.order_by(campo_orden.desc())
        else:
            query = query.order_by(campo_orden.asc())
        
        # Ejecutar paginación
        paginacion = query.paginate(
            page=pagina,
            per_page=por_pagina,
            error_out=False
        )
        
        # Construir respuesta
        documentos = []
        for doc in paginacion.items:
            doc_dict = doc.to_dict(incluir_archivo_info=True)
            
            # Agregar información de propietario si es útil
            if usuario_actual.es_admin() or usuario_actual.es_supervisor():
                propietario = Usuario.query.get(doc.propietario_id)
                doc_dict['propietario'] = propietario.to_dict() if propietario else None
            
            documentos.append(doc_dict)
        
        return jsonify({
            'documentos': documentos,
            'paginacion': {
                'pagina_actual': paginacion.page,
                'por_pagina': paginacion.per_page,
                'total_elementos': paginacion.total,
                'total_paginas': paginacion.pages,
                'tiene_siguiente': paginacion.has_next,
                'tiene_anterior': paginacion.has_prev
            },
            'filtros_aplicados': {
                'nivel_seguridad': nivel_seguridad or None,
                'categoria': categoria or None,
                'busqueda': termino_busqueda or None,
                'ordenar_por': ordenar_por,
                'orden': orden
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error listando documentos: {str(e)}")
        return jsonify({
            'error': 'Error interno listando documentos',
            'codigo': 'ERROR_INTERNO_LISTADO'
        }), 500


@documentos_bp.route('/<int:documento_id>', methods=['GET'])
@validar_acceso_documento('ver')
def obtener_documento(documento_id, usuario_actual, documento):
    """
    Obtiene información detallada de un documento específico.
    
    Endpoint: GET /api/documentos/<id>
    
    Returns:
        JSON: Información completa del documento
    """
    try:
        # Verificar si requiere OTP para ver este documento
        requiere_otp = GestorOTP.requiere_otp_para_accion(
            accion='ver',
            nivel_seguridad=documento.nivel_seguridad,
            rol_usuario=usuario_actual.rol
        )
        print(requiere_otp)
        
        if requiere_otp:
            # Verificar código OTP en headers
            codigo_otp = request.headers.get('X-OTP-Code')
            if not codigo_otp:
                return jsonify({
                    'error': 'Código OTP requerido para acceder a este documento',
                    'codigo': 'OTP_REQUERIDO_VER',
                    'nivel_seguridad': documento.nivel_seguridad
                }), 428  # Precondition Required
            
            # Validar OTP
            if not usuario_actual.validar_otp(codigo_otp):
                return jsonify({
                    'error': 'Código OTP inválido',
                    'codigo': 'OTP_INVALIDO'
                }), 401
        
        # Registrar visualización
        documento.registrar_visualizacion(usuario_actual.id)
        
        # Obtener información del propietario
        propietario = Usuario.query.get(documento.propietario_id)
        
        # Construir respuesta completa
        respuesta = {
            'documento': documento.to_dict(
                incluir_estadisticas=True,
                incluir_archivo_info=True
            ),
            'propietario': propietario.to_dict() if propietario else None,
            'permisos_usuario': {
                'puede_ver': True,  # Ya validado por el decorador
                'puede_editar': documento.puede_ser_modificado_por(usuario_actual),
                'puede_eliminar': documento.puede_ser_eliminado_por(usuario_actual),
                'puede_descargar': documento.puede_ser_accedido_por(usuario_actual)
            }
        }
        
        # Solo incluir información sensible si el usuario tiene permisos altos
        if usuario_actual.es_admin() or documento.propietario_id == usuario_actual.id:
            respuesta['metadatos_sistema'] = {
                'ruta_archivo': documento.ruta_archivo,
                'nombre_archivo_sistema': documento.nombre_archivo_sistema,
                'archivo_existe': documento.obtener_ruta_completa() is not None
            }
        
        return jsonify(respuesta), 200
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo documento {documento_id}: {str(e)}")
        return jsonify({
            'error': 'Error interno obteniendo documento',
            'codigo': 'ERROR_INTERNO_OBTENCION'
        }), 500


@documentos_bp.route('/<int:documento_id>', methods=['PUT'])
@validar_contenido_json(['nombre'])
@validar_acceso_documento('editar')
@registrar_auditoria('modificar_documento')
def actualizar_documento(documento_id, usuario_actual, documento):
    """
    Actualiza metadatos de un documento existente.
    
    Endpoint: PUT /api/documentos/<id>
    Content-Type: application/json
    
    Body JSON:
    {
        "nombre": "string (requerido)",
        "descripcion": "string (opcional)",
        "categoria": "string (opcional)",
        "tags": "string (opcional)",
        "nivel_seguridad": "string (opcional)"
    }
    
    Returns:
        JSON: Información del documento actualizado
    """
    try:
        datos = request.get_json()
        
        # Validar campos requeridos
        nombre = datos.get('nombre', '').strip()
        descripcion = datos.get('descripcion', '').strip()
        categoria = datos.get('categoria', '').strip()
        tags = datos.get('tags', '').strip()
        nuevo_nivel = datos.get('nivel_seguridad', '').strip().lower()
        
        # Validaciones usando ValidadorDatos
        nombre_valido, error_nombre = ValidadorDatos.validar_nombre_documento(nombre)
        if not nombre_valido:
            return jsonify({
                'error': error_nombre,
                'codigo': 'NOMBRE_INVALIDO'
            }), 400
        
        if descripcion:
            desc_valida, error_desc = ValidadorDatos.validar_descripcion(descripcion)
            if not desc_valida:
                return jsonify({
                    'error': error_desc,
                    'codigo': 'DESCRIPCION_INVALIDA'
                }), 400
        
        # Validar cambio de nivel de seguridad si se especifica
        if nuevo_nivel and nuevo_nivel != documento.nivel_seguridad:
            nivel_valido, error_nivel = ValidadorDatos.validar_nivel_seguridad(nuevo_nivel)
            if not nivel_valido:
                return jsonify({
                    'error': error_nivel,
                    'codigo': 'NIVEL_SEGURIDAD_INVALIDO'
                }), 400
            
            # Verificar permisos para cambiar nivel de seguridad
            if nuevo_nivel == 'secreto' and not (usuario_actual.es_admin() or usuario_actual.es_supervisor()):
                return jsonify({
                    'error': 'No tienes permisos para establecer nivel secreto',
                    'codigo': 'PERMISOS_INSUFICIENTES_NIVEL_SECRETO'
                }), 403
            
            # El cambio de nivel de seguridad requiere mover el archivo
            documento.nivel_seguridad = nuevo_nivel
            if not documento.mover_a_carpeta_seguridad():
                return jsonify({
                    'error': 'Error moviendo archivo a nueva carpeta de seguridad',
                    'codigo': 'ERROR_MOVIENDO_ARCHIVO'
                }), 500
        
        # Actualizar campos
        documento.nombre = nombre
        documento.descripcion = descripcion or None
        documento.categoria = categoria or None
        documento.tags = tags or None
        documento.fecha_modificacion = datetime.utcnow()
        
        # Guardar cambios
        db.session.commit()
        
        current_app.logger.info(
            f"Documento {documento.id} actualizado por usuario {usuario_actual.email}"
        )
        
        return jsonify({
            'mensaje': 'Documento actualizado exitosamente',
            'documento': documento.to_dict(
                incluir_estadisticas=True,
                incluir_archivo_info=True
            )
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error actualizando documento {documento_id}: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Error interno actualizando documento',
            'codigo': 'ERROR_INTERNO_ACTUALIZACION'
        }), 500


@documentos_bp.route('/<int:documento_id>', methods=['DELETE'])
@validar_acceso_documento('eliminar')
@registrar_auditoria('eliminar_documento')
def eliminar_documento(documento_id, usuario_actual, documento):
    """
    Elimina un documento y su archivo asociado.
    
    Endpoint: DELETE /api/documentos/<id>
    
    Headers opcionales:
    - X-OTP-Code: Código OTP (requerido según nivel de seguridad)
    
    Returns:
        JSON: Confirmación de eliminación
    """
    try:
        # Guardar información para el log antes de eliminar
        info_documento = {
            'id': documento.id,
            'nombre': documento.nombre,
            'nivel_seguridad': documento.nivel_seguridad,
            'propietario_id': documento.propietario_id,
            'ruta_archivo': documento.ruta_archivo
        }
        
        # Eliminar archivo físico
        archivo_eliminado = documento.eliminar_archivo_fisico()
        
        # Marcar como eliminado en la base de datos (soft delete)
        documento.estado = 'eliminado'
        documento.fecha_modificacion = datetime.utcnow()
        
        db.session.commit()
        
        current_app.logger.info(
            f"Documento eliminado: {info_documento['id']} ({info_documento['nombre']}) "
            f"por usuario {usuario_actual.email} - Archivo físico: {'eliminado' if archivo_eliminado else 'no encontrado'}"
        )
        
        return jsonify({
            'mensaje': 'Documento eliminado exitosamente',
            'documento_eliminado': {
                'id': info_documento['id'],
                'nombre': info_documento['nombre'],
                'nivel_seguridad': info_documento['nivel_seguridad']
            },
            'archivo_fisico_eliminado': archivo_eliminado
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error eliminando documento {documento_id}: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Error interno eliminando documento',
            'codigo': 'ERROR_INTERNO_ELIMINACION'
        }), 500


# ===============================
# ENDPOINTS DE GESTIÓN DE ARCHIVOS
# ===============================

@documentos_bp.route('/<int:documento_id>/descargar', methods=['GET'])
@validar_acceso_documento('descargar')
@registrar_auditoria('descargar_documento')
def descargar_documento(documento_id, usuario_actual, documento):
    """
    Descarga el archivo asociado a un documento.
    
    Endpoint: GET /api/documentos/<id>/descargar
    
    Headers opcionales:
    - X-OTP-Code: Código OTP (requerido según nivel de seguridad)
    
    Returns:
        File: Archivo para descarga
    """
    try:
        # Verificar que el archivo existe
        ruta_archivo = documento.obtener_ruta_completa()
        if not ruta_archivo:
            return jsonify({
                'error': 'Archivo no encontrado en el sistema',
                'codigo': 'ARCHIVO_NO_ENCONTRADO'
            }), 404
        
        # Registrar descarga
        documento.registrar_descarga(usuario_actual.id)
        
        # Enviar archivo
        return send_file(
            ruta_archivo,
            as_attachment=True,
            download_name=documento.nombre_archivo_original or f"{documento.nombre}.{documento.extension_archivo}",
            mimetype=documento.tipo_mime
        )
        
    except Exception as e:
        current_app.logger.error(f"Error descargando documento {documento_id}: {str(e)}")
        return jsonify({
            'error': 'Error interno descargando archivo',
            'codigo': 'ERROR_INTERNO_DESCARGA'
        }), 500


# ===============================
# ENDPOINTS DE BÚSQUEDA AVANZADA
# ===============================

@documentos_bp.route('/buscar', methods=['POST'])
@validar_contenido_json(['termino'])
@requiere_autenticacion
def buscar_documentos_avanzado(usuario_actual):
    """
    Búsqueda avanzada de documentos con múltiples criterios.
    
    Endpoint: POST /api/documentos/buscar
    Content-Type: application/json
    
    Body JSON:
    {
        "termino": "string (requerido)",
        "niveles_seguridad": ["publico", "confidencial"],
        "limite": 20
    }
    
    Returns:
        JSON: Resultados de búsqueda
    """
    try:
        datos = request.get_json()
        
        termino = datos.get('termino', '').strip()
        niveles_seguridad = datos.get('niveles_seguridad', [])
        categorias = datos.get('categorias', [])
        fecha_desde = datos.get('fecha_desde')
        fecha_hasta = datos.get('fecha_hasta')
        limite = min(datos.get('limite', 20), 100)  # Máximo 100 resultados
        
        # Usar función de búsqueda del modelo
        documentos_encontrados = buscar_documentos(termino, usuario_actual, limite)
        
        # Aplicar filtros adicionales
        if niveles_seguridad:
            documentos_encontrados = [
                doc for doc in documentos_encontrados
                if doc.nivel_seguridad in niveles_seguridad
            ]
        
        if categorias:
            documentos_encontrados = [
                doc for doc in documentos_encontrados
                if doc.categoria and any(cat.lower() in doc.categoria.lower() for cat in categorias)
            ]
        
        # Filtros de fecha
        if fecha_desde:
            try:
                fecha_desde_dt = datetime.fromisoformat(fecha_desde)
                documentos_encontrados = [
                    doc for doc in documentos_encontrados
                    if doc.fecha_creacion >= fecha_desde_dt
                ]
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha_hasta_dt = datetime.fromisoformat(fecha_hasta)
                documentos_encontrados = [
                    doc for doc in documentos_encontrados
                    if doc.fecha_creacion <= fecha_hasta_dt
                ]
            except ValueError:
                pass
        
        # Construir respuesta
        resultados = []
        for doc in documentos_encontrados:
            doc_dict = doc.to_dict(incluir_archivo_info=True)
            
            # Agregar relevancia básica (cuántas veces aparece el término)
            relevancia = 0
            termino_lower = termino.lower()
            
            if termino_lower in doc.nombre.lower():
                relevancia += 3
            if doc.descripcion and termino_lower in doc.descripcion.lower():
                relevancia += 2
            if doc.categoria and termino_lower in doc.categoria.lower():
                relevancia += 1
            if doc.tags and termino_lower in doc.tags.lower():
                relevancia += 1
            
            doc_dict['relevancia'] = relevancia
            resultados.append(doc_dict)
        
        # Ordenar por relevancia
        resultados.sort(key=lambda x: x['relevancia'], reverse=True)
        
        return jsonify({
            'resultados': resultados,
            'total_encontrados': len(resultados),
            'termino_busqueda': termino,
            'filtros_aplicados': {
                'niveles_seguridad': niveles_seguridad,
                'categorias': categorias,
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error en búsqueda avanzada: {str(e)}")
        return jsonify({
            'error': 'Error interno en búsqueda',
            'codigo': 'ERROR_INTERNO_BUSQUEDA'
        }), 500

# ===============================
# ENDPOINTS DE GESTIÓN DE NIVELES
# ===============================

@documentos_bp.route('/por-nivel/<string:nivel_seguridad>', methods=['GET'])
@requiere_autenticacion
def obtener_documentos_por_nivel(nivel_seguridad, usuario_actual):
    """
    Obtiene documentos de un nivel de seguridad específico.
    
    Endpoint: GET /api/documentos/por-nivel/<nivel>
    
    Returns:
        JSON: Lista de documentos del nivel especificado
    """
    try:
        # Validar nivel de seguridad
        nivel_valido, error_nivel = ValidadorDatos.validar_nivel_seguridad(nivel_seguridad)
        if not nivel_valido:
            return jsonify({
                'error': error_nivel,
                'codigo': 'NIVEL_SEGURIDAD_INVALIDO'
            }), 400
        
        # Usar función del modelo para obtener documentos por nivel
        documentos = obtener_documentos_por_nivel_seguridad(nivel_seguridad, usuario_actual)
        
        # Convertir a diccionarios
        documentos_dict = [
            doc.to_dict(incluir_archivo_info=True)
            for doc in documentos
        ]
        
        return jsonify({
            'documentos': documentos_dict,
            'nivel_seguridad': nivel_seguridad,
            'total_encontrados': len(documentos_dict),
            'acceso_permitido': True
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo documentos por nivel {nivel_seguridad}: {str(e)}")
        return jsonify({
            'error': 'Error interno obteniendo documentos por nivel',
            'codigo': 'ERROR_INTERNO_NIVEL'
        }), 500