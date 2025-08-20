# Sistema de Gestión de Documentos Seguros

Sistema backend completo desarrollado en Flask para la gestión segura de documentos y archivos con autenticación JWT, sistema OTP (Doble factor de seguridad) y control de acceso basado en roles.

---

## **TRABAJO ENTREGABLE**

## Proyecto desarrollado por José Luis Cortese, de la carrera de Ingeniería en Ciencias de Datos en la asignatura de Ciencias de Datos.

## Unidad 2 - Semana 4 - Encargo

## Profesor a cargo: Juan Pablo Urzúa Otárola. IPG 2025

## **OBJETIVO DEL PROYECTO**

## Desarrollar un sistema backend robusto que permita la gestión segura de documentos y archivos con diferentes niveles de seguridad, implementando autenticación multifactor y control de acceso según roles de usuario.

## **ARQUITECTURA DEL PROYECTO**

### **Framework Principal**

- **Flask** (Python 3.11+)
- **SQLAlchemy** para Base de Datos
- **JWT** para autenticación de sesiones
- **Sistema OTP** integrado para acciones seguras (escalabilidad)

### **Estructura de Directorios**

```
proyecto_documentos/
├── app.py                      # Aplicación principal Flask
├── config.py                   # Configuración del sistema
├── requirements.txt            # Dependencias
├── models/                     # Modelos de datos
│   ├── __init__.py
│   ├── usuario.py             # Modelo Usuario con roles
│   ├── documento.py           # Modelo Documento con niveles
│   └── otp.py                 # Sistema OTP integrado
├── routes/                     # Rutas API
│   ├── auth.py                # Autenticación JWT/OTP
│   ├── documentos.py          # CRUD documentos completo
│   └── frontend.py            # Rutas para templates
│   └── monitoreo.py            # Rutas para monitoreo
├── utils/                      # Utilidades
│   ├── decoradores.py         # Middleware auth/roles
│   └── validaciones.py        # Validaciones centralizadas
├── static/                     # Archivos estáticos
│   ├── css/style.css          # Estilos responsive
│   └── js/                    # JavaScript modular
├── plantillas/                 # Templates HTML
│   ├── base.html              # Layout base
│   ├── auth/login.html        # Formulario login
│   └── documentos/             # Panel principal
├── uploads/                    # Archivos organizados por nivel
│   ├── publicos/
│   ├── confidenciales/
│   └── secretos/
└── documentos.db              # Base de datos SQLite
```

---

## **INSTALACIÓN Y CONFIGURACIÓN**

### **1. Clonar y Configurar**

```bash (terminal)
# Crear entorno virtual python en la ruta de clonación del proyecto
# Windows
python -m venv venv
source venv/Scripts/activate

# MacOs / Linux
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar aplicación
python app.py
```

### **2. Configuración Automática**

El sistema se configura automáticamente en el primer arranque:

- Crea base de datos SQLite
- Genera carpetas de uploads organizadas
- Crea 3 usuarios de prueba con diferentes roles

### **3. Acceso al Sistema**

```
URL: http://localhost:5000
```

---

## **USUARIOS DE PRUEBA**

El sistema crea automáticamente usuarios para testing:

| Email               | Contraseña    | Rol        | Permisos                         |
| ------------------- | ------------- | ---------- | -------------------------------- |
| admin@test.com      | admin123      | admin      | Acceso total, elimina sin OTP    |
| supervisor@test.com | supervisor123 | supervisor | Gestiona públicos/confidenciales |
| usuario@test.com    | usuario123    | usuario    | Solo sus documentos + públicos   |

---

## **SISTEMA DE SEGURIDAD**

### **Autenticación**

- **JWT**: Tokens de sesión con expiración configurable
- **OTP**: Códigos de un solo uso para acciones sensibles
- **Rate Limiting**: Protección contra ataques de fuerza bruta (tecnica de restricción que restringe la cantidad de solicitudes a un endpoint)

### **Autorización por Roles**

#### **Usuario Normal**

- Ver documentos públicos y propios
- Crear documentos públicos/confidenciales
- No puede crear documentos secretos
- No puede ver documentos de otros usuarios

#### **Supervisor**

- Todo lo de usuario normal
- Ver todos los documentos públicos/confidenciales
- Crear documentos secretos
- No puede ver documentos secretos de otros

#### **Administrador**

- Acceso total a todos los documentos
- Eliminar documentos públicos/confidenciales propios y de otros con OTP

### **Niveles de Seguridad de Documentos**

| Nivel            | Descripción           | Quién Puede Ver          | OTP Requerido      |
| ---------------- | --------------------- | ------------------------ | ------------------ |
| **Público**      | Acceso general        | Todos los usuarios       | Solo para eliminar |
| **Confidencial** | Información sensible  | Propietario + superiores | Solo para eliminar |
| **Secreto**      | Altamente clasificado | Propietario + Admin      | Siempre            |

### **Matriz de Uso requerido de OTP por Acción**

| Acción / Nivel | Público | Confidencial | Secreto |
| -------------- | ------- | ------------ | ------- |
| **Ver**        | No      | No           | Si      |
| **Eliminar**   | Si      | Si           | Si      |
| **Descargar**  | No      | Si           | Si      |

---

## **API RESTful COMPLETA**

### **Autenticación**

```http
POST   /api/auth/login                          # Login con JWT
POST   /api/auth/refresh                        # Refrescar Token JWT
POST   /api/auth/logout                         # Cerrar sesión
GET    /api/auth/verificar                      # Verificar token
GET    /api/auth/perfil                         # Datos del usuario logueado
GET    /api/auth/otp/generar                    # Generar código OTP
GET    /api/auth/otp/estado                     # Verificar OTP activo de usuario
POST   /api/auth/otp/configurar-inicial         # Seteo inicial con validación de OTP
POST   /api/auth/otp/resetear                   # Reseteo de OTP de usuario
POST   /api/auth/otp/validar                    # Validar código OTP
```

### **Gestión de Documentos**

```http
POST   /api/documentos              # Crear registro de archivo (Subir archivo)
GET    /api/documentos              # Lista de archivos con filtros/paginación
GET    /api/documentos/<id>         # Ver documento específico
PUT    /api/documentos/<id>         # Actualizar datos del archivo
DELETE /api/documentos/<id>         # Eliminar documento
GET    /api/documentos/<id>/descargar # Descargar archivo
```

### **Búsqueda y Estadísticas**

```http
POST   /api/documentos/buscar       # Búsqueda avanzada
GET    /api/documentos/por-nivel/<nivel> # Filtrar por nivel
```

### **Utilidad**

```http
GET    /api/health                  # Estado del sistema
GET    /api                         # Información general
```

---

## **FRONTEND WEB**

### **Características**

- **Responsive**: Diseño con Bootstrap 5
- **Modular**: JavaScript organizado en módulos
- **Intuitivo**: Drag & drop para subida de archivos
- **Seguro**: Modal OTP integrado para acciones sensibles

### **Páginas Principales**

- **Login**: Autenticación con usuarios de prueba
- **Gestión Documentos**: CRUD completo con interfaz

---

## **FUNCIONALIDADES IMPLEMENTADAS**

### **Backend Core (Flask)**

- **API RESTful completa** (8 endpoints principales)
- **Autenticación JWT** con refresh tokens
- **Sistema OTP integrado** para acciones sensibles
- **Control de acceso** por roles
- **Gestión de archivos** organizada por nivel de seguridad
- **Validaciones robustas** de datos y archivos
- **Búsqueda avanzada** con filtros múltiples
- **Auditoría completa** de todas las acciones
- **Rate limiting** para protección de API

### **Seguridad**

- **Autenticación multifactor** (JWT + OTP)
- **Autorización basada en roles** (3 niveles)
- **Validación de archivos** (tipo, tamaño, contenido)
- **Protección CSRF** y headers de seguridad (Cross-Site)
- **Encriptación de contraseñas** con bcrypt

### **Optimización**

- **Organización eficiente** de archivos por nivel
- **Respuestas JSON estandarizadas**
- **Manejo centralizado de errores**
- **Logging detallado** para debugging

---

## **CONFIGURACIÓN**

### **Variables de Entorno**

```bash
# Desarrollo
FLASK_ENV=development
JWT_SECRET_KEY=clave-secreta-jwt
MAX_FILE_SIZE=16777216  # 16MB

```

### **Problemas Comunes**

**Error: Base de datos no encontrada**

```bash
# Solución: La app crea automáticamente la BD en primer arranque
python app.py
```

**Error: Archivos no se suben**

```bash
# Verificar permisos de carpeta uploads/
chmod 755 uploads/
```

**Error: OTP no funciona**

```bash
# Verificar configuración en config.py
OTP_EXPIRATION = 300  # 5 minutos
```

---

## **CONCLUSIÓN**

Sistema completo de gestión de documentos corporativos que cumple con todos los requisitos de seguridad, escalabilidad y funcionalidad requeridos para un entorno empresarial real.

**Características destacadas:**

- Backend robusto con Flask
- Seguridad multifactor (JWT + OTP)
- Control de acceso granular
- API RESTful completa
- Frontend moderno responsive
- Arquitectura escalable y mantenible

**Uso ideal para:**

- Empresas que manejan información sensible
- Organizaciones con múltiples niveles de acceso
- Aplicaciones que necesitan autenticación multifactor
