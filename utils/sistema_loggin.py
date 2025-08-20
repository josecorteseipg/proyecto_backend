
import os
import json
import logging
from datetime import datetime
from functools import wraps
from logging.handlers import RotatingFileHandler
from flask import request, g, current_app
import colorlog

class GestorLoggingAvanzado:
    """
    Gestor de logging que registra acciones, errores y métricas de performance
    """
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa el sistema de logging con la app Flask"""
        self.configurar_logging_principal(app)
        self.configurar_logging_auditoria(app)
        self.configurar_logging_performance(app)
        self.configurar_logging_errores(app)
    
    def configurar_logging_principal(self, app):
        """Configura el logger principal de la aplicación"""
        # Crear directorio de logs si no existe
        os.makedirs('logs', exist_ok=True)
        
        # Configurar logger principal con colores para desarrollo
        if app.debug:
            handler = colorlog.StreamHandler()
            handler.setFormatter(colorlog.ColoredFormatter(
                '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            ))
        else:
            # Para producción, usar archivo rotativo
            handler = RotatingFileHandler(
                app.config.get('LOG_FILE_PATH', 'logs/sistema_documentos.log'),
                maxBytes=app.config.get('LOG_MAX_BYTES', 10*1024*1024),
                backupCount=app.config.get('LOG_BACKUP_COUNT', 5)
            )
            handler.setFormatter(logging.Formatter(
                app.config.get('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ))
        
        # Configurar nivel de logging
        nivel_log = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper())
        app.logger.setLevel(nivel_log)
        app.logger.addHandler(handler)
        
        # Eliminar handlers por defecto de Flask para evitar duplicados
        app.logger.handlers = [handler]
        
        app.logger.info("🚀 Sistema de logging avanzado inicializado")
    
    def configurar_logging_auditoria(self, app):
        """Configura logger específico para auditoría de acciones"""
        self.logger_auditoria = logging.getLogger('auditoria')
        self.logger_auditoria.setLevel(logging.INFO)
        
        handler_auditoria = RotatingFileHandler(
            'logs/auditoria.log',
            maxBytes=10*1024*1024,
            backupCount=10
        )
        handler_auditoria.setFormatter(logging.Formatter(
            '%(asctime)s - AUDIT - %(message)s'
        ))
        
        self.logger_auditoria.addHandler(handler_auditoria)
        
    def configurar_logging_performance(self, app):
        """Configura logger específico para métricas de performance"""
        self.logger_performance = logging.getLogger('performance')
        self.logger_performance.setLevel(logging.INFO)
        
        handler_performance = RotatingFileHandler(
            'logs/performance.log',
            maxBytes=5*1024*1024,
            backupCount=5
        )
        handler_performance.setFormatter(logging.Formatter(
            '%(asctime)s - PERF - %(message)s'
        ))
        
        self.logger_performance.addHandler(handler_performance)
    
    def configurar_logging_errores(self, app):
        """Configura logger específico para errores críticos"""
        self.logger_errores = logging.getLogger('errores')
        self.logger_errores.setLevel(logging.ERROR)
        
        handler_errores = RotatingFileHandler(
            'logs/errores.log',
            maxBytes=10*1024*1024,
            backupCount=10
        )
        handler_errores.setFormatter(logging.Formatter(
            '%(asctime)s - ERROR - %(levelname)s - %(name)s - %(message)s\n'
            'Request: %(pathname)s:%(lineno)d\n'
            'Traceback: %(exc_info)s\n'
            '---'
        ))
        
        self.logger_errores.addHandler(handler_errores)
    
    def registrar_accion_auditoria(self, accion, usuario_id=None, detalles=None, resultado='exito'):
        """
        Registra una acción para auditoría
        
        Args:
            accion: Tipo de acción realizada
            usuario_id: ID del usuario que realizó la acción
            detalles: Detalles adicionales de la acción
            resultado: 'exito', 'error', 'denegado'
        """
        entrada_auditoria = {
            'timestamp': datetime.utcnow().isoformat(),
            'accion': accion,
            'usuario_id': usuario_id,
            'ip_cliente': request.remote_addr if request else 'N/A',
            'user_agent': request.headers.get('User-Agent', 'N/A') if request else 'N/A',
            'endpoint': request.endpoint if request else 'N/A',
            'metodo': request.method if request else 'N/A',
            'resultado': resultado,
            'detalles': detalles or {}
        }
        
        self.logger_auditoria.info(json.dumps(entrada_auditoria, ensure_ascii=False))
    
    def registrar_metrica_performance(self, operacion, tiempo_ms, detalles=None):
        """
        Registra métricas de performance
        
        Args:
            operacion: Nombre de la operación
            tiempo_ms: Tiempo en milisegundos
            detalles: Información adicional
        """
        entrada_performance = {
            'timestamp': datetime.utcnow().isoformat(),
            'operacion': operacion,
            'tiempo_ms': tiempo_ms,
            'endpoint': request.endpoint if request else 'N/A',
            'metodo': request.method if request else 'N/A',
            'detalles': detalles or {}
        }
        
        self.logger_performance.info(json.dumps(entrada_performance, ensure_ascii=False))
    
    def registrar_error_critico(self, error, contexto=None):
        """
        Registra errores críticos del sistema
        
        Args:
            error: Excepción o mensaje de error
            contexto: Contexto adicional del error
        """
        entrada_error = {
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(error),
            'tipo_error': type(error).__name__ if isinstance(error, Exception) else 'Error',
            'endpoint': request.endpoint if request else 'N/A',
            'metodo': request.method if request else 'N/A',
            'usuario_id': getattr(g, 'usuario_actual', {}).get('id') if hasattr(g, 'usuario_actual') else None,
            'contexto': contexto or {}
        }
        
        self.logger_errores.error(json.dumps(entrada_error, ensure_ascii=False))

# Instancia global del gestor
gestor_logging = GestorLoggingAvanzado()

def auditar_accion(accion, incluir_detalles=True):
    """
    Decorador para auditar automáticamente acciones de endpoints
    
    Args:
        accion: Tipo de acción a registrar
        incluir_detalles: Si incluir detalles de la request
    """
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            inicio = datetime.utcnow()
            usuario_id = None
            
            # Obtener usuario actual si existe
            if hasattr(g, 'usuario_actual') and g.usuario_actual:
                usuario_id = g.usuario_actual.id
            
            # Preparar detalles
            detalles = {}
            if incluir_detalles:
                if request.json:
                    # Filtrar campos sensibles
                    detalles['request_data'] = {
                        k: v for k, v in request.json.items() 
                        if k not in ['password', 'password_hash', 'token']
                    }
                if request.args:
                    detalles['query_params'] = dict(request.args)
            
            try:
                # Ejecutar función
                resultado = func(*args, **kwargs)
                
                # Calcular tiempo de ejecución
                tiempo_ejecucion = (datetime.utcnow() - inicio).total_seconds() * 1000
                
                # Registrar auditoría de éxito
                gestor_logging.registrar_accion_auditoria(
                    accion=accion,
                    usuario_id=usuario_id,
                    detalles=detalles,
                    resultado='exito'
                )
                
                # Registrar performance si toma más de 100ms
                if tiempo_ejecucion > 100:
                    gestor_logging.registrar_metrica_performance(
                        operacion=accion,
                        tiempo_ms=tiempo_ejecucion,
                        detalles={'funcion': func.__name__}
                    )
                
                return resultado
                
            except Exception as e:
                # Registrar auditoría de error
                gestor_logging.registrar_accion_auditoria(
                    accion=accion,
                    usuario_id=usuario_id,
                    detalles={**detalles, 'error': str(e)},
                    resultado='error'
                )
                
                # Registrar error crítico
                gestor_logging.registrar_error_critico(
                    error=e,
                    contexto={'accion': accion, 'funcion': func.__name__}
                )
                
                raise
        
        return wrapper
    return decorador

def medir_performance(operacion):
    """
    Decorador para medir automáticamente performance de funciones
    """
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            inicio = datetime.utcnow()
            
            resultado = func(*args, **kwargs)
            
            tiempo_ejecucion = (datetime.utcnow() - inicio).total_seconds() * 1000
            
            gestor_logging.registrar_metrica_performance(
                operacion=operacion,
                tiempo_ms=tiempo_ejecucion,
                detalles={'funcion': func.__name__}
            )
            
            return resultado
        
        return wrapper
    return decorador

class AnalizadorLogs:
    """
    Clase para analizar logs y generar reportes
    """
    
    @staticmethod
    def obtener_resumen_auditoria(horas=24):
        """
        Obtiene resumen de actividad de auditoría de las últimas horas
        """
        try:
            with open('logs/auditoria.log', 'r', encoding='utf-8') as f:
                lineas = f.readlines()
            
            # Filtrar últimas horas
            ahora = datetime.utcnow()
            limite = ahora.timestamp() - (horas * 3600)
            
            acciones = []
            for linea in lineas[-1000:]:  # Últimas 1000 entradas
                try:
                    # Extraer JSON de la línea
                    inicio_json = linea.find('{')
                    if inicio_json != -1:
                        datos = json.loads(linea[inicio_json:])
                        timestamp = datetime.fromisoformat(datos['timestamp'])
                        
                        if timestamp.timestamp() > limite:
                            acciones.append(datos)
                except:
                    continue
            
            # Generar resumen
            resumen = {
                'total_acciones': len(acciones),
                'acciones_por_tipo': {},
                'usuarios_activos': set(),
                'errores': 0,
                'endpoints_mas_usados': {}
            }
            
            for accion in acciones:
                # Contar por tipo
                tipo = accion.get('accion', 'desconocido')
                resumen['acciones_por_tipo'][tipo] = resumen['acciones_por_tipo'].get(tipo, 0) + 1
                
                # Usuarios activos
                if accion.get('usuario_id'):
                    resumen['usuarios_activos'].add(accion['usuario_id'])
                
                # Errores
                if accion.get('resultado') == 'error':
                    resumen['errores'] += 1
                
                # Endpoints
                endpoint = accion.get('endpoint', 'desconocido')
                resumen['endpoints_mas_usados'][endpoint] = resumen['endpoints_mas_usados'].get(endpoint, 0) + 1
            
            resumen['usuarios_activos'] = len(resumen['usuarios_activos'])
            
            return resumen
            
        except Exception as e:
            current_app.logger.error(f"Error analizando logs de auditoría: {e}")
            return {'error': 'No se pudieron analizar los logs'}
    
    @staticmethod
    def obtener_metricas_performance():
        """
        Obtiene métricas de performance del sistema
        """
        try:
            with open('logs/performance.log', 'r', encoding='utf-8') as f:
                lineas = f.readlines()
            
            metricas = []
            for linea in lineas[-500:]:  # Últimas 500 entradas
                try:
                    inicio_json = linea.find('{')
                    if inicio_json != -1:
                        datos = json.loads(linea[inicio_json:])
                        metricas.append(datos)
                except:
                    continue
            
            if not metricas:
                return {'info': 'No hay métricas de performance disponibles'}
            
            # Calcular estadísticas
            tiempos = [m['tiempo_ms'] for m in metricas]
            operaciones = {}
            
            for metrica in metricas:
                op = metrica['operacion']
                if op not in operaciones:
                    operaciones[op] = []
                operaciones[op].append(metrica['tiempo_ms'])
            
            resumen = {
                'tiempo_promedio_ms': sum(tiempos) / len(tiempos),
                'tiempo_maximo_ms': max(tiempos),
                'tiempo_minimo_ms': min(tiempos),
                'total_mediciones': len(tiempos),
                'operaciones_lentas': len([t for t in tiempos if t > 1000]),  # > 1 segundo
                'por_operacion': {}
            }
            
            for op, tiempos_op in operaciones.items():
                resumen['por_operacion'][op] = {
                    'promedio_ms': sum(tiempos_op) / len(tiempos_op),
                    'maximo_ms': max(tiempos_op),
                    'total_mediciones': len(tiempos_op)
                }
            
            return resumen
            
        except Exception as e:
            current_app.logger.error(f"Error analizando métricas de performance: {e}")
            return {'error': 'No se pudieron analizar las métricas'}