
import json
import hashlib
from functools import wraps
from flask import request, g, current_app
from flask_caching import Cache

# Instancia global de caché
cache = Cache()

class GestorCacheInteligente:
    """
    Gestor de caché que optimiza automáticamente según el tipo de contenido
    """
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa el sistema de caché con la app Flask"""
        try:
            # Configurar caché principal (Redis)
            cache.init_app(app, config={
                'CACHE_TYPE': app.config.get('CACHE_TYPE', 'redis'),
                'CACHE_REDIS_URL': app.config.get('CACHE_REDIS_URL'),
                'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_DEFAULT_TIMEOUT', 300)
            })
            app.logger.info("Sistema de caché Redis inicializado")
            
        except Exception as e:
            # Fallback a caché simple si Redis no está disponible
            app.logger.warning(f"Redis no disponible, usando caché simple: {e}")
            cache.init_app(app, config={
                'CACHE_TYPE': app.config.get('CACHE_FALLBACK_TYPE', 'simple'),
                'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_FALLBACK_TIMEOUT', 180)
            })
    
    def generar_clave_cache(self, prefijo, usuario_id=None, **kwargs):
        """
        Genera clave única de caché considerando usuario y parámetros
        """
        elementos_clave = [prefijo]
        
        if usuario_id:
            elementos_clave.append(f"user_{usuario_id}")
        
        # Agregar parámetros de query ordenados
        if hasattr(request, 'args') and request.args:
            params_ordenados = sorted(request.args.items())
            params_str = json.dumps(params_ordenados, sort_keys=True)
            hash_params = hashlib.md5(params_str.encode()).hexdigest()[:8]
            elementos_clave.append(f"params_{hash_params}")
        
        # Agregar kwargs adicionales
        if kwargs:
            kwargs_str = json.dumps(kwargs, sort_keys=True)
            hash_kwargs = hashlib.md5(kwargs_str.encode()).hexdigest()[:8]
            elementos_clave.append(f"extra_{hash_kwargs}")
        
        return ":".join(elementos_clave)
    
    def invalidar_cache_usuario(self, usuario_id):
        """
        Invalida todo el caché relacionado con un usuario específico
        """
        try:
            # Obtener todas las claves que contienen el usuario_id
            patron = f"*user_{usuario_id}*"
            claves = cache.cache._write_client.keys(patron)
            
            if claves:
                cache.cache._write_client.delete(*claves)
                current_app.logger.info(f"Cache invalidado para usuario {usuario_id}: {len(claves)} entradas")
                
        except Exception as e:
            current_app.logger.warning(f"Error invalidando caché de usuario {usuario_id}: {e}")
    
    def invalidar_cache_documentos(self):
        """
        Invalida caché relacionado con listados de documentos
        """
        try:
            patrones = [
                "documentos:*",
                "estadisticas:*", 
                "busqueda:*"
            ]
            
            total_invalidadas = 0
            for patron in patrones:
                claves = cache.cache._write_client.keys(patron)
                if claves:
                    cache.cache._write_client.delete(*claves)
                    total_invalidadas += len(claves)
            
            if total_invalidadas > 0:
                current_app.logger.info(f"Cache de documentos invalidado: {total_invalidadas} entradas")
                
        except Exception as e:
            current_app.logger.warning(f"Error invalidando caché de documentos: {e}")

# Instancia global del gestor
gestor_cache = GestorCacheInteligente()

def cache_inteligente(prefijo, timeout=None, por_usuario=True, invalidar_en=['POST', 'PUT', 'DELETE']):
    """
    Decorador de caché inteligente que se adapta automáticamente
    
    Args:
        prefijo: Prefijo para la clave de caché
        timeout: Tiempo de expiración (None = usar default)
        por_usuario: Si debe considerar el usuario actual
        invalidar_en: Métodos HTTP que invalidan el caché
    """
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Verificar si el método actual invalida caché
            if request.method in invalidar_en:
                # Ejecutar función e invalidar caché después
                resultado = func(*args, **kwargs)
                
                if por_usuario and hasattr(g, 'usuario_actual'):
                    gestor_cache.invalidar_cache_usuario(g.usuario_actual.id)
                
                gestor_cache.invalidar_cache_documentos()
                return resultado
            
            # Para métodos GET, intentar usar caché
            if request.method == 'GET':
                usuario_id = None
                if por_usuario and hasattr(g, 'usuario_actual'):
                    usuario_id = g.usuario_actual.id
                
                clave_cache = gestor_cache.generar_clave_cache(
                    prefijo, 
                    usuario_id=usuario_id,
                    **kwargs
                )
                
                # Intentar obtener del caché
                try:
                    resultado_cache = cache.get(clave_cache)
                    if resultado_cache is not None:
                        current_app.logger.debug(f"Cache HIT: {clave_cache}")
                        return resultado_cache
                except Exception as e:
                    current_app.logger.warning(f"Error leyendo caché: {e}")
                
                # Ejecutar función y guardar en caché
                resultado = func(*args, **kwargs)
                
                try:
                    timeout_real = timeout or current_app.config.get('CACHE_DEFAULT_TIMEOUT', 300)
                    cache.set(clave_cache, resultado, timeout=timeout_real)
                    current_app.logger.debug(f"Cache SET: {clave_cache}")
                except Exception as e:
                    current_app.logger.warning(f"Error guardando en caché: {e}")
                
                return resultado
            
            # Para otros métodos, ejecutar directamente
            return func(*args, **kwargs)
        
        return wrapper
    return decorador

def cache_documentos_list(timeout=300):
    """Cache específico para listados de documentos con paginación"""
    return cache_inteligente('documentos', timeout=timeout, por_usuario=True)

def cache_estadisticas(timeout=600):
    """Cache específico para estadísticas (más tiempo)"""
    return cache_inteligente('estadisticas', timeout=timeout, por_usuario=True)

def cache_busqueda(timeout=180):
    """Cache específico para búsquedas (menos tiempo por ser más dinámico)"""
    return cache_inteligente('busqueda', timeout=timeout, por_usuario=True)

def cache_documento_detalle(timeout=900):
    """Cache específico para detalles de documento individual"""
    return cache_inteligente('documento_detalle', timeout=timeout, por_usuario=True)

class MetricasCache:
    """
    Clase para recopilar métricas del sistema de caché
    """
    
    @staticmethod
    def obtener_estadisticas_cache():
        """
        Obtiene estadísticas del uso del caché
        """
        try:
            info_redis = cache.cache._write_client.info()
            
            return {
                'tipo_cache': 'Redis',
                'memoria_usada': info_redis.get('used_memory_human', 'N/A'),
                'claves_totales': info_redis.get('keyspace_hits', 0) + info_redis.get('keyspace_misses', 0),
                'hits': info_redis.get('keyspace_hits', 0),
                'misses': info_redis.get('keyspace_misses', 0),
                'ratio_hit': round(
                    info_redis.get('keyspace_hits', 0) / 
                    max(1, info_redis.get('keyspace_hits', 0) + info_redis.get('keyspace_misses', 0)) * 100, 
                    2
                ),
                'clientes_conectados': info_redis.get('connected_clients', 0)
            }
        except:
            return {
                'tipo_cache': 'Simple/Fallback',
                'estado': 'Activo',
                'info': 'Caché en memoria local'
            }