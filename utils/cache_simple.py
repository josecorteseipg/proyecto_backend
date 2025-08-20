"""
Implementa caché en memoria para desarrollo sin dependencias externas
"""
import json
import hashlib
import time
from functools import wraps
from flask import request, g, current_app

class CacheSimple:
    """
    Implementación simple de caché en memoria
    """
    
    def __init__(self):
        self.store = {}
        self.expiration = {}
    
    def get(self, key):
        """Obtiene valor del caché"""
        if key in self.store:
            # Verificar si ha expirado
            if key in self.expiration and time.time() > self.expiration[key]:
                del self.store[key]
                del self.expiration[key]
                return None
            return self.store[key]
        return None
    
    def set(self, key, value, timeout=300):
        """Guarda valor en caché"""
        self.store[key] = value
        if timeout:
            self.expiration[key] = time.time() + timeout
    
    def delete(self, key):
        """Elimina valor del caché"""
        if key in self.store:
            del self.store[key]
        if key in self.expiration:
            del self.expiration[key]
    
    def clear(self):
        """Limpia todo el caché"""
        self.store.clear()
        self.expiration.clear()
    
    def keys(self, pattern=None):
        """Obtiene claves que coinciden con patrón"""
        if pattern:
            # Implementación simple de pattern matching
            import fnmatch
            return [k for k in self.store.keys() if fnmatch.fnmatch(k, pattern)]
        return list(self.store.keys())

# Instancia global de caché simple
cache = CacheSimple()

class GestorCacheInteligente:
    """
    Gestor de caché que optimiza automáticamente según el tipo de contenido
    Versión simplificada sin Redis
    """
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa el sistema de caché con la app Flask"""
        global cache
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['cache'] = cache
        
        app.logger.info("Sistema de caché simple inicializado (memoria local)")
    
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
            claves_a_eliminar = []
            for clave in cache.keys():
                if f"user_{usuario_id}" in clave:
                    claves_a_eliminar.append(clave)
            
            for clave in claves_a_eliminar:
                cache.delete(clave)
                
            if claves_a_eliminar:
                current_app.logger.info(f"Cache invalidado para usuario {usuario_id}: {len(claves_a_eliminar)} entradas")
                
        except Exception as e:
            current_app.logger.warning(f"Error invalidando caché de usuario {usuario_id}: {e}")
    
    def invalidar_cache_documentos(self):
        """
        Invalida caché relacionado con listados de documentos
        """
        try:
            patrones = ["documentos:*", "estadisticas:*", "busqueda:*"]
            
            claves_a_eliminar = []
            for patron in patrones:
                claves_a_eliminar.extend(cache.keys(patron))
            
            for clave in claves_a_eliminar:
                cache.delete(clave)
            
            if claves_a_eliminar:
                current_app.logger.info(f"Cache de documentos invalidado: {len(claves_a_eliminar)} entradas")
                
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
                        current_app.logger.debug(f"Cache Id: {clave_cache}")
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
            total_claves = len(cache.store)
            memoria_aprox = sum(len(str(k)) + len(str(v)) for k, v in cache.store.items())
            
            return {
                'tipo_cache': 'Simple (Memoria Local)',
                'total_claves': total_claves,
                'memoria_usada_aprox': f"{memoria_aprox / 1024:.2f} KB",
                'estado': 'Activo',
                'info': 'Caché en memoria local para desarrollo'
            }
        except:
            return {
                'tipo_cache': 'Simple/Error',
                'estado': 'Error',
                'info': 'Error obteniendo estadísticas'
            }