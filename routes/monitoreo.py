"""
Sistema de monitoreo y métricas del Sistema de Gestión de Documentos Seguros
Endpoints para ver performance, logs y estadísticas del sistema
Autor: José Luis Cortese
Asignatura: Backend - IPG 2025
Fecha: Agosto 17, 2025
"""
import psutil
import os
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from utils.decoradores import requiere_autenticacion, requiere_rol
from utils.sistema_cache import MetricasCache, gestor_cache
from utils.sistema_loggin import AnalizadorLogs, gestor_logging
from utils.middleware_optimizacion import MonitorRateLimiting

# Crear blueprint para monitoreo
monitoreo_bp = Blueprint('monitoreo', __name__, url_prefix='/api/monitoreo')

@monitoreo_bp.route('/salud', methods=['GET'])
def verificar_salud_sistema():
    """
    Endpoint de health check con información del sistema
    """
    try:
        # Información básica del sistema
        uso_cpu = psutil.cpu_percent(interval=1)
        memoria = psutil.virtual_memory()
        disco = psutil.disk_usage('/')
        
        # Información de la aplicación
        proceso_actual = psutil.Process()
        memoria_app = proceso_actual.memory_info()
        
        salud = {
            'estado': 'saludable',
            'timestamp': datetime.utcnow().isoformat(),
            'sistema': {
                'cpu_porcentaje': uso_cpu,
                'memoria_total_gb': round(memoria.total / (1024**3), 2),
                'memoria_disponible_gb': round(memoria.available / (1024**3), 2),
                'memoria_uso_porcentaje': memoria.percent,
                'disco_total_gb': round(disco.total / (1024**3), 2),
                'disco_libre_gb': round(disco.free / (1024**3), 2),
                'disco_uso_porcentaje': round((disco.used / disco.total) * 100, 2)
            },
            'aplicacion': {
                'memoria_rss_mb': round(memoria_app.rss / (1024**2), 2),
                'memoria_vms_mb': round(memoria_app.vms / (1024**2), 2),
                'pid': proceso_actual.pid,
                'tiempo_ejecucion_horas': round((datetime.now() - datetime.fromtimestamp(proceso_actual.create_time())).total_seconds() / 3600, 2)
            },
            'servicios': {
                'cache': 'activo',
                'rate_limiting': 'activo',
                'logging': 'activo',
                'compresion': 'activo'
            }
        }
        
        # Verificar estado de servicios críticos
        if uso_cpu > 90:
            salud['estado'] = 'advertencia'
            salud['alertas'] = salud.get('alertas', [])
            salud['alertas'].append('CPU usage alto')
        
        if memoria.percent > 90:
            salud['estado'] = 'advertencia'
            salud['alertas'] = salud.get('alertas', [])
            salud['alertas'].append('Memoria usage alto')
        
        return jsonify(salud), 200
        
    except Exception as e:
        return jsonify({
            'estado': 'error',
            'mensaje': f'Error verificando salud del sistema: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@monitoreo_bp.route('/performance', methods=['GET'])
@requiere_autenticacion
@requiere_rol(['supervisor', 'admin'])
def obtener_metricas_performance():
    """
    Obtiene métricas detalladas de performance del sistema
    Solo accesible para supervisores y administradores
    """
    try:
        # Métricas de caché
        estadisticas_cache = MetricasCache.obtener_estadisticas_cache()
        
        # Métricas de performance de logs
        metricas_performance = AnalizadorLogs.obtener_metricas_performance()
        
        # Métricas de rate limiting
        stats_rate_limiting = MonitorRateLimiting.obtener_estadisticas_rate_limiting()
        limites_configurados = MonitorRateLimiting.obtener_limites_configurados()
        
        # Información de archivos de logs
        info_logs = {}
        archivos_log = ['logs/sistema_documentos.log', 'logs/auditoria.log', 'logs/performance.log', 'logs/errores.log']
        
        for archivo in archivos_log:
            if os.path.exists(archivo):
                stat = os.stat(archivo)
                info_logs[archivo] = {
                    'tamano_mb': round(stat.st_size / (1024**2), 2),
                    'ultima_modificacion': datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'cache': estadisticas_cache,
            'performance': metricas_performance,
            'rate_limiting': {
                'estadisticas': stats_rate_limiting,
                'configuracion': limites_configurados
            },
            'logs': info_logs
        }), 200
        
    except Exception as e:
        gestor_logging.registrar_error_critico(
            error=e,
            contexto={'endpoint': 'obtener_metricas_performance'}
        )
        
        return jsonify({
            'error': 'Error obteniendo métricas de performance',
            'mensaje': str(e)
        }), 500

@monitoreo_bp.route('/auditoria', methods=['GET'])
@requiere_autenticacion
@requiere_rol(['supervisor', 'admin'])
def obtener_resumen_auditoria():
    """
    Obtiene resumen de actividad y auditoría del sistema
    """
    try:
        # Parámetros de consulta
        horas = request.args.get('horas', 24, type=int)
        horas = min(horas, 168)  # Máximo 7 días
        
        # Obtener resumen de auditoría
        resumen_auditoria = AnalizadorLogs.obtener_resumen_auditoria(horas=horas)
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'periodo_horas': horas,
            'resumen': resumen_auditoria
        }), 200
        
    except Exception as e:
        gestor_logging.registrar_error_critico(
            error=e,
            contexto={'endpoint': 'obtener_resumen_auditoria'}
        )
        
        return jsonify({
            'error': 'Error obteniendo resumen de auditoría',
            'mensaje': str(e)
        }), 500

