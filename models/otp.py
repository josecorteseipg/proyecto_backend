import pyotp
import qrcode
import os
from flask import current_app
from datetime import datetime, timedelta
class GestorOTP:
    @staticmethod
    def generar_otp_para_usuario(email_usuario, nombre_completo=None):
        """
        Genera código OTP y QR para un usuario específico.
        Integra y españoliza la función original generar_otp().
        
        Args:
            email_usuario (str): Email del usuario (equivale al rutusuario original)
            nombre_completo (str): Nombre completo del usuario para el QR
        
        Returns:
            dict: Diccionario con key32, url y ruta del QR generado
        """
        try:
            # Generar clave base32 aleatoria
            clave_base32 = pyotp.random_base32()
            
            # Crear objeto TOTP
            generador_totp = pyotp.TOTP(clave_base32)
            
            # Generar URL para QR con issuer personalizado
            nombre_para_qr = nombre_completo or email_usuario
            url_qr = generador_totp.provisioning_uri(
                name=nombre_para_qr,
                issuer_name=current_app.config.get('OTP_ISSUER_NAME', 'IPG_Backend')
            )
            
            # Generar archivo QR
            carpeta_qr = current_app.config.get('QR_FOLDER', 'qr_codes')
            os.makedirs(carpeta_qr, exist_ok=True)
            
            nombre_archivo_qr = f"qr_{email_usuario.replace('@', '_').replace('.', '_')}.png"
            ruta_completa_qr = os.path.join(carpeta_qr, nombre_archivo_qr)
            
            # Crear y guardar QR
            qrcode.make(url_qr).save(ruta_completa_qr)
            
            # Datos a retornar (mantiene estructura similar al original)
            datos_otp = {
                'clave_base32': clave_base32,
                'url_qr': url_qr,
                'archivo_qr': nombre_archivo_qr,
                'ruta_completa_qr': ruta_completa_qr,
                'email_usuario': email_usuario,
                'fecha_generacion': datetime.utcnow().isoformat()
            }
            
            return datos_otp
            
        except Exception as e:
            # Log del error para debugging
            current_app.logger.error(f"Error generando OTP para {email_usuario}: {str(e)}")
            return None
    
    
    @staticmethod
    def validar_otp_codigo(codigo_otp, clave_base32_generada):
        """
        Valida un código OTP contra la clave base32.
        Adaptación de la función original validar_otp().
        
        Args:
            codigo_otp (str): Código OTP ingresado por el usuario
            clave_base32_generada (str): Clave base32 previamente generada
        
        Returns:
            dict: Resultado de la validación con detalles
        """
        try:
            import time
            # Crear objeto TOTP con la clave base32
            verificador_totp = pyotp.TOTP(clave_base32_generada)
            
            # Obtener código actual
            codigo_actual = verificador_totp.now()
            timestamp_actual = int(time.time())            
            # Validar código (también permite códigos anteriores/posteriores para tolerancia)
            es_valido = verificador_totp.verify(codigo_otp, valid_window=1)
            for i in range(-2, 3):
                timestamp_test = timestamp_actual + (i * 30)
                codigo_test = verificador_totp.at(timestamp_test)
                match = codigo_test == codigo_otp
            resultado = {
                'es_valido': es_valido,
                'codigo_ingresado': codigo_otp,
                'codigo_actual_servidor': codigo_actual,
                'timestamp': timestamp_actual,
                'mensaje': 'OTP válido' if es_valido else 'OTP inválido',
                'timestamp_validacion': datetime.utcnow().isoformat()
            }
            
            return resultado
            
        except Exception as e:
            current_app.logger.error(f"Error validando OTP: {str(e)}")
            return {
                'es_valido': False,
                'mensaje': 'Error interno en validación OTP',
                'error': str(e)
            }
    
    
    @staticmethod
    def requiere_otp_para_accion(accion, nivel_seguridad, rol_usuario):
        """
        Determina si una acción específica requiere validación OTP.
        
        Args:
            accion (str): Tipo de acción ('ver', 'eliminar', 'descargar')
            nivel_seguridad (str): Nivel del documento ('publico', 'confidencial', 'secreto')
            rol_usuario (str): Rol del usuario ('usuario', 'supervisor', 'admin')
        
        Returns:
            bool: True si requiere OTP, False en caso contrario
        """
        
        # Matriz de acciones que requieren OTP
        reglas_otp = {
            'secreto': {
                'ver': True,      # Siempre requiere OTP para documentos secretos
                'eliminar': True,
                'descargar': True
            },
            'confidencial': {
                'ver': False,     # Ver no requiere OTP para confidenciales
                'eliminar': True, # Eliminar siempre requiere OTP
                'descargar': rol_usuario == 'usuario'  # Solo usuarios normales necesitan OTP
            },
            'publico': {
                'ver': False,
                'eliminar': rol_usuario != 'admin',  # Solo admin puede eliminar sin OTP
                'descargar': False
            }
        }
        
        return reglas_otp.get(nivel_seguridad, {}).get(accion, False)
    
    
    @staticmethod
    def validar_otp_para_documento(usuario_id, codigo_otp, documento_id, accion):
        """
        Validación OTP específica para acciones sobre documentos.
        Funcionalidad extendida para el sistema de documentos.
        
        Args:
            usuario_id (int): ID del usuario
            codigo_otp (str): Código OTP ingresado
            documento_id (int): ID del documento
            accion (str): Acción a realizar
        
        Returns:
            dict: Resultado detallado de la validación
        """
        
        resultado = {
            'validacion_exitosa': False,
            'mensaje': 'Validación OTP para documento',
            'usuario_id': usuario_id,
            'documento_id': documento_id,
            'accion': accion,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return resultado
    
    
    @staticmethod
    def limpiar_qr_antiguos(dias_antiguedad=7):
        """
        Limpia archivos QR antiguos para mantener el sistema ordenado.
        
        Args:
            dias_antiguedad (int): Días después de los cuales eliminar QR
        """
        try:
            carpeta_qr = current_app.config.get('QR_FOLDER', 'qr_codes')
            if not os.path.exists(carpeta_qr):
                return
            
            fecha_limite = datetime.now() - timedelta(days=dias_antiguedad)
            archivos_eliminados = 0
            
            for archivo in os.listdir(carpeta_qr):
                if archivo.startswith('qr_') and archivo.endswith('.png'):
                    ruta_archivo = os.path.join(carpeta_qr, archivo)
                    fecha_modificacion = datetime.fromtimestamp(os.path.getmtime(ruta_archivo))
                    
                    if fecha_modificacion < fecha_limite:
                        os.remove(ruta_archivo)
                        archivos_eliminados += 1
            
            current_app.logger.info(f"Limpieza QR: {archivos_eliminados} archivos eliminados")
            
        except Exception as e:
            current_app.logger.error(f"Error en limpieza QR: {str(e)}")


def generar_otp(rutusuario):
    resultado = GestorOTP.generar_otp_para_usuario(rutusuario)
    if resultado:
        return {
            'key32': resultado['clave_base32'],
            'url': resultado['url_qr'],
            'qrurl': resultado['archivo_qr']
        }
    else:
        return "Error", 400


def validar_otp(otp, base32generado):
    resultado = GestorOTP.validar_otp_codigo(otp, base32generado)
    if resultado['es_valido']:
        return "OTP valido"
    else:
        return "OTP invalido"