@monitoreo_bp.route('/cache/estadisticas', methods=['GET'])
@requiere_autenticacion
@requiere_rol(['admin'])
def obtener_estadisticas_cache():
    """
    Obtiene estadísticas detalladas del sistema de caché
    Solo para administradores
    """
    try:
        estadisticas = MetricasCache.obtener_estadisticas_cache()
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'estadisticas': estadisticas
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Error obteniendo estadísticas de caché',
            'mensaje': str(e)
        }), 500

@monitoreo_bp.route('/cache/limpiar', methods=['POST'])
@requiere_autenticacion
@requiere_rol(['admin'])
def limpiar_cache():
    """
    Limpia completamente el caché del sistema
    Solo para administradores
    """
    try:
        # Obtener parámetros
        tipo_limpieza = request.json.get('tipo', 'todo') if request.json else 'todo'
        usuario_especifico = request.json.get('usuario_id') if request.json else None
        
        if tipo_limpieza == 'usuario' and usuario_especifico:
            # Limpiar caché de usuario específico
            gestor_cache.invalidar_cache_usuario(usuario_especifico)
            mensaje = f'Caché del usuario {usuario_especifico} limpiado'
            
        elif tipo_limpieza == 'documentos':
            # Limpiar caché relacionado con documentos
            gestor_cache.invalidar_cache_documentos()
            mensaje = 'Caché de documentos limpiado'
            
        else:
            # Limpiar todo el caché
            from utils.sistema_cache import cache
            cache.clear()
            mensaje = 'Caché completo limpiado'
        
        # Registrar acción
        gestor_logging.registrar_accion_auditoria(
            accion='limpiar_cache',
            detalles={'tipo': tipo_limpieza, 'usuario_especifico': usuario_especifico},
            resultado='exito'
        )
        
        return jsonify({
            'mensaje': mensaje,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        gestor_logging.registrar_error_critico(
            error=e,
            contexto={'endpoint': 'limpiar_cache'}
        )
        
        return jsonify({
            'error': 'Error limpiando caché',
            'mensaje': str(e)
        }), 500

@monitoreo_bp.route('/dashboard', methods=['GET'])
@requiere_autenticacion
@requiere_rol(['supervisor', 'admin'])
def obtener_dashboard_monitoreo():
    """
    Obtiene datos consolidados para dashboard de monitoreo
    """
    try:
        # Obtener datos de los últimos 30 minutos para dashboard
        ahora = datetime.utcnow()
        hace_30_min = ahora - timedelta(minutes=30)
        
        # Métricas básicas del sistema
        uso_cpu = psutil.cpu_percent()
        memoria = psutil.virtual_memory()
        
        # Resumen de auditoría de la última hora
        resumen_auditoria = AnalizadorLogs.obtener_resumen_auditoria(horas=1)
        
        # Estadísticas de caché
        stats_cache = MetricasCache.obtener_estadisticas_cache()
        
        # Dashboard consolidado
        dashboard = {
            'timestamp': ahora.isoformat(),
            'periodo': '30 minutos',
            'sistema': {
                'cpu_porcentaje': uso_cpu,
                'memoria_porcentaje': memoria.percent,
                'estado': 'normal' if uso_cpu < 80 and memoria.percent < 80 else 'alerta'
            },
            'actividad_reciente': {
                'total_acciones': resumen_auditoria.get('total_acciones', 0),
                'usuarios_activos': resumen_auditoria.get('usuarios_activos', 0),
                'errores': resumen_auditoria.get('errores', 0),
                'endpoints_populares': list(resumen_auditoria.get('endpoints_mas_usados', {}).keys())[:5]
            },
            'cache': {
                'tipo': stats_cache.get('tipo_cache', 'Desconocido'),
                'hits_porcentaje': stats_cache.get('ratio_hit', 0),
                'memoria_usada': stats_cache.get('memoria_usada', 'N/A')
            },
            'alertas': []
        }
        
        # Generar alertas
        if uso_cpu > 80:
            dashboard['alertas'].append({
                'tipo': 'warning',
                'mensaje': f'CPU usage alto: {uso_cpu}%'
            })
        
        if memoria.percent > 80:
            dashboard['alertas'].append({
                'tipo': 'warning', 
                'mensaje': f'Memoria usage alto: {memoria.percent}%'
            })
        
        if resumen_auditoria.get('errores', 0) > 5:
            dashboard['alertas'].append({
                'tipo': 'error',
                'mensaje': f'Muchos errores en la última hora: {resumen_auditoria["errores"]}'
            })
        
        return jsonify(dashboard), 200
        
    except Exception as e:
        gestor_logging.registrar_error_critico(
            error=e,
            contexto={'endpoint': 'obtener_dashboard_monitoreo'}
        )
        
        return jsonify({
            'error': 'Error obteniendo dashboard de monitoreo',
            'mensaje': str(e)
        }), 500

@monitoreo_bp.route('/logs/recientes', methods=['GET'])
@requiere_autenticacion
@requiere_rol(['admin'])
def obtener_logs_recientes():
    """
    Obtiene las últimas entradas de logs del sistema
    Solo para administradores
    """
    try:
        tipo_log = request.args.get('tipo', 'sistema')  # sistema, auditoria, performance, errores
        limite = request.args.get('limite', 50, type=int)
        limite = min(limite, 200)  # Máximo 200 entradas
        
        archivo_log = {
            'sistema': 'logs/sistema_documentos.log',
            'auditoria': 'logs/auditoria.log',
            'performance': 'logs/performance.log',
            'errores': 'logs/errores.log'
        }.get(tipo_log, 'logs/sistema_documentos.log')
        
        if not os.path.exists(archivo_log):
            return jsonify({
                'error': f'Archivo de log {tipo_log} no encontrado'
            }), 404
        
        # Leer últimas líneas del archivo
        with open(archivo_log, 'r', encoding='utf-8') as f:
            lineas = f.readlines()
        
        # Obtener últimas entradas
        ultimas_lineas = lineas[-limite:] if len(lineas) > limite else lineas
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'tipo_log': tipo_log,
            'total_entradas': len(ultimas_lineas),
            'entradas': [linea.strip() for linea in ultimas_lineas]
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Error obteniendo logs recientes',
            'mensaje': str(e)
        }), 